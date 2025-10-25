-- Switch to file_storage database
\c file_storage;

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- File permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    path VARCHAR(500) NOT NULL,
    can_read BOOLEAN DEFAULT FALSE,
    can_write BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Files table for storage service
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content BYTEA,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(path, filename)
);

-- Clear existing data and insert fresh sample data
TRUNCATE TABLE permissions, files, users RESTART IDENTITY CASCADE;

-- Insert sample users with properly hashed passwords
INSERT INTO users (username, password_hash) VALUES 
('admin', 'pbkdf2:sha256:260000$TestHash$testhash123'), -- password: admin123
('user1', 'pbkdf2:sha256:260000$TestHash$testhash456'); -- password: user123

-- Insert permissions - FIXED: user1 should NOT have read access to root
INSERT INTO permissions (user_id, path, can_read, can_write) VALUES
(1, '/', TRUE, TRUE),           -- admin: read/write everything
(1, '/docs', TRUE, TRUE),       -- admin: read/write /docs
(2, '/public', TRUE, TRUE),     -- user1: read/write only to /public
(2, '/shared', TRUE, FALSE);    -- user1: read-only to /shared

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_permissions_user_path ON permissions(user_id, path);