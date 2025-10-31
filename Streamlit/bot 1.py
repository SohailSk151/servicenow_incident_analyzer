import os
import requests
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory

# ----------------------------
# MCP server configuration
# ----------------------------
MCP_API_URL = "http://localhost:8080/incidents"  # Replace with your MCP URL if different

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

# ----------------------------
# Gemini chatbot initialization
# ----------------------------
def init_gemini_bot():
    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = "AIzaSyCVkLrB91gJfZVMLQocJowpKpZlMJ4RL_g"  # Replace with your key or use dotenv
    model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    history = ChatMessageHistory()
    return model, history

# ----------------------------
# Chatbot response function
# ----------------------------
def get_response(model, history, user_input):
    # If user asks about incidents or tickets
    if "incident" in user_input.lower() or "ticket" in user_input.lower():
        data = fetch_incidents_from_mcp()
        if "error" in data:
            response_text = f"Sorry, I couldn't fetch incident data: {data['error']}"
        else:
            # Summarize the incidents for Gemini
            incidents_summary = "\n".join(
                [
                    f"ID: {i['id']}, Short Description: {i['short_description']}, Details: {i.get('description', 'N/A')}"
                    for i in data[:5]  # Limit to first 5 incidents
                ]
            )
            # Create a prompt asking Gemini to provide recommendations
            prompt = (
                f"You are a ServiceNow expert AI assistant. "
                f"Given the following incidents, provide recommendations or steps to resolve each one:\n\n"
                f"{incidents_summary}\n\n"
                f"Provide clear, actionable recommendations."
            )
            # Add user input to history
            history.add_message(HumanMessage(content=user_input))
            # Generate recommendations using Gemini
            response = model.invoke([HumanMessage(content=prompt)])
            response_text = response.content
            # Add AI response to history
            history.add_message(AIMessage(content=response_text))
        return response_text

    # For other queries, use Gemini normally
    history.add_message(HumanMessage(content=user_input))
    response = model.invoke(history.messages)
    history.add_message(AIMessage(content=response.content))
    return response.content

# ----------------------------
# Main chat loop
# ----------------------------
if __name__ == "__main__":
    model, history = init_gemini_bot()
    print("Chatbot initialized! Type 'exit' or 'quit' to stop.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        reply = get_response(model, history, user_input)
        print("Bot:", reply)



# import os
# from langchain.chat_models import init_chat_model
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_community.chat_message_histories import ChatMessageHistory

# # Initialize Gemini model
# def init_gemini_bot():
#     if not os.environ.get("GOOGLE_API_KEY"):
#         os.environ["GOOGLE_API_KEY"] = "AIzaSyCVkLrB91gJfZVMLQocJowpKpZlMJ4RL_g"  # or use dotenv
#     model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
#     history = ChatMessageHistory()
#     return model, history


# def get_response(model, history, user_input):
#     # Add human message
#     history.add_message(HumanMessage(content=user_input))
    
#     # Generate AI response
#     response = model.invoke(history.messages)
    
#     # Add AI message
#     history.add_message(AIMessage(content=response.content))
    
#     return response.content



# import os
# import asyncio
# from langchain_mcp_adapters.client import MultiServerMCPClient
# from langchain.agents import create_agent
# from langchain.chat_models import init_chat_model

# # ✅ Initialize Gemini 2.5 model
# os.environ["GOOGLE_API_KEY"] = "AIzaSyCVkLrB91gJfZVMLQocJowpKpZlMJ4RL_g"
# gemini = init_chat_model("gemini-2.5-flash")

# # ✅ Configure ServiceNow MCP server
# client = MultiServerMCPClient({
#     "servicenow-mcp": {
#         "transport": "stdio",
#         "command": "C:/Users/Admin/Desktop/servicenow/servicenow_MCP/servicenow-mcp/.venv/Scripts/python.exe",
#         "args": [
#             "C:/Users/Admin/Desktop/servicenow/servicenow_MCP/servicenow-mcp/src/servicenow_mcp/cli.py"
#         ],
#         "env": {
#             "MCP_TOOL_PACKAGE": "full",
#             "SERVICENOW_INSTANCE_URL": "https://dev194650.service-now.com/",
#             "SERVICENOW_USERNAME": "admin",
#             "SERVICENOW_PASSWORD": "Ct5@T9eKfK*w"
#         }
#     }
# })

# # ✅ Run the agent
# async def main():
#     tools = await client.get_tools()
#     agent = create_agent(gemini, tools)

#     # Example queries to the ServiceNow MCP
#     incident_res = await agent.ainvoke({
#         "messages": [{"role": "user", "content": "Fetch all open incidents"}]
#     })

#     new_incident_res = await agent.ainvoke({
#         "messages": [{"role": "user", "content": "Create a new incident for a login issue"}]
#     })

#     print("Open Incidents:", incident_res)
#     print("New Incident:", new_incident_res)

# if __name__ == "__main__":
#     asyncio.run(main())
