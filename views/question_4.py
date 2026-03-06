import streamlit as st
import plotly.express as px


def render_question_4(df):
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
