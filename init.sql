-- Create database
CREATE DATABASE file_storage;

\c file_storage;

-- Users table for authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- File permissions table
CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    path VARCHAR(500) NOT NULL,
    can_read BOOLEAN DEFAULT FALSE,
    can_write BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Files table for storage service
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    path VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content BYTEA,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(path, filename)
);

-- Insert sample data
INSERT INTO users (username, password_hash) VALUES 
('admin', 'pbkdf2:sha256:260000$TestHash$testhash123'), -- password: admin123
('user1', 'pbkdf2:sha256:260000$TestHash$testhash456'); -- password: user123

INSERT INTO permissions (user_id, path, can_read, can_write) VALUES
(1, '/', TRUE, TRUE),
(1, '/docs', TRUE, TRUE),
(2, '/', TRUE, FALSE),
(2, '/public', TRUE, TRUE);

CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_permissions_user_path ON permissions(user_id, path);