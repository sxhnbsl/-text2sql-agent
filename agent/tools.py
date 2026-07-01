"""工具函数：Agent 调用的所有能力都写在这里。

每个函数对应 Agent 大脑可以调用的一个"工具"：
  get_schema()        —— 拿数据库表结构
  generate_sql()      —— 让 LLM 生成 SQL
  validate_sql()      —— 安全校验（拦危险操作）
  execute_sql()       —— 执行只读 SQL
  plot_chart()        —— 用 matplotlib 画图
  explain_result()    —— 让 LLM 用大白话解释结果
"""
import re
import io
import base64
import os
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无头模式，不弹窗
import matplotlib.pyplot as plt
from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY, MODEL_NAME, API_BASE,
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    DANGEROUS_KEYWORDS, USE_SQLITE
)

# 本地模式才需要 pymysql，Streamlit Cloud 只用 sqlite3
if not USE_SQLITE:
    import pymysql

# 中文字体（Windows 上常见的黑体）
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# 复用 OpenAI SDK 调 DeepSeek（接口兼容）
_llm_client = None

def get_llm_client():
    """延迟初始化：用到时才创建，避免 Secret 未配时导入就崩溃。"""
    global _llm_client
    if _llm_client is None:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置。请在 .env 或 Streamlit Cloud Secrets 中设置。")
        _llm_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=API_BASE)
    return _llm_client


def get_db_conn():
    """每次操作新建连接。本地用 MySQL，Streamlit Cloud 用 SQLite。"""
    if USE_SQLITE:
        db_path = os.path.join(os.path.dirname(__file__), "..", "demo.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        return pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME, charset="utf8mb4"
        )


def get_schema() -> str:
    """工具1：拿全部表结构，喂给 LLM 做 schema linking。

    返回格式化的建表信息，例如：
      ## users (35 rows)
        id            bigint        PK
        nickname      varchar(50)
        ...
    """
    conn = get_db_conn()
    cur = conn.cursor()

    if USE_SQLITE:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
    else:
        cur.execute("SHOW TABLES")
        tables = [r[0] for r in cur.fetchall()]

    lines = []
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM \"{t}\"")
        cnt = cur.fetchone()[0]

        if USE_SQLITE:
            cur.execute(f"PRAGMA table_info(\"{t}\")")
            cols = cur.fetchall()
        else:
            cur.execute(f"DESCRIBE `{t}`")
            cols = cur.fetchall()

        lines.append(f"## {t}  ({cnt} rows)")
        for c in cols:
            pk = "PK" if c[-1] == 1 else ""
            name = c[1] if USE_SQLITE else c[0]
            dtype = c[2] if USE_SQLITE else c[1]
            lines.append(f"  {name:28s} {dtype:20s} {pk}")
        lines.append("")
    conn.close()
    return "\n".join(lines)


SQL_SYSTEM_PROMPT = """你是 SQL 生成专家。根据用户的问题和下面的数据库表结构，生成一条只读 SELECT 语句。

规则：
1. 只能生成 SELECT 语句，绝对不能生成 DROP/DELETE/UPDATE/INSERT/ALTER 等写操作
2. 表名和字段名用双引号 "" 包裹
3. 字段值用单引号
4. 涉及中文 LIKE 查询时用 LIKE '%关键词%'
5. 时间字段用 created_at / test_date / report_time 等，按问题语义选择
6. 只输出 SQL 本身，不要任何解释、不要 markdown 代码块标记
7. 如果用户问题超出数据库能回答的范围，直接返回：CANNOT_ANSWER
"""


def generate_sql(question: str, schema: str) -> str:
    """工具2：让 LLM 根据问题 + schema 生成 SQL。"""
    resp = get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": f"表结构：\n{schema}\n\n用户问题：{question}\n\n生成的 SQL："}
        ],
        temperature=0
    )
    sql = resp.choices[0].message.content.strip()
    # 防止 LLM 包了 markdown
    sql = sql.strip("`")
    return sql


def validate_sql(sql: str) -> tuple[bool, str]:
    """工具3：安全校验。返回 (是否通过, 原因)。"""
    sql_upper = sql.upper()

    # 1. 必须是 SELECT 开头
    if not sql_upper.strip().startswith("SELECT"):
        return False, "只允许 SELECT 查询"

    # 2. 危险关键词黑名单（注意用单词边界，避免误伤字段名）
    for kw in DANGEROUS_KEYWORDS:
        pattern = r"\b" + kw + r"\b"
        if re.search(pattern, sql_upper):
            return False, f"检测到危险关键词：{kw}，已拦截"

    # 3. 防止分号串联多条语句
    if ";" in sql.rstrip(";"):
        return False, "不允许分号串联多条 SQL"

    return True, "ok"


