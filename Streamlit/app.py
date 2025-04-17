import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
API_URL = os.getenv("API_URL", "http://localhost:5000")

# Set page configuration
st.set_page_config(
    page_title="DeepFetch AI",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
    }
    .chat-message.user {
        background-color: #f0f2f6;
    }
    .chat-message.bot {
        background-color: #e6f3ff;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .chat-message .message {
        flex-grow: 1;
    }
    .source-link {
        font-size: 0.8rem;
        color: #0068c9;
        margin-right: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# App header
st.title("DeepFetch AI")
st.markdown("Ask any question and get an AI response based on real-time web search results.")

# Function to send query to backend API
def send_query(query):
    try:
        response = requests.post(
            f"{API_URL}/api/query",
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error: Received status code {response.status_code}")
            return {"response": "Sorry, there was an error processing your request.", "sources": []}
    except Exception as e:
        st.error(f"Error communicating with the API: {e}")
        return {"response": "Sorry, there was an error connecting to the backend service.", "sources": []}

# Display chat history
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                st.markdown("#### Sources:")
                for idx, source in enumerate(message["sources"]):
                    st.markdown(f"{idx+1}. [{source}]({source})")

# Chat input
user_query = st.chat_input("Ask something...")

if user_query:
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_query)
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    # Display a spinner while waiting for the response
    with st.spinner("Searching the web and generating a response..."):
        # Send query to backend
        response_data = send_query(user_query)
        
        # Display assistant response
        with st.chat_message("assistant"):
            st.markdown(response_data["response"])
            if "sources" in response_data and response_data["sources"]:
                st.markdown("#### Sources:")
                for idx, source in enumerate(response_data["sources"]):
                    st.markdown(f"{idx+1}. [{source}]({source})")
        
        # Add assistant response to chat history
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response_data["response"],
            "sources": response_data.get("sources", [])
        })

# Sidebar with information
with st.sidebar:
    st.header("About")
    st.markdown("""
    This AI assistant searches the web in real-time to provide up-to-date information
    in response to your questions. The system:
    
    1. Searches the web for relevant content
    2. Processes and extracts meaningful information
    3. Uses Gemini-1.5-Flash to generate a response
    4. Provides source links for verification
    
    The assistant remembers your conversation context and can refer back to previous exchanges.
    """)
    
    st.header("Example Questions")
    st.markdown("""
    - What are the latest developments in quantum computing?
    - Tell me about Trum Tariffs?
    - Tell me about the latest stock price of CAMS?
    - What are the health benefits of meditation?
    """)