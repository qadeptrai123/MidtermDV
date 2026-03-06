import streamlit as st
import plotly.express as px


def render_question_3(df):
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
