# 防诈骗数据助手 (Text2SQL Agent)

> 用大白话问数据，AI 自动生成 SQL、执行、出图、解读。基于防诈骗小程序真实业务库。

## 这是什么

一个 Text2SQL 数据分析 Agent —— 让不会写 SQL 的人（运营/产品/老板）用自然语言问数据库，Agent 自动完成：

1. **理解问题** → 分析意图
2. **Schema Linking** → 从 17 张表里定位到相关表
3. **生成 SQL** → LLM 写 SELECT 语句
4. **安全校验** → 拦截 DROP/DELETE 等危险操作
5. **执行 SQL** → 连 MySQL 查数
6. **自我纠错** → SQL 报错时自动修正重试（最多2次）
7. **画图** → 自动选柱状图/折线图
8. **解读** → LLM 用大白话解释结果

## 技术栈

- **Python 3.13**
- **Streamlit** — 前端 UI
- **OpenAI SDK** — 调 DeepSeek（接口兼容）
- **PyMySQL** — 连 MySQL
- **Pandas + Matplotlib** — 数据处理 + 可视化

## 数据源

复用防诈骗科普社区平台的真实业务库 `anti_fraud_platform`，包含 17 张表：
- `users` — 用户表
- `chat_history` — AI 问答记录
- `cases` — 诈骗案例
- `knowledge` — 防诈知识库
- `posts` / `comments` — 社区论坛
- `test_record` / `test_question` — 防诈测试
- 等等

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key 和 MySQL 密码
```

`.env` 内容：
```
DEEPSEEK_API_KEY=sk-your-real-key
MODEL_NAME=deepseek-chat

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=anti_fraud_platform
```

### 3. 启动

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

## 试试这些问题

- "AI问答里用户问得最多的5种诈骗类型是什么"
- "最近一个月每天有多少条AI问答记录"
- "防诈测试平均分是多少，及格率和不及格率各占多少"
- "发帖量最高的前5个用户是谁"
- "哪种诈骗类型的案件浏览量最高"
- "删除users表所有数据"  ← 应该被拦截

## 项目结构

```
text2sql-agent/
├── app.py              # Streamlit 前端
├── config.py           # 配置加载
├── requirements.txt
├── .env.example
├── .gitignore
└── agent/
    ├── __init__.py
    ├── tools.py        # 6个工具函数
    └── core.py         # Agent 核心循环 + 自我纠错
```

## 面试可聊的技术点

- **Schema Linking**：怎么让 LLM 从17张表里找到正确的表
- **SQL 安全防护**：黑名单关键词 + 只允许 SELECT + 防分号注入
- **自我纠错**：SQL 报错后把错误信息喂回 LLM 让它修正
- **自动选图**：根据结果列数和数据类型自动选柱状图/折线图
- **成本控制**：强制加 LIMIT 500 防止超大结果集
