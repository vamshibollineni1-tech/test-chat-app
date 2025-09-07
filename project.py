# pip install "streamlit[auth]" "google-cloud-aiplatform>=1.47.0" "google-cloud-bigquery" python-dotenv
import streamlit as st
import google.cloud.aiplatform as vertex_ai
# Correctly import the GenerativeModel class from its submodule
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from google.cloud import bigquery
import os
from dotenv import load_dotenv
import re
import subprocess
import shlex

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
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET")
BIGQUERY_ROLE_TABLE = os.getenv("BIGQUERY_ROLE_TABLE")


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

# Initialize BigQuery client
try:
    bq_client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
    st.sidebar.success("BigQuery client initialized.")
except Exception as e:
    st.error(f"Failed to initialize BigQuery client: {e}")
    st.stop()

# --- Command Handling Functions ---

def check_role_in_bigquery(role: str) -> bool:
    """Checks if a role exists in the authorized roles table in BigQuery."""
    if not BIGQUERY_DATASET or not BIGQUERY_ROLE_TABLE:
        st.warning("BigQuery dataset/table configuration is missing. Skipping role validation.")
        return False

    table_id = f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_ROLE_TABLE}"
    # Assuming the table has a single column named 'role_name'
    query = f"SELECT role_name FROM `{table_id}` WHERE role_name = @role"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("role", "STRING", role)]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job) # Wait for the job to complete
        return len(results) > 0
    except Exception as e:
        st.error(f"BigQuery query failed: {e}")
        return False

def apply_iam_policy(member: str, role: str) -> str:
    """Applies an IAM policy binding using the gcloud command."""
    # IMPORTANT: Using shlex.quote to prevent command injection vulnerabilities.
    command = (
        f"gcloud projects add-iam-policy-binding {shlex.quote(PROJECT_ID)} "
        f"--member={shlex.quote(member)} "
        f"--role={shlex.quote(role)}"
    )
    try:
        # Execute the command
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return f"Successfully applied role `{role}` to `{member}`.\n\n**Details:**\n```\n{result.stdout}\n```"
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to apply IAM policy. **Error**:\n```\n{e.stderr}\n```"
        return error_message

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
    st.session_state.chat = st.session_state.model.start_chat(history=[])

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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

    # --- Intent Detection and Command Handling ---
    # Simple regex to detect "add role <role> to <member>"
    match = re.match(r"add role\s+(.+?)\s+to\s+(.+)", prompt, re.IGNORECASE)

    if match:
        role_to_add = match.group(1).strip()
        member_to_add = match.group(2).strip()
        
        with st.chat_message("assistant"):
            with st.spinner(f"Validating role `{role_to_add}` in BigQuery..."):
                is_valid_role = check_role_in_bigquery(role_to_add)

            if is_valid_role:
                st.success(f"Role `{role_to_add}` is valid. Applying policy...")
                with st.spinner(f"Applying role to `{member_to_add}`..."):
                    result_message = apply_iam_policy(member_to_add, role_to_add)
                    st.markdown(result_message)
                    st.session_state.messages.append({"role": "assistant", "content": result_message})
            else:
                error_msg = f"Error: Role `{role_to_add}` is not a valid or approved role in the BigQuery table."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
    else:
        # --- Default Chat Behavior ---
        with st.chat_message("assistant"):
            try:
                def stream_to_text(stream):
                    for chunk in stream:
                        if chunk.text:
                            yield chunk.text

                stream = st.session_state.chat.send_message(
                    prompt,
                    stream=True,
                )
                
                response = st.write_stream(stream_to_text(stream))
                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                st.error(f"An error occurred while generating the response: {e}")
                st.rerun()
