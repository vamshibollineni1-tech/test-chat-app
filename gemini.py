# pip install "streamlit[auth]" "google-cloud-aiplatform>=1.47.0" python-dotenv
import streamlit as st
import google.cloud.aiplatform as vertex_ai
# Correctly import the GenerativeModel class from its submodule
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
import os
from dotenv import load_dotenv

# --- Page and Authentication Setup ---

st.set_page_config(page_title="Vertex AI Chat App", layout="wide")
st.title("Vertex AI Chat App")

# Using Streamlit's built-in user authentication (for apps deployed on Streamlit Community Cloud)
# This handles the Google OAuth2.0 login flow for the end-user.
if not st.user.is_logged_in:
    st.info("Please log in to continue.")
    st.button("Log in with Google", on_click=st.login)  # uses [auth] in secrets.toml
    st.stop()

# Display user info and logout button
st.sidebar.write(f"Welcome, {st.user.name}!")
st.sidebar.button("Log out", on_click=st.logout, use_container_width=True)


# --- Configuration and Vertex AI Initialization ---

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
# Ensure these are set in your .env file or Streamlit secrets
SERVICE_ACCOUNT_KEY_FILE = os.getenv("SERVICE_ACCOUNT_KEY_FILE")
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash-001") # Default to a common model

# Authenticate to Google Cloud using the service account.
# This service account is what the Streamlit backend uses to call the Vertex AI API.
# It's separate from the end-user login.
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    # This is the key step to initialize the Vertex AI environment
    vertex_ai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)

except (FileNotFoundError, TypeError, Exception) as e:
    st.error(f"Configuration or authentication error: {e}")
    st.info("Please ensure SERVICE_ACCOUNT_KEY_FILE, PROJECT_ID, and LOCATION are set correctly in your environment.")
    st.stop()

# --- Chat Logic ---

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize the generative model from the vertex_ai library
# This ensures we use the Vertex AI endpoint and the correct authentication
if "model" not in st.session_state:
    # Use the directly imported GenerativeModel class
    st.session_state.model = GenerativeModel(MODEL_NAME)

# Initialize the chat object for conversational history
if "chat" not in st.session_state:
    # Reconstruct history from session state for the chat object
    history = []
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [Part.from_text(msg["content"])]})
    st.session_state.chat = st.session_state.model.start_chat(history=history)

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What can I help you with?"):
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate and display assistant's response
    with st.chat_message("assistant"):
        try:
            # Helper function to extract text from the streaming response
            def stream_to_text(stream):
                for chunk in stream:
                    # The actual text is in chunk.text
                    if chunk.text:
                        yield chunk.text

            # Send the prompt and get a streaming response
            stream = st.session_state.chat.send_message(
                prompt,
                stream=True,
            )
            
            # Use st.write_stream with the helper generator to render the text
            response = st.write_stream(stream_to_text(stream))
            
            # Add the assistant's full response to the session state
            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"An error occurred while generating the response: {e}")
            st.rerun()