def execute_sql(sql: str, limit: int = 500) -> tuple[list, list]:
    """工具4：执行只读 SQL，返回 (列名, 行数据)。"""
    conn = get_db_conn()
    try:
        # 强制加 LIMIT，防止超大结果集
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + f" LIMIT {limit};"
        df = pd.read_sql(sql, conn)
        return df.columns.tolist(), df.values.tolist(), df
    finally:
        conn.close()


def plot_chart(df: pd.DataFrame, question: str) -> str | None:
    """工具5：根据结果自动选图画图，返回 base64 编码的 PNG。

    策略：
      - 先找出第一列「分类维度」和第一列「数值」
      - 如果分类维度是日期/时间 → 折线图
      - 否则 → 横向柱状图
    """
    if df is None or len(df) == 0:
        return None

    try:
        # 找第一列能当分类维度的列（非数值优先）
        categorical_candidates = []
        numeric_candidates = []
        for c in df.columns:
            try:
                pd.to_numeric(df[c])
                numeric_candidates.append(c)
            except Exception:
                categorical_candidates.append(c)

        # 如果没找到分类列，用第一列当 x 轴
        x_col = categorical_candidates[0] if categorical_candidates else df.columns[0]
        # 数值列优先选第一列数值列，不是 x_col
        y_col = [c for c in numeric_candidates if c != x_col][0] if [c for c in numeric_candidates if c != x_col] else numeric_candidates[0] if numeric_candidates else df.columns[1] if len(df.columns) > 1 else None
        if y_col is None or x_col == y_col:
            return None

        # 复制数据并清洗
        plot_df = df[[x_col, y_col]].copy()
        plot_df[y_col] = plot_df[y_col].apply(lambda v: float(v) if v is not None else None)
        plot_df = plot_df.dropna(subset=[y_col])
        if len(plot_df) == 0:
            return None

        # 判断 x 轴是不是日期
        is_date = False
        try:
            pd.to_datetime(plot_df[x_col])
            is_date = True
        except Exception:
            pass

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=100)

        if is_date and len(df.columns) >= 2:
            # 折线图：日期 x 轴，其他数值列当 y 轴
            plot_df[x_col] = pd.to_datetime(plot_df[x_col])
            # 把其他数值列也画出来
            numeric_other = [c for c in numeric_candidates if c != x_col]
            for i, c in enumerate(numeric_other):
                plot_df[c] = plot_df[c].apply(lambda v: float(v) if v is not None else None)
                plot_df_nona = plot_df.dropna(subset=[c])
                ax.plot(plot_df_nona[x_col], plot_df_nona[c], marker="o", label=c, color=["#378ADD", "#EF9F27"][i % 2])
            ax.legend()
            ax.set_xlabel(x_col)
            ax.set_ylabel("数值")
            plt.xticks(rotation=30)
        else:
            # 横向柱状图：分类维度 x 轴，数值 y 轴
            plot_df[x_col] = plot_df[x_col].fillna("未分类/NULL").astype(str).str.slice(0, 15)
            plot_df = plot_df.sort_values(by=y_col, ascending=True).tail(20)
            ax.bar(plot_df[x_col], plot_df[y_col], color="#378ADD")
            ax.set_ylabel(y_col)
            ax.set_xlabel(x_col)
            plt.xticks(rotation=30)

        ax.set_title(question[:30], fontsize=12)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        return img_b64
    except Exception as e:
        plt.close("all")
        return None


EXPLAIN_PROMPT = """你是数据分析助手。用户问了一个问题，查询数据库得到了下面的结果。
请用大白话（中文）给用户解释这个结果，要求：
1. 先说结论（最关键的1-2个发现）
2. 再给2-3条具体数据支撑
3. 如果有业务含义，给一句行动建议
4. 不要超过150字，不要列 SQL，不要列字段名
"""


def explain_result(question: str, df: pd.DataFrame) -> str:
    """工具6：让 LLM 用大白话解读查询结果。"""
    if df is None or len(df) == 0:
        return "查询没有返回数据，可能是这个条件目前库里还没有相关记录。"

    # 把 df 压缩成 LLM 能读的文本（最多前 30 行）
    preview = df.head(30).to_string(index=False)
    resp = get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": EXPLAIN_PROMPT},
            {"role": "user", "content": f"用户问题：{question}\n\n查询结果：\n{preview}"}
        ],
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()
