import os
import requests
import streamlit as st
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory
import pandas as pd
import plotly.express as px

# API URLs
AUTH_API_URL = "http://localhost:8000/api"
MCP_API_URL = "http://localhost:8080"

# Gemini API Key
if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = "AIzaSyCVkLrB91gJfZVMLQocJowpKpZlMJ4RL_g"

# Page Config
st.set_page_config(
    page_title="ServiceNow Platform",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_type" not in st.session_state:
    st.session_state.user_type = None
if "token" not in st.session_state:
    st.session_state.token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = ChatMessageHistory()
if "model" not in st.session_state:
    st.session_state.model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

# API Helper Functions
def api_request(method, endpoint, data=None, use_auth=False):
    """Make API request"""
    headers = {}
    if use_auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    try:
        if method == "GET":
            response = requests.get(endpoint, headers=headers)
        elif method == "POST":
            response = requests.post(endpoint, json=data, headers=headers)
        elif method == "PATCH":
            response = requests.patch(endpoint, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(endpoint, headers=headers)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def logout():
    """Logout user"""
    st.session_state.authenticated = False
    st.session_state.user_type = None
    st.session_state.token = None
    st.session_state.user_info = {}
    st.session_state.messages = []
    st.rerun()

# ==================== LOGIN PAGE ====================
def show_login_page():
    st.title("🎫 ServiceNow Platform")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 👤 User Login")
        user_email = st.text_input("Email", key="user_login_email")
        user_password = st.text_input("Password", type="password", key="user_login_password")
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔐 Login", use_container_width=True, key="user_login_btn"):
                if user_email and user_password:
                    result = api_request("POST", f"{AUTH_API_URL}/auth/login/user", {
                        "email": user_email,
                        "password": user_password
                    })
                    
                    if "error" in result:
                        st.error(f"❌ Invalid credentials")
                    else:
                        st.session_state.authenticated = True
                        st.session_state.user_type = "user"
                        st.session_state.token = result['access_token']
                        st.session_state.user_info = result['user_info']
                        st.success("✅ Login successful!")
                        st.rerun()
                else:
                    st.error("Please enter email and password")
        
        with col_b:
            with st.popover("📝 Register"):
                reg_name = st.text_input("Name", key="reg_user_name")
                reg_email = st.text_input("Email", key="reg_user_email")
                reg_password = st.text_input("Password", type="password", key="reg_user_password")
                
                if st.button("Register", use_container_width=True):
                    if reg_name and reg_email and reg_password:
                        result = api_request("POST", f"{AUTH_API_URL}/auth/register/user", {
                            "name": reg_name,
                            "email": reg_email,
                            "password": reg_password
                        })
                        
                        if "error" in result:
                            st.error(f"❌ {result['error']}")
                        else:
                            st.success("✅ Registered! Please login.")
                    else:
                        st.error("All fields required")
    
    with col2:
        st.markdown("### 👑 Admin Login")
        admin_email = st.text_input("Email", key="admin_login_email")
        admin_password = st.text_input("Password", type="password", key="admin_login_password")
        
        if st.button("🔐 Login as Admin", use_container_width=True, key="admin_login_btn"):
            if admin_email and admin_password:
                result = api_request("POST", f"{AUTH_API_URL}/auth/login/admin", {
                    "email": admin_email,
                    "password": admin_password
                })
                
                if "error" in result:
                    st.error(f"❌ Invalid credentials")
                else:
                    st.session_state.authenticated = True
                    st.session_state.user_type = "admin"
                    st.session_state.token = result['access_token']
                    st.session_state.user_info = result['user_info']
                    st.success("✅ Login successful!")
                    st.rerun()
            else:
                st.error("Please enter email and password")

# ==================== USER DASHBOARD ====================
def show_user_dashboard():
    # Sidebar
    with st.sidebar:
        st.title(f"👤 {st.session_state.user_info['name']}")
        st.write(f"📧 {st.session_state.user_info['email']}")
        st.write(f"**Role:** User")
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
        
        st.markdown("---")
        
        menu = st.radio(
            "Navigation",
            ["💬 AI Assistant", "➕ Submit Incident", "📤 My Submissions"]
        )
    
    # Main Content
    if menu == "💬 AI Assistant":
        show_ai_assistant()
    elif menu == "➕ Submit Incident":
        show_submit_incident()
    elif menu == "📤 My Submissions":
        show_my_submissions()

def show_ai_assistant():
    st.title("💬 AI Assistant")
    st.write("Ask me about ServiceNow incidents - I can help you find P1 tickets, analyze issues, and more!")
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])
    
    # Chat input
    if user_input := st.chat_input("Ask about incidents, tickets, or any ServiceNow question..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate response
        with st.spinner("Analyzing..."):
            # Check if asking about incidents
            if any(word in user_input.lower() for word in ["incident", "ticket", "p1", "p2", "p3", "priority", "show"]):
                # Extract priority filter
                priority = None
                if "p1" in user_input.lower() or "priority 1" in user_input.lower():
                    priority = "1"
                elif "p2" in user_input.lower() or "priority 2" in user_input.lower():
                    priority = "2"
                elif "p3" in user_input.lower() or "priority 3" in user_input.lower():
                    priority = "3"
                
                # Fetch incidents from MCP
                endpoint = f"{MCP_API_URL}/incidents?limit=10"
                if priority:
                    endpoint += f"&priority={priority}"
                
                data = api_request("GET", endpoint)
                
                if "error" in data:
                    response_text = f"Sorry, couldn't fetch incidents: {data['error']}"
                else:
                    # Prepare incident summary
                    incidents_summary = "\n".join([
                        f"- Ticket {i.get('number', 'N/A')}: {i.get('short_description', 'N/A')} "
                        f"(Priority: {i.get('priority', 'N/A')}, State: {i.get('state', 'N/A')})"
                        for i in data[:10]
                    ])
                    
                    prompt = f"""You are a ServiceNow expert AI assistant. 
                    
Here are the current incidents:
{incidents_summary}

User question: {user_input}

Provide helpful, actionable insights and recommendations."""
                    
                    st.session_state.history.add_message(HumanMessage(content=user_input))
                    response = st.session_state.model.invoke([HumanMessage(content=prompt)])
                    response_text = response.content
                    st.session_state.history.add_message(AIMessage(content=response_text))
            else:
                # General query
                st.session_state.history.add_message(HumanMessage(content=user_input))
                response = st.session_state.model.invoke(st.session_state.history.messages)
                response_text = response.content
                st.session_state.history.add_message(AIMessage(content=response_text))
        
        # Display assistant response
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        with st.chat_message("assistant"):
            st.markdown(response_text)

def show_submit_incident():
    st.title("➕ Submit New Incident")
    st.info("ℹ️ Your incident will be reviewed by an administrator before being created in ServiceNow")
    
    with st.form("submit_incident_form"):
        short_description = st.text_input("Short Description*", placeholder="Brief summary of the issue")
        description = st.text_area("Detailed Description*", placeholder="Provide detailed information about the incident", height=150)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            priority = st.selectbox("Priority*", ["1 - Critical", "2 - High", "3 - Moderate", "4 - Low", "5 - Planning"])
        with col2:
            urgency = st.selectbox("Urgency*", ["1 - High", "2 - Medium", "3 - Low"])
        with col3:
            impact = st.selectbox("Impact*", ["1 - High", "2 - Medium", "3 - Low"])
        
        category = st.text_input("Category (Optional)", placeholder="e.g., Hardware, Software, Network")
        
        submitted = st.form_submit_button("📤 Submit for Approval", use_container_width=True, type="primary")
        
        if submitted:
            if not short_description or not description:
                st.error("❌ Short Description and Detailed Description are required!")
            else:
                data = {
                    "short_description": short_description,
                    "description": description,
                    "priority": priority.split(" - ")[0],
                    "urgency": urgency.split(" - ")[0],
                    "impact": impact.split(" - ")[0],
                    "category": category
                }
                
                result = api_request("POST", f"{AUTH_API_URL}/user/incidents/submit", data, use_auth=True)
                
                if "error" in result:
                    st.error(f"❌ {result['error']}")
                else:
                    st.success("✅ Incident submitted successfully! An administrator will review it shortly.")
                    st.balloons()

def show_my_submissions():
    st.title("📤 My Submissions")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    with st.spinner("Loading your submissions..."):
        data = api_request("GET", f"{AUTH_API_URL}/user/incidents/my-submissions", use_auth=True)
    
    if "error" in data:
        st.error(f"❌ {data['error']}")
    else:
        if not data:
            st.info("📭 No submissions yet. Submit your first incident to get started!")
        else:
            st.success(f"📋 You have {len(data)} submission(s)")
            
            # Status filter
            status_filter = st.selectbox("Filter by Status", ["All", "Pending", "Approved", "Rejected"])
            
            for incident in data:
                status = incident.get('status', 'unknown').lower()
                
                # Apply filter
                if status_filter != "All" and status != status_filter.lower():
                    continue
                
                status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
                status_color = {"pending": "orange", "approved": "green", "rejected": "red"}
                
                with st.expander(f"{status_emoji.get(status, '❓')} {incident.get('short_description', 'N/A')}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Status:** :{status_color.get(status, 'gray')}[{status.upper()}]")
                        st.write(f"**Priority:** P{incident.get('priority', 'N/A')}")
                    with col2:
                        st.write(f"**Category:** {incident.get('category', 'N/A')}")
                        st.write(f"**Urgency:** {incident.get('urgency', 'N/A')}")
                    with col3:
                        st.write(f"**Impact:** {incident.get('impact', 'N/A')}")
                        st.write(f"**Submitted:** {incident.get('created_at', 'N/A')[:19]}")
                    
                    st.markdown("---")
                    st.write("**Description:**")
                    st.write(incident.get('description', 'N/A'))

# ==================== ADMIN DASHBOARD ====================
def show_admin_dashboard():
    # Sidebar
    with st.sidebar:
        st.title(f"👑 {st.session_state.user_info['name']}")
        st.write(f"📧 {st.session_state.user_info['email']}")
        st.write(f"**Role:** Administrator")
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
        
        st.markdown("---")
        
        menu = st.radio(
            "Admin Panel",
            ["📊 Dashboard", "⏳ Pending Approvals", "📋 View Incidents", 
             "✏️ Manage Incidents", "👥 Add Admin"]
        )
    
    # Main Content
    if menu == "📊 Dashboard":
        show_admin_dashboard_stats()
    elif menu == "⏳ Pending Approvals":
        show_pending_approvals()
    elif menu == "📋 View Incidents":
        show_view_incidents_admin()
    elif menu == "✏️ Manage Incidents":
        show_manage_incidents()
    elif menu == "👥 Add Admin":
        show_add_admin()

def show_admin_dashboard_stats():
    st.title("📊 Admin Dashboard")
    
    with st.spinner("Loading statistics..."):
        stats = api_request("GET", f"{AUTH_API_URL}/admin/dashboard/stats", use_auth=True)
    
    if "error" in stats:
        st.error(f"❌ {stats['error']}")
    else:
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Users", stats.get('total_users', 0))
        with col2:
            pending = stats.get('pending_incidents', 0)
            st.metric("⏳ Pending", pending, delta="Review needed" if pending > 0 else None)
        with col3:
            st.metric("✅ Approved", stats.get('approved_incidents', 0))
        with col4:
            st.metric("❌ Rejected", stats.get('rejected_incidents', 0))
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Submission Status")
            status_data = pd.DataFrame({
                'Status': ['Pending', 'Approved', 'Rejected'],
                'Count': [
                    stats.get('pending_incidents', 0),
                    stats.get('approved_incidents', 0),
                    stats.get('rejected_incidents', 0)
                ]
            })
            fig = px.pie(status_data, values='Count', names='Status', 
                        color='Status',
                        color_discrete_map={'Pending':'#FFA500', 'Approved':'#00CC00', 'Rejected':'#FF4444'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Recent Activity")
            recent = stats.get('recent_activity', [])
            if recent:
                for item in recent[:5]:
                    status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
                    st.write(f"{status_emoji.get(item.get('status'), '❓')} {item.get('short_description', 'N/A')[:50]}...")
            else:
                st.info("No recent activity")

def show_pending_approvals():
    st.title("⏳ Pending Approvals")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    with st.spinner("Loading pending incidents..."):
        data = api_request("GET", f"{AUTH_API_URL}/admin/incidents/pending", use_auth=True)
    
    if "error" in data:
        st.error(f"❌ {data['error']}")
    else:
        if not data:
            st.success("✅ No pending approvals")
        else:
            st.warning(f"⚠️ {len(data)} incident(s) awaiting your approval")
            
            for incident in data:
                with st.expander(f"🎫 {incident.get('short_description', 'N/A')} - {incident.get('user_email', 'N/A')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Submitted by:**", incident.get('user_email', 'N/A'))
                        st.write("**Priority:**", f"P{incident.get('priority', 'N/A')}")
                        st.write("**Urgency:**", incident.get('urgency', 'N/A'))
                    with col2:
                        st.write("**Impact:**", incident.get('impact', 'N/A'))
                        st.write("**Category:**", incident.get('category', 'N/A'))
                        st.write("**Submitted:**", incident.get('created_at', 'N/A')[:19])
                    
                    st.markdown("**Description:**")
                    st.write(incident.get('description', 'N/A'))
                    
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Approve & Create in ServiceNow", key=f"approve_{incident['id']}", use_container_width=True, type="primary"):
                            # Approve in database
                            result = api_request("POST", f"{AUTH_API_URL}/admin/incidents/{incident['id']}/approve", use_auth=True)
                            
                            if "error" not in result:
                                # Create in ServiceNow
                                snow_data = {
                                    "short_description": incident['short_description'],
                                    "description": incident['description'],
                                    "priority": incident['priority'],
                                    "urgency": incident['urgency'],
                                    "impact": incident['impact'],
                                    "category": incident.get('category')
                                }
                                
                                snow_result = api_request("POST", f"{MCP_API_URL}/incidents", snow_data)
                                
                                if "error" in snow_result:
                                    st.error(f"❌ Approved but failed in ServiceNow: {snow_result['error']}")
                                else:
                                    st.success("✅ Approved and created in ServiceNow!")
                                    st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                    
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{incident['id']}", use_container_width=True):
                            result = api_request("POST", f"{AUTH_API_URL}/admin/incidents/{incident['id']}/reject", 
                                               {"reason": "Rejected by admin"}, use_auth=True)
                            
                            if "error" not in result:
                                st.success("✅ Incident rejected")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")

def show_view_incidents_admin():
    st.title("📋 View ServiceNow Incidents")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        limit = st.number_input("Limit", min_value=1, max_value=100, value=20)
    with col2:
        priority_filter = st.selectbox("Priority", ["All", "1 - Critical", "2 - High", "3 - Moderate", "4 - Low", "5 - Planning"])
    with col3:
        state_filter = st.text_input("State Filter", placeholder="e.g., 1, 2, 6")
    with col4:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Build query
    endpoint = f"{MCP_API_URL}/incidents?limit={limit}"
    if priority_filter != "All":
        priority = priority_filter.split(" - ")[0]
        endpoint += f"&priority={priority}"
    if state_filter:
        endpoint += f"&sysparm_query=state={state_filter}"
    
    with st.spinner("Fetching incidents..."):
        data = api_request("GET", endpoint)
    
    if "error" in data:
        st.error(f"❌ {data['error']}")
    else:
        st.success(f"✅ Found {len(data)} incidents")
        
        if data:
            df = pd.DataFrame(data)
            display_cols = ['number', 'short_description', 'state', 'priority', 'category', 'opened_at']
            available_cols = [col for col in display_cols if col in df.columns]
            st.dataframe(df[available_cols], use_container_width=True, height=400)

def show_manage_incidents():
    st.title("✏️ Manage Incidents")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Update", "Delete", "Assign", "Resolve"])
    
    with tab1:
        st.subheader("Update Incident")
        incident_id = st.text_input("Incident Number or sys_id", key="update_id")
        
        if incident_id:
            current = api_request("GET", f"{MCP_API_URL}/incidents/{incident_id}")
            
            if "error" not in current:
                with st.form("update_form"):
                    short_desc = st.text_input("Short Description", value=current.get('short_description', ''))
                    state = st.selectbox("State", ["1 - New", "2 - In Progress", "6 - Resolved", "7 - Closed"])
                    priority = st.selectbox("Priority", ["1", "2", "3", "4", "5"])
                    work_notes = st.text_area("Work Notes")
                    
                    if st.form_submit_button("Update", use_container_width=True):
                        data = {
                            "short_description": short_desc,
                            "state": state.split(" - ")[0],
                            "priority": priority
                        }
                        if work_notes:
                            data["work_notes"] = work_notes
                        
                        result = api_request("PATCH", f"{MCP_API_URL}/incidents/{incident_id}", data)
                        if "error" not in result:
                            st.success("✅ Updated!")
                        else:
                            st.error(f"❌ {result['error']}")
    
    with tab2:
        st.subheader("Delete Incident")
        st.warning("⚠️ This action cannot be undone!")
        del_id = st.text_input("Incident Number or sys_id", key="delete_id")
        if st.button("🗑️ Delete", type="primary"):
            if del_id:
                result = api_request("DELETE", f"{MCP_API_URL}/incidents/{del_id}")
                if "error" not in result:
                    st.success("✅ Deleted!")
                else:
                    st.error(f"❌ {result['error']}")
    
    with tab3:
        st.subheader("Assign Incident")
        assign_id = st.text_input("Incident Number", key="assign_id")
        user_id = st.text_input("Assign to (sys_id or username)")
        if st.button("Assign"):
            if assign_id and user_id:
                result = api_request("POST", f"{MCP_API_URL}/incidents/{assign_id}/assign", {"assigned_to": user_id})
                if "error" not in result:
                    st.success("✅ Assigned!")
                else:
                    st.error(f"❌ {result['error']}")
    
    with tab4:
        st.subheader("Resolve Incident")
        resolve_id = st.text_input("Incident Number", key="resolve_id")
        resolution = st.text_area("Resolution Notes")
        if st.button("✅ Resolve"):
            if resolve_id and resolution:
                result = api_request("POST", f"{MCP_API_URL}/incidents/{resolve_id}/resolve", {"close_notes": resolution})
                if "error" not in result:
                    st.success("✅ Resolved!")
                else:
                    st.error(f"❌ {result['error']}")

def show_add_admin():
    st.title("👥 Add New Administrator")
    st.info("ℹ️ Only existing administrators can add new admins")
    
    with st.form("add_admin_form"):
        admin_name = st.text_input("Name*")
        admin_email = st.text_input("Email*")
        admin_password = st.text_input("Password*", type="password")
        
        submitted = st.form_submit_button("➕ Add Administrator", use_container_width=True, type="primary")
        
        if submitted:
            if admin_name and admin_email and admin_password:
                result = api_request("POST", f"{AUTH_API_URL}/auth/register/admin", {
                    "name": admin_name,
                    "email": admin_email,
                    "password": admin_password
                })
                
                if "error" in result:
                    st.error(f"❌ {result['error']}")
                else:
                    st.success(f"✅ Administrator {admin_name} added successfully!")
                    st.balloons()
            else:
                st.error("❌ All fields are required!")

# ==================== MAIN APP ====================
def main():
    if not st.session_state.authenticated:
        show_login_page()
    else:
        if st.session_state.user_type == "user":
            show_user_dashboard()
        elif st.session_state.user_type == "admin":
            show_admin_dashboard()

if __name__ == "__main__":
    main()