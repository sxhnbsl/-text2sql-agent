"""配置：从 .env 读敏感信息，代码里不硬编码。"""
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")
API_BASE = "https://api.deepseek.com"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "anti_fraud_platform")

# 自动检测 SQLite 模式：本地直接连 MySQL，Streamlit Cloud 用 demo.db
USE_SQLITE = os.path.exists(os.path.join(os.path.dirname(__file__), "demo.db")) or \
             os.getenv("USE_SQLITE", "").lower() == "true"

# 只允许 SELECT，拦截一切写/改/删操作
DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "PRAGMA",
    "CREATE", "RENAME", "REPLACE", "LOAD_FILE", "INTO OUTFILE"
]
