import streamlit as st
import plotly.express as px


def render_question_2(df):
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
