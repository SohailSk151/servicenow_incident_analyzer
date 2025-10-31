import os
import requests
import streamlit as st
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory

# ------------------------------
# 1️⃣ Setup Gemini API Key
# ------------------------------
if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = "AIzaSyCVkLrB91gJfZVMLQocJowpKpZlMJ4RL_g"  # 🔑 Replace with your Gemini API key

# ------------------------------
# 2️⃣ MCP Server configuration
# ------------------------------
MCP_API_URL = "http://localhost:8080/incidents"  # Replace with your MCP FastAPI URL

def fetch_incidents_from_mcp():
    """
    Fetch incidents from MCP server.
    """
    try:
        response = requests.get(MCP_API_URL)
        if response.status_code == 200:
            return response.json()  # Returns list of incidents
        else:
            return {"error": f"Failed to fetch incidents: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ------------------------------
# 3️⃣ Initialize Streamlit page
# ------------------------------
st.set_page_config(page_title="ServiceNow AI Assistant", page_icon="🤖", layout="centered")
st.title("🤖 ServiceNow Incident Analyzer")
st.write("Chat with an AI assistant trained to help you analyze ServiceNow incidents!")

# ------------------------------
# 4️⃣ Initialize session state
# ------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = ChatMessageHistory()
if "model" not in st.session_state:
    st.session_state.model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

# ------------------------------
# 5️⃣ Helper function to get model response
# ------------------------------
def get_response(model, history, user_input):
    # If user asks about incidents/tickets
    if "incident" in user_input.lower() or "ticket" in user_input.lower():
        data = fetch_incidents_from_mcp()
        if "error" in data:
            response_text = f"Sorry, I couldn't fetch incident data: {data['error']}"
        else:
            # Debug: Print first incident to see structure
            if data and len(data) > 0:
                st.write("DEBUG - First incident structure:", data[0].keys())
            
            # Summarize incidents for Gemini
            incidents_summary = "\n".join(
                [
                    f"Number: {i.get('number', 'N/A')}, "
                    f"Short Description: {i.get('short_description', 'N/A')}, "
                    f"State: {i.get('state', 'N/A')}, "
                    f"Priority: {i.get('priority', 'N/A')}, "
                    f"Category: {i.get('category', 'N/A')}, "
                    f"Description: {i.get('description', 'N/A')[:200] if i.get('description') else 'N/A'}"
                    for i in data[:5]  # Limit to first 5 incidents
                ]
            )
            
            prompt = (
                f"You are a ServiceNow expert AI assistant. "
                f"Given the following incidents, provide recommendations or steps to resolve each one:\n\n"
                f"{incidents_summary}\n\n"
                f"Provide clear, actionable recommendations for each incident."
            )
            # Add human message to history
            history.add_message(HumanMessage(content=user_input))
            # Generate recommendations using Gemini
            response = model.invoke([HumanMessage(content=prompt)])
            response_text = response.content
            # Add AI message to history
            history.add_message(AIMessage(content=response_text))
        return response_text

    # For other queries, fallback to normal Gemini response
    history.add_message(HumanMessage(content=user_input))
    response = model.invoke(history.messages)
    history.add_message(AIMessage(content=response.content))
    return response.content

# ------------------------------
# 6️⃣ Display chat history
# ------------------------------
for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["content"])

# ------------------------------
# 7️⃣ Chat input
# ------------------------------
user_input = st.chat_input(
    "Ask about a ServiceNow incident or any issue...",
    key="main_chat_input"  # Unique key
)

# ------------------------------
# 8️⃣ Handle new message
# ------------------------------
if user_input:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response
    with st.spinner("Analyzing with Gemini..."):
        response = get_response(st.session_state.model, st.session_state.history, user_input)

    # Display bot response
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)