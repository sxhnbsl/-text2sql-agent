"""把 MySQL 数据导出到 SQLite，用于 Streamlit Cloud 免费部署（连不到本地 MySQL）。"""
import sqlite3
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

mysql_conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "anti_fraud_platform"),
    charset="utf8mb4",
)

sqlite_conn = sqlite3.connect("demo.db")
mc = mysql_conn.cursor()
mc.execute("SHOW TABLES")
tables = [r[0] for r in mc.fetchall()]

for t in tables:
    mc.execute(f"SELECT * FROM `{t}`")
    rows = mc.fetchall()
    cols = [c[0] for c in mc.description]
    types = {c[0]: c[1] for c in mc.description}

    # 建表
    col_defs = []
    pk_col = None
    mc.execute(f"DESCRIBE `{t}`")
    for col_info in mc.fetchall():  # 0=Field,1=Type,2=Null,3=Key
        name = col_info[0]
        mysql_type = col_info[1].lower()
        is_pk = col_info[3] == "PRI"
        nullable = "" if col_info[2] == "NO" else ""

        # 类型映射: MySQL → SQLite
        if "int" in mysql_type:
            sqlite_type = "INTEGER"
        elif any(x in mysql_type for x in ["float", "double", "decimal"]):
            sqlite_type = "REAL"
        else:
            sqlite_type = "TEXT"

        col_def = f'"{name}" {sqlite_type}{nullable}'
        col_defs.append(col_def)
        if is_pk:
            pk_col = name

    if pk_col:
        col_defs.append(f"PRIMARY KEY (\"{pk_col}\")")

    create_sql = f'CREATE TABLE IF NOT EXISTS "{t}" ({", ".join(col_defs)})'
    sqlite_conn.execute(create_sql)

    # 插数据
    if rows:
        placeholders = ", ".join(["?" for _ in cols])
        quoted_cols = ", ".join([f'"{c}"' for c in cols])
        insert_sql = f'INSERT OR REPLACE INTO "{t}" ({quoted_cols}) VALUES ({placeholders})'

        # 处理数据：MySQL 行转 SQLite 兼容格式
        clean_rows = []
        for row in rows:
            clean = []
            for val in row:
                if val is None:
                    clean.append(None)
                elif isinstance(val, bytes):
                    clean.append(val.decode("utf-8", errors="replace"))
                elif isinstance(val, bytearray):
                    clean.append(bytes(val).decode("utf-8", errors="replace"))
                else:
                    clean.append(val)
            clean_rows.append(tuple(clean))

        sqlite_conn.executemany(insert_sql, clean_rows)

    print(f"[OK] {t}: {len(rows)} rows")

mysql_conn.close()
sqlite_conn.commit()
sqlite_conn.close()
print("\n=== 导出完成: demo.db ===")
