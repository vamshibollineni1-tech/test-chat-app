import streamlit as st

st.title("Echo Bot")

# with st.chat_message("user"):
#     st.markdown("**User 👤:** Hello!")

# with st.chat_message("assistant"):
#     st.markdown("**Assistant 🤖:** Hi there!")

# prompt = st.chat_input("Say something")
# if prompt:
#     st.write(f"User has sent the following prompt: {prompt}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown("**User 👤:** prompt")
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
