# 🎫 ServiceNow MCP Platform

A comprehensive ServiceNow integration platform featuring an AI-powered incident management system with Model Context Protocol (MCP) server, authentication backend, and modern Streamlit UI.

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Usage Guide](#usage-guide)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## ✨ Features

### 🤖 AI-Powered Assistant
- **Gemini 2.5 Flash Integration**: Advanced AI chatbot for incident analysis
- **Intelligent Recommendations**: Get actionable insights for incident resolution
- **Natural Language Queries**: Ask questions about incidents in plain English

### 🔐 Authentication & Authorization
- **Dual Role System**: Separate user and admin portals
- **JWT-based Authentication**: Secure token-based session management
- **Password Hashing**: bcrypt encryption for secure password storage

### 📊 User Portal
- **Submit Incidents**: Create and submit incidents for admin approval
- **Track Submissions**: Monitor status of submitted incidents (Pending/Approved/Rejected)
- **AI Assistant**: Interactive chatbot for incident queries

### 👑 Admin Portal
- **Dashboard Analytics**: Visual insights with pie charts and statistics
- **Approval Workflow**: Review and approve/reject pending incidents
- **Full CRUD Operations**: Create, Read, Update, Delete incidents in ServiceNow
- **Incident Management**: Assign, resolve, and update incidents
- **User Management**: Add new administrators

### 🔌 MCP Server (Model Context Protocol)
- **RESTful API**: Full CRUD operations for ServiceNow incidents
- **SSE Transport**: Server-Sent Events for real-time communication
- **Tool Packages**: Configurable tool sets via environment variables
- **Health Monitoring**: Built-in health check endpoints

## 🏗️ Architecture

```
┌─────────────────┐
│  Streamlit UI   │  (Port 8501)
│   (Frontend)    │
└────────┬────────┘
         │
         ├──────────────┬─────────────────┐
         │              │                 │
         ▼              ▼                 ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────┐
│   Auth API     │ │  MCP Server  │ │ Gemini 2.5   │
│  (Port 8000)   │ │ (Port 8080)  │ │    Flash     │
└────────┬───────┘ └──────┬───────┘ └──────────────┘
         │                │
         ▼                ▼
┌────────────────┐ ┌──────────────┐
│  MySQL DB      │ │  ServiceNow  │
│                │ │   Instance   │
└────────────────┘ └──────────────┘
```

## 📦 Prerequisites

- **Python**: 3.8 or higher
- **MySQL**: 5.7 or higher
- **ServiceNow Instance**: Developer instance or production instance
- **Google API Key**: For Gemini AI model access
- **Git**: For cloning the repository

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/servicenow-mcp-platform.git
cd servicenow-mcp-platform
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup MySQL Database

```sql
CREATE DATABASE servicenow_db;
```

The tables will be created automatically when you first run the Auth API.

## ⚙️ Configuration

### 1. Environment Variables

Create a `.env` file in the `servicenow-mcp/` directory:

```env
# ServiceNow Configuration
SERVICENOW_INSTANCE_URL=https://dev194650.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your_password

# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_db_password
DB_NAME=servicenow_db

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this

# Google AI Configuration
GOOGLE_API_KEY=your_google_api_key

# MCP Tool Package (options: full, basic, minimal, none)
MCP_TOOL_PACKAGE=full
```

### 2. Update Streamlit Configuration

In `Streamlit/app.py`, update the API key (or use environment variable):

```python
os.environ["GOOGLE_API_KEY"] = "your_google_api_key"
```

### 3. Tool Package Configuration

Edit `config/tool_packages.yaml` to customize available MCP tools:

```yaml
full:
  - list_incidents
  - create_incident
  - update_incident
  - delete_incident
  - get_incident
  - assign_incident
  - resolve_incident

basic:
  - list_incidents
  - get_incident
  - create_incident
```

## 🏃 Running the Application

### Start All Services

You need to run three separate services:

#### 1. Start Auth API (Terminal 1)

```bash
cd servicenow-mcp/src/servicenow_mcp
python auth_api.py
```

**Runs on**: `http://localhost:8000`

#### 2. Start MCP Server (Terminal 2)

```bash
cd servicenow-mcp/src/servicenow_mcp
python server_sse.py --host 0.0.0.0 --port 8080
```

**Runs on**: `http://localhost:8080`

#### 3. Start Streamlit UI (Terminal 3)

```bash
cd Streamlit
streamlit run app.py
```

**Runs on**: `http://localhost:8501`

### Verify Services

Check if all services are running:

- **Auth API**: `http://localhost:8000/`
- **MCP Health**: `http://localhost:8080/health`
- **Streamlit UI**: `http://localhost:8501`

## 📚 API Documentation

### Auth API Endpoints

#### User Authentication
- `POST /api/auth/register/user` - Register new user
- `POST /api/auth/login/user` - User login
- `GET /api/auth/verify` - Verify JWT token

#### Admin Authentication
- `POST /api/auth/register/admin` - Register new admin
- `POST /api/auth/login/admin` - Admin login

#### User Operations
- `POST /api/user/incidents/submit` - Submit incident for approval
- `GET /api/user/incidents/my-submissions` - Get user's submissions

#### Admin Operations
- `GET /api/admin/incidents/pending` - Get pending approvals
- `POST /api/admin/incidents/{id}/approve` - Approve incident
- `POST /api/admin/incidents/{id}/reject` - Reject incident
- `GET /api/admin/dashboard/stats` - Get dashboard statistics

### MCP Server Endpoints

#### Incident Management
- `GET /incidents` - List incidents
  - Query params: `limit`, `priority`, `sysparm_query`
- `POST /incidents` - Create incident
- `GET /incidents/{id}` - Get specific incident
- `PATCH /incidents/{id}` - Update incident
- `DELETE /incidents/{id}` - Delete incident

#### Additional Operations
- `POST /incidents/{id}/assign` - Assign to user
- `POST /incidents/{id}/resolve` - Resolve incident
- `GET /health` - Health check

### Example API Calls

#### Create Incident
```bash
curl -X POST http://localhost:8080/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "short_description": "Server down",
    "description": "Production server is not responding",
    "priority": "1",
    "urgency": "1",
    "impact": "1"
  }'
```

#### List P1 Incidents
```bash
curl "http://localhost:8080/incidents?priority=1&limit=10"
```

## 📖 Usage Guide

### For Users

1. **Register Account**
   - Open the Streamlit UI
   - Click "Register" under User Login
   - Fill in name, email, and password

2. **Login**
   - Enter credentials and click "Login"

3. **Submit Incident**
   - Navigate to "Submit Incident"
   - Fill in incident details
   - Click "Submit for Approval"

4. **Use AI Assistant**
   - Go to "AI Assistant"
   - Ask questions like:
     - "Show me all P1 tickets"
     - "What incidents need attention?"
     - "Analyze recent issues"

5. **Track Submissions**
   - Check "My Submissions" to see status
   - Filter by Pending/Approved/Rejected

### For Administrators

1. **Login as Admin**
   - Use admin credentials to login

2. **View Dashboard**
   - See statistics and charts
   - Monitor pending approvals

3. **Review Pending Incidents**
   - Navigate to "Pending Approvals"
   - Review incident details
   - Approve (creates in ServiceNow) or Reject

4. **Manage Incidents**
   - View all ServiceNow incidents
   - Update, delete, assign, or resolve
   - Filter by priority and state

5. **Add Administrators**
   - Go to "Add Admin"
   - Create new admin accounts

## 📁 Project Structure

```
servicenow-mcp-platform/
│
├── Streamlit/
│   ├── app.py                    # Main Streamlit application
│   └── bot 1.py                  # Chatbot implementation
│
├── servicenow-mcp/
│   ├── src/
│   │   └── servicenow_mcp/
│   │       ├── auth_api.py       # Authentication API
│   │       ├── server.py         # Core MCP server
│   │       ├── server_sse.py     # SSE MCP server with REST API
│   │       ├── auth/
│   │       │   └── auth_manager.py
│   │       ├── tools/
│   │       │   └── knowledge_base.py
│   │       └── utils/
│   │           ├── config.py
│   │           └── tool_utils.py
│   │
│   ├── config/
│   │   └── tool_packages.yaml    # Tool package definitions
│   │
│   └── .env                      # Environment variables
│
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── CONTRIBUTING.md               # Contribution guidelines
└── LICENSE                       # MIT License
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Database Connection Error
```
Error: Database connection failed
```
**Solution**: 
- Verify MySQL is running
- Check DB credentials in `.env`
- Ensure database `servicenow_db` exists

#### 2. ServiceNow API Error
```
Error: ServiceNow API returned 401
```
**Solution**:
- Verify ServiceNow credentials
- Check instance URL format
- Ensure user has necessary permissions

#### 3. Gemini API Error
```
Error: Invalid API key
```
**Solution**:
- Verify Google API key is valid
- Check API key has Gemini access enabled
- Update key in `.env` and `app.py`

#### 4. Port Already in Use
```
Error: Address already in use
```
**Solution**:
```bash
# Find process using the port
lsof -i :8000  # or :8080, :8501

# Kill the process
kill -9 <PID>
```

#### 5. JWT Token Expired
```
Error: Token has expired
```
**Solution**: Re-login to get a new token

### Logs

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```


**Made with ❤️ for better incident management**
