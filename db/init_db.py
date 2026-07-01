"""建库 + 灌样例数据。防诈骗小程序领域，5 张表。

跑一次：python db/init_db.py
之后 db/fraud.db 就有了，Agent 直接连它。
"""
import sqlite3
import random
from datetime import datetime, timedelta
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "fraud.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    nickname TEXT,
    age INTEGER,
    gender TEXT,
    city TEXT,
    register_time TEXT
);

CREATE TABLE IF NOT EXISTS ai_chat_logs (
    log_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    topic TEXT,
    question TEXT,
    answer TEXT,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS knowledge_views (
    view_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    article_id INTEGER,
    article_title TEXT,
    view_duration INTEGER,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS fraud_cases (
    case_id INTEGER PRIMARY KEY,
    fraud_type TEXT,
    victim_age INTEGER,
    city TEXT,
    loss_amount REAL,
    report_time TEXT
);

CREATE TABLE IF NOT EXISTS quiz_results (
    result_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    score INTEGER,
    total_questions INTEGER,
    passed INTEGER,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""


TOPICS = [
    "冒充客服退款", "虚假投资理财", "冒充公检法",
    "刷单返利", "虚假中奖", "冒充熟人借款",
    "杀猪盘", "网贷诈骗", "注销校园贷", "虚假购物"
]

CITIES = ["广州", "深圳", "北京", "上海", "杭州", "成都", "武汉", "西安", "南京", "重庆"]

ARTICLES = [
    (1, "教你识别冒充客服退款诈骗"),
    (2, "投资理财防坑指南"),
    (3, "公检法不会让你转账"),
    (4, "刷单就是诈骗"),
    (5, "中奖信息都是套路"),
    (6, "熟人借钱先打电话核实"),
    (7, "网恋对象让你投资怎么办"),
    (8, "网贷前先看这三点"),
]


def gen_users(n=200):
    rows = []
    for i in range(1, n + 1):
        age = random.randint(18, 65)
        gender = random.choice(["男", "女"])
        city = random.choice(CITIES)
        days_ago = random.randint(1, 180)
        reg = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        rows.append((i, f"用户{i:04d}", age, gender, city, reg))
    return rows


def gen_chat_logs(users, n=2000):
    rows = []
    for i in range(1, n + 1):
        uid = random.choice(users)[0]
        topic = random.choice(TOPICS)
        q = f"我遇到了{topic}的情况，怎么办？"
        a = f"关于{topic}，请警惕以下几点：1.核实对方身份 2.不轻易转账 3.及时报警。"
        days_ago = random.randint(0, 90)
        t = (datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        rows.append((i, uid, topic, q, a, t))
    return rows


def gen_views(users, n=1500):
    rows = []
    for i in range(1, n + 1):
        uid = random.choice(users)[0]
        art = random.choice(ARTICLES)
        dur = random.randint(10, 600)
        days_ago = random.randint(0, 90)
        t = (datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        rows.append((i, uid, art[0], art[1], dur, t))
    return rows


def gen_cases(n=500):
    rows = []
    for i in range(1, n + 1):
        ftype = random.choice(TOPICS)
        age = random.randint(18, 70)
        city = random.choice(CITIES)
        loss = round(random.uniform(500, 200000), 2)
        days_ago = random.randint(0, 180)
        t = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        rows.append((i, ftype, age, city, loss, t))
    return rows


def gen_quiz(users, n=800):
    rows = []
    for i in range(1, n + 1):
        uid = random.choice(users)[0]
        total = 10
        score = random.randint(0, total)
        passed = 1 if score >= 6 else 0
        days_ago = random.randint(0, 90)
        t = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        rows.append((i, uid, score, total, passed, t))
    return rows


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[clean] 旧库已删除: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    print("[schema] 5 张表已创建")

    users = gen_users(200)
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", users)
    print(f"[data] users: {len(users)} 行")

    chats = gen_chat_logs(users, 2000)
    cur.executemany("INSERT INTO ai_chat_logs VALUES (?,?,?,?,?,?)", chats)
    print(f"[data] ai_chat_logs: {len(chats)} 行")

    views = gen_views(users, 1500)
    cur.executemany("INSERT INTO knowledge_views VALUES (?,?,?,?,?,?)", views)
    print(f"[data] knowledge_views: {len(views)} 行")

    cases = gen_cases(500)
    cur.executemany("INSERT INTO fraud_cases VALUES (?,?,?,?,?,?)", cases)
    print(f"[data] fraud_cases: {len(cases)} 行")

    quizzes = gen_quiz(users, 800)
    cur.executemany("INSERT INTO quiz_results VALUES (?,?,?,?,?,?)", quizzes)
    print(f"[data] quiz_results: {len(quizzes)} 行")

    conn.commit()
    conn.close()
    print(f"\n[done] 数据库就绪: {DB_PATH}")
    print("[next] 运行 streamlit run app.py 启动应用")


if __name__ == "__main__":
    main()
