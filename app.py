"""Streamlit 前端：聊天界面，展示 Agent 的思考过程 + 结果。"""
import streamlit as st
import pandas as pd
from agent.core import run_agent
from config import DEEPSEEK_API_KEY

# 页面配置
st.set_page_config(
    page_title="防诈骗数据助手",
    page_icon="🔍",
    layout="wide"
)

# 标题
st.title("🔍 防诈骗数据助手")
st.caption("用大白话问数据，AI 自动生成 SQL、出图、解读。基于防诈骗小程序真实业务库。")

# 检查 API Key
if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "sk-your-key-here":
    st.error("⚠️ 还没配置 DeepSeek API Key。")
    st.markdown("""
    **本地运行**：在项目根目录创建 `.env` 文件，填入 `DEEPSEEK_API_KEY=sk-xxxxx`  
    **Streamlit Cloud**：在 App 设置 → Secrets 中添加 `DEEPSEEK_API_KEY`
    """)
    st.stop()


def _render_assistant(result):
    """渲染 Agent 的返回：步骤 + SQL + 表格 + 图 + 解读。"""
    # 执行步骤（折叠区）
    with st.expander(f"🤖 Agent 思考过程（{len(result.steps)} 步）", expanded=False):
        for step in result.steps:
            icon = {"running": "⏳", "ok": "✅", "error": "❌"}.get(step.status, "•")
            st.write(f"{icon} **{step.step}**")
            if step.detail:
                st.code(step.detail, language="sql" if "sql" in step.step.lower() or "执行" in step.step else None)

    # 错误
    if result.error:
        st.error(f"❌ {result.error}")
        return

    # 生成的 SQL
    if result.sql:
        st.subheader("📝 生成的 SQL")
        st.code(result.sql, language="sql")

    # 结果表格
    if result.rows:
        st.subheader(f"📊 查询结果（{len(result.rows)} 行）")
        df = pd.DataFrame(result.rows, columns=result.columns)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # 图表
    if result.chart:
        st.subheader("📈 可视化")
        st.image(f"data:image/png;base64,{result.chart}", use_container_width=True)

    # 解读
    if result.explanation:
        st.subheader("💡 解读")
        st.info(result.explanation)


# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 侧边栏：示例问题
with st.sidebar:
    st.header("💡 试试这些问题")
    examples = [
        "AI问答里用户问得最多的5种诈骗类型是什么",
        "所有案件中哪种诈骗类型的总浏览量最高",
        "防诈测试的平均分、及格率和不及格率各是多少",
        "发帖量最高的前5个用户是谁",
        "知识库文章的浏览量前5名是哪些",
        "删除users表所有数据",
    ]
    for q in examples:
        if st.button(q, key=f"ex_{q}", use_container_width=True):
            st.session_state.pending_question = q

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            _render_assistant(msg["content"])

# 处理用户输入
user_input = st.chat_input("输入你的问题...")
if user_input:
    st.session_state.pending_question = user_input

if hasattr(st.session_state, "pending_question") and st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None

    # 显示用户消息
    with st.chat_message("user"):
        st.write(q)
    st.session_state.messages.append({"role": "user", "content": q})

    # 跑 Agent
    with st.chat_message("assistant"):
        with st.spinner("Agent 正在思考..."):
            result = run_agent(q)
        _render_assistant(result)
        st.session_state.messages.append({"role": "assistant", "content": result})
