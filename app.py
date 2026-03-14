import streamlit as st
import pandas as pd
import numpy as np

from views import (
    render_dashboard
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ---------- Global ---------- */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif !important;
    }
    [data-testid="stAppViewContainer"] {
        background: #0a0e17;
    }
    [data-testid="stHeader"] {
        background: rgba(10, 14, 23, 0.8);
        backdrop-filter: blur(10px);
    }

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
        padding-top: 1rem;
        max-width: 100% !important;
    }

    /* ---------- Metric cards ---------- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(0,212,170,0.1));
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        backdrop-filter: blur(10px);
    }
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
    }

    /* ---------- ECharts chart containers ---------- */
    iframe {
        background: #0d1117;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 0.5rem;
    }

    /* ---------- Markdown headers ---------- */
    h3 {
        color: #e5e7eb !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        padding-top: 0.5rem;
    }

    /* ---------- Horizontal rules ---------- */
    hr {
        border-color: rgba(255, 255, 255, 0.06) !important;
        margin: 0.5rem 0 !important;
    }

    /* ---------- Selectbox / Multiselect ---------- */
    [data-testid="stMultiSelect"], [data-testid="stSelectbox"] {
        background: rgba(17, 24, 39, 0.5);
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MAIN LAYOUT (No Sidebar)
# ============================================================


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
render_dashboard()
