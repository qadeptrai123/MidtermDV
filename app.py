import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Dashboard Giữa Kì - Data Visualization",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown(
    """
    <style>
    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29, #302b63, #24243e);
    }
    [data-testid="stSidebar"] * {
        color: #f0f0f0 !important;
    }

    /* ---------- Radio buttons as card-style tabs ---------- */
    [data-testid="stSidebar"] .stRadio > div {
        gap: 0.35rem;
    }
    [data-testid="stSidebar"] .stRadio > div > label {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 10px;
        padding: 0.65rem 1rem;
        cursor: pointer;
        transition: all 0.25s ease;
    }
    [data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255, 255, 255, 0.14);
        border-color: rgba(255, 255, 255, 0.25);
    }
    [data-testid="stSidebar"] .stRadio > div > label[data-checked="true"] {
        background: rgba(99, 102, 241, 0.35);
        border-color: #6366f1;
    }

    /* ---------- Main area ---------- */
    .block-container {
        padding-top: 1.5rem;
    }

    /* ---------- Metric cards ---------- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea33, #764ba233);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 📊 Data Visualization")
    st.markdown("### Midterm Project Dashboard")
    st.markdown("---")

    selected = st.radio(
        "**Chọn câu hỏi nghiên cứu:**",
        options=[
            "📌 Câu hỏi 1",
            "📌 Câu hỏi 2",
            "📌 Câu hỏi 3",
            "📌 Câu hỏi 4",
            "📌 Câu hỏi 5",
        ],
        index=0,
        label_visibility="visible",
    )

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; font-size:0.75rem; opacity:0.5;'>"
        "© 2026 – Midterm DV Project"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# HELPER – Sample data (Replace with your real data)
# ============================================================
@st.cache_data
def load_sample_data():
    """Return a sample DataFrame for demonstration."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "category": np.random.choice(["A", "B", "C", "D"], size=len(dates)),
            "value": np.random.randint(10, 100, size=len(dates)),
            "score": np.round(np.random.uniform(1, 10, size=len(dates)), 2),
        }
    )
    return df


df = load_sample_data()


# ============================================================
# PAGE RENDERERS
# ============================================================
def render_question_1():
    st.header("📌 Câu hỏi nghiên cứu 1")
    st.markdown("> *Mô tả câu hỏi nghiên cứu 1 ở đây…*")
    st.markdown("---")

    # -- KPI row
    col1, col2, col3 = st.columns(3)
    col1.metric("Tổng bản ghi", f"{len(df):,}")
    col2.metric("Giá trị trung bình", f"{df['value'].mean():.1f}")
    col3.metric("Điểm cao nhất", f"{df['score'].max()}")

    # -- Chart
    fig = px.line(
        df.groupby("date")["value"].sum().reset_index(),
        x="date",
        y="value",
        title="Biểu đồ mẫu – Line Chart",
        template="plotly_dark",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, width="stretch")


def render_question_2():
    st.header("📌 Câu hỏi nghiên cứu 2")
    st.markdown("> *Mô tả câu hỏi nghiên cứu 2 ở đây…*")
    st.markdown("---")

    fig = px.bar(
        df.groupby("category")["value"].sum().reset_index(),
        x="category",
        y="value",
        color="category",
        title="Biểu đồ mẫu – Bar Chart",
        template="plotly_dark",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, width="stretch")


def render_question_3():
    st.header("📌 Câu hỏi nghiên cứu 3")
    st.markdown("> *Mô tả câu hỏi nghiên cứu 3 ở đây…*")
    st.markdown("---")

    fig = px.scatter(
        df,
        x="value",
        y="score",
        color="category",
        title="Biểu đồ mẫu – Scatter Plot",
        template="plotly_dark",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, width="stretch")


def render_question_4():
    st.header("📌 Câu hỏi nghiên cứu 4")
    st.markdown("> *Mô tả câu hỏi nghiên cứu 4 ở đây…*")
    st.markdown("---")

    fig = px.pie(
        df.groupby("category")["value"].sum().reset_index(),
        names="category",
        values="value",
        title="Biểu đồ mẫu – Pie Chart",
        template="plotly_dark",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, width="stretch")


def render_question_5():
    st.header("📌 Câu hỏi nghiên cứu 5")
    st.markdown("> *Mô tả câu hỏi nghiên cứu 5 ở đây…*")
    st.markdown("---")

    fig = px.histogram(
        df,
        x="score",
        nbins=20,
        color="category",
        title="Biểu đồ mẫu – Histogram",
        template="plotly_dark",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# ROUTER
# ============================================================
PAGES = {
    "📌 Câu hỏi 1": render_question_1,
    "📌 Câu hỏi 2": render_question_2,
    "📌 Câu hỏi 3": render_question_3,
    "📌 Câu hỏi 4": render_question_4,
    "📌 Câu hỏi 5": render_question_5,
}

PAGES[selected]()
