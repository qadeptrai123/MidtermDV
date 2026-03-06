import streamlit as st
import plotly.express as px


def render_question_1(df):
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
