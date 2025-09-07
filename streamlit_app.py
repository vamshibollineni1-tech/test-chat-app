# pip install "streamlit[auth]" Authlib>=1.3.2
import streamlit as st
from openai import OpenAI

st.title("TEST-CHAT-APP")

# Login gate: show a login button until the user signs in
if not st.user.is_logged_in:
    st.button("Log in with Google", on_click=st.login)  # uses [auth] in secrets.toml
    st.stop()

# Optional: show who is logged in and a logout button
st.write(f"Welcome, {st.user.name}!")
st.button("Log out", on_click=st.logout)

# Set OpenAI API key from Streamlit secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini-2024-07-18"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})