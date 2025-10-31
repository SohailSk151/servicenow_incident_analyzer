CREATE DATABASE servicenow_db;
USE servicenow_db;

SELECT * FROM users;
TRUNCATE TABLE users;
DROP TABLE users;

SELECT * FROM admin;
TRUNCATE TABLE admin;
DROP TABLE admin;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pending_incidents (
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
);

SELECT * FROM pending_incidents;

CREATE TABLE incident_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    incident_number VARCHAR(50),
    action VARCHAR(50),
    performed_by VARCHAR(50),
    user_type VARCHAR(20),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

SELECT * FROM incident_history;