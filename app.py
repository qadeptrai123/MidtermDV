import streamlit as st
import pandas as pd
import numpy as np

from views import (
    render_question_1,
    render_question_2,
    render_question_3,
    render_question_4,
    render_question_5,
)

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
# SAMPLE DATA (Replace with your real data)
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
# ROUTER
# ============================================================
PAGES = {
    "📌 Câu hỏi 1": render_question_1,
    "📌 Câu hỏi 2": render_question_2,
    "📌 Câu hỏi 3": render_question_3,
    "📌 Câu hỏi 4": render_question_4,
    "📌 Câu hỏi 5": render_question_5,
}

PAGES[selected](df)
