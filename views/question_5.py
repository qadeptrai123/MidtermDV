import streamlit as st
import plotly.express as px


def render_question_5(df):
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
    st.plotly_chart(fig, width="stretch")
