import streamlit as st

with st.chat_message("user"):
    st.markdown("**User 👤:** Hello!")

with st.chat_message("assistant"):
    st.markdown("**Assistant 🤖:** Hi there!")
