"""
Authentication and Authorization Backend API
Handles user/admin login, registration, and session management
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import mysql.connector
from mysql.connector import Error
import bcrypt
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="ServiceNow Auth API")
security = HTTPBearer()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'servicenow_db')
}

# Pydantic Models
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_type: str
    user_info: dict

class PendingIncident(BaseModel):
    short_description: str
    description: str
    priority: str
    urgency: str
    impact: str
    category: Optional[str] = None
    caller_id: Optional[str] = None

# Database Helper Functions
def get_db_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def create_tables():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            email VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(500) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Admin table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            email VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Pending incidents table (awaiting admin approval)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_incidents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            user_email VARCHAR(50) NOT NULL,
            short_description TEXT NOT NULL,
            description TEXT NOT NULL,
            priority VARCHAR(10),
            urgency VARCHAR(10),
            impact VARCHAR(10),
            category VARCHAR(100),
            caller_id VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Incident history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incident_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            incident_number VARCHAR(50),
            action VARCHAR(50),
            performed_by VARCHAR(50),
            user_type VARCHAR(20),
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# Password Hashing
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# JWT Functions
def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Authentication Dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user from token"""
    token = credentials.credentials
    payload = decode_token(token)
    return payload

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """Verify current user is admin"""
    if current_user.get("user_type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# API Endpoints

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    create_tables()

@app.get("/")
async def root():
    return {"message": "ServiceNow Auth API", "version": "1.0"}

# User Registration
@app.post("/api/auth/register/user")
async def register_user(user: UserRegister):
    """Register new user"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password and insert
        hashed_password = hash_password(user.password)
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (user.name, user.email, hashed_password)
        )
        conn.commit()
        
        return {"message": "User registered successfully", "email": user.email}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Admin Registration
@app.post("/api/auth/register/admin")
async def register_admin(admin: UserRegister):
    """Register new admin"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id FROM admin WHERE email = %s", (admin.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = hash_password(admin.password)
        cursor.execute(
            "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)",
            (admin.name, admin.email, hashed_password)
        )
        conn.commit()
        
        return {"message": "Admin registered successfully", "email": admin.email}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# User Login
@app.post("/api/auth/login/user", response_model=TokenResponse)
async def login_user(credentials: UserLogin):
    """User login"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (credentials.email,))
        user = cursor.fetchone()
        
        if not user or not verify_password(credentials.password, user['password']):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create token
        token_data = {
            "user_id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "user_type": "user"
        }
        access_token = create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "user",
            "user_info": {
                "id": user['id'],
                "name": user['name'],
                "email": user['email']
            }
        }
    
    finally:
        cursor.close()
        conn.close()

# Admin Login
@app.post("/api/auth/login/admin", response_model=TokenResponse)
async def login_admin(credentials: UserLogin):
    """Admin login"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM admin WHERE email = %s", (credentials.email,))
        admin = cursor.fetchone()
        
        if not admin or not verify_password(credentials.password, admin['password']):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        token_data = {
            "user_id": admin['id'],
            "email": admin['email'],
            "name": admin['name'],
            "user_type": "admin"
        }
        access_token = create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "admin",
            "user_info": {
                "id": admin['id'],
                "name": admin['name'],
                "email": admin['email']
            }
        }
    
    finally:
        cursor.close()
        conn.close()

# Verify Token
@app.get("/api/auth/verify")
async def verify_token_endpoint(current_user: dict = Depends(get_current_user)):
    """Verify if token is valid"""
    return {"valid": True, "user": current_user}

# Submit incident for approval (User)
@app.post("/api/user/incidents/submit")
async def submit_incident(
    incident: PendingIncident,
    current_user: dict = Depends(get_current_user)
):
    """User submits incident for admin approval"""
    if current_user.get("user_type") != "user":
        raise HTTPException(status_code=403, detail="Only users can submit incidents")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO pending_incidents 
            (user_id, user_email, short_description, description, priority, urgency, impact, category, caller_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            current_user['user_id'],
            current_user['email'],
            incident.short_description,
            incident.description,
            incident.priority,
            incident.urgency,
            incident.impact,
            incident.category,
            incident.caller_id or current_user['email']
        ))
        conn.commit()
        incident_id = cursor.lastrowid
        
        return {
            "message": "Incident submitted for approval",
            "pending_id": incident_id,
            "status": "pending"
        }
    
    finally:
        cursor.close()
        conn.close()

# Get pending incidents (Admin only)
@app.get("/api/admin/incidents/pending")
async def get_pending_incidents(current_admin: dict = Depends(get_current_admin)):
    """Admin views all pending incidents"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM pending_incidents 
            WHERE status = 'pending' 
            ORDER BY created_at DESC
        """)
        incidents = cursor.fetchall()
        return incidents
    
    finally:
        cursor.close()
        conn.close()

# Approve incident (Admin only)
@app.post("/api/admin/incidents/{incident_id}/approve")
async def approve_incident(
    incident_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """Admin approves incident and creates it in ServiceNow"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get pending incident
        cursor.execute("SELECT * FROM pending_incidents WHERE id = %s", (incident_id,))
        incident = cursor.fetchone()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        if incident['status'] != 'pending':
            raise HTTPException(status_code=400, detail="Incident already processed")
        
        # Update status to approved
        cursor.execute(
            "UPDATE pending_incidents SET status = 'approved' WHERE id = %s",
            (incident_id,)
        )
        conn.commit()
        
        return {
            "message": "Incident approved",
            "incident_id": incident_id,
            "incident_data": incident
        }
    
    finally:
        cursor.close()
        conn.close()

# Reject incident (Admin only)
@app.post("/api/admin/incidents/{incident_id}/reject")
async def reject_incident(
    incident_id: int,
    reason: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Admin rejects incident"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE pending_incidents SET status = 'rejected' WHERE id = %s",
            (incident_id,)
        )
        conn.commit()
        
        return {"message": "Incident rejected", "reason": reason}
    
    finally:
        cursor.close()
        conn.close()

# Get user's submitted incidents
@app.get("/api/user/incidents/my-submissions")
async def get_my_submissions(current_user: dict = Depends(get_current_user)):
    """User views their submitted incidents"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM pending_incidents 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (current_user['user_id'],))
        incidents = cursor.fetchall()
        return incidents
    
    finally:
        cursor.close()
        conn.close()

# Admin Dashboard Stats
@app.get("/api/admin/dashboard/stats")
async def get_dashboard_stats(current_admin: dict = Depends(get_current_admin)):
    """Get statistics for admin dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        stats = {}
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        stats['total_users'] = cursor.fetchone()['count']
        
        # Pending incidents
        cursor.execute("SELECT COUNT(*) as count FROM pending_incidents WHERE status = 'pending'")
        stats['pending_incidents'] = cursor.fetchone()['count']
        
        # Approved incidents
        cursor.execute("SELECT COUNT(*) as count FROM pending_incidents WHERE status = 'approved'")
        stats['approved_incidents'] = cursor.fetchone()['count']
        
        # Rejected incidents
        cursor.execute("SELECT COUNT(*) as count FROM pending_incidents WHERE status = 'rejected'")
        stats['rejected_incidents'] = cursor.fetchone()['count']
        
        # Recent activity
        cursor.execute("""
            SELECT * FROM pending_incidents 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        stats['recent_activity'] = cursor.fetchall()
        
        return stats
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)