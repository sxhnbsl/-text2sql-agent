"""Agent 核心循环：LLM 大脑 + 工具调度 + 自我纠错。

流程：
  用户问题
    → 拿 schema
    → LLM 生成 SQL
    → 校验 SQL（拦危险操作）
    → 执行 SQL
      → 失败？把错误信息喂回 LLM，让它修正，最多重试 2 次
    → 画图
    → LLM 解读
    → 返回给用户
"""
from dataclasses import dataclass
from agent.tools import (
    get_schema, generate_sql, validate_sql, execute_sql, plot_chart, explain_result
)


@dataclass
class AgentStep:
    """记录 Agent 每一步的执行过程，给前端展示。"""
    step: str       # 步骤名
    detail: str     # 详情
    status: str     # running / ok / error


@dataclass
class AgentResult:
    """Agent 最终返回给前端的结构。"""
    steps: list          # 执行步骤
    sql: str             # 最终执行的 SQL
    columns: list        # 结果列名
    rows: list           # 结果数据
    chart: str | None    # base64 图（可能为空）
    explanation: str     # LLM 解读
    error: str | None    # 出错时的错误信息


def run_agent(question: str) -> AgentResult:
    """Text2SQL Agent 主循环。"""
    steps = []
    sql = ""
    error = None

    # Step 1: 拿 schema
    steps.append(AgentStep("分析表结构", "正在读取数据库 schema...", "running"))
    try:
        schema = get_schema()
        steps[-1].status = "ok"
        steps[-1].detail = f"已加载 {schema.count('##')} 张表的结构信息"
    except Exception as e:
        steps[-1].status = "error"
        steps[-1].detail = str(e)
        return AgentResult(steps, "", [], [], None, "", f"读取数据库失败：{e}")

    # Step 2: 生成 SQL
    steps.append(AgentStep("生成 SQL", "LLM 正在根据你的问题生成 SQL...", "running"))
    try:
        sql = generate_sql(question, schema)
        if sql == "CANNOT_ANSWER":
            steps[-1].status = "error"
            steps[-1].detail = "这个问题超出数据库能回答的范围"
            return AgentResult(steps, "", [], [], None, "", "这个问题数据库答不了，换个问法试试")
        steps[-1].status = "ok"
        steps[-1].detail = sql
    except Exception as e:
        steps[-1].status = "error"
        steps[-1].detail = str(e)
        return AgentResult(steps, "", [], [], None, "", f"生成 SQL 失败：{e}")

    # Step 3: 校验 SQL
    steps.append(AgentStep("安全校验", "检查 SQL 是否含危险操作...", "running"))
    ok, reason = validate_sql(sql)
    if not ok:
        steps[-1].status = "error"
        steps[-1].detail = f"已拦截：{reason}"
        return AgentResult(steps, sql, [], [], None, "", f"SQL 安全校验未通过：{reason}")
    steps[-1].status = "ok"
    steps[-1].detail = "通过，是只读 SELECT"

    # Step 4: 执行 SQL（带自我纠错，最多重试 2 次）
    columns, rows, df = [], [], None
    max_retries = 2
    current_sql = sql
    for attempt in range(max_retries + 1):
        label = "执行 SQL" if attempt == 0 else f"修正后重试 ({attempt}/{max_retries})"
        steps.append(AgentStep(label, current_sql, "running"))
        try:
            columns, rows, df = execute_sql(current_sql)
            steps[-1].status = "ok"
            steps[-1].detail = f"返回 {len(rows)} 行数据"
            sql = current_sql
            break
        except Exception as e:
            steps[-1].status = "error"
            err_msg = str(e)
            steps[-1].detail = err_msg
            if attempt < max_retries:
                # 让 LLM 看着报错信息修正 SQL
                steps.append(AgentStep(f"自我纠错 ({attempt+1}/{max_retries})", f"SQL 报错：{err_msg}，让 LLM 修正...", "running"))
                try:
                    current_sql = _fix_sql(question, schema, current_sql, err_msg)
                    steps[-1].status = "ok"
                    steps[-1].detail = f"修正后的 SQL：{current_sql}"
                except Exception as fix_err:
                    steps[-1].status = "error"
                    steps[-1].detail = f"修正失败：{fix_err}"
                    error = f"SQL 执行失败且自动修正也失败：{err_msg}"
                    return AgentResult(steps, current_sql, [], [], None, "", error)
            else:
                error = f"SQL 执行失败，重试 {max_retries} 次后仍报错：{err_msg}"
                return AgentResult(steps, current_sql, [], [], None, "", error)

    # Step 5: 画图
    chart = None
    if df is not None and len(df) > 0:
        steps.append(AgentStep("生成图表", "正在根据数据自动选图...", "running"))
        try:
            chart = plot_chart(df, question)
            steps[-1].status = "ok"
            steps[-1].detail = "图表已生成" if chart else "当前数据不适合画图"
        except Exception as e:
            steps[-1].status = "error"
            steps[-1].detail = str(e)

    # Step 6: 解读
    steps.append(AgentStep("结果解读", "LLM 正在用大白话解释...", "running"))
    try:
        explanation = explain_result(question, df)
        steps[-1].status = "ok"
        steps[-1].detail = "解读完成"
    except Exception as e:
        steps[-1].status = "error"
        steps[-1].detail = str(e)
        explanation = "解读生成失败"

    return AgentResult(steps, sql, columns, rows, chart, explanation, error)


def _fix_sql(question: str, schema: str, bad_sql: str, err_msg: str) -> str:
    """自我纠错：把报错信息喂回 LLM，让它修正 SQL。"""
    from agent.tools import llm_client, MODEL_NAME
    from config import DEEPSEEK_API_KEY, API_BASE
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=API_BASE)

    prompt = f"""刚才生成的 SQL 执行报错了，请修正。

用户问题：{question}

表结构：
{schema}

原 SQL：
{bad_sql}

报错信息：
{err_msg}

修正后的 SQL（只输出 SQL 本身，不要任何解释）：
"""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return resp.choices[0].message.content.strip().strip("`")
