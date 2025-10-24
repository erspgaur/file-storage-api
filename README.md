# File Storage API with Authentication

A Docker-based file storage system with HTTP API, PostgreSQL backend, and separate authentication service.

## Architecture

- **Storage Service**: Main file storage API (port 5000)
- **Auth Service**: Authentication and authorization (port 5001) 
- **PostgreSQL**: Database (port 5432)

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd file-storage-api
   ```

2. **Start services**:
    ```bash
    docker-compose up --build
    ```

3. **Services will be available at**:

        Storage API: http://localhost:5000
        Auth API: http://localhost:5001
        PostgreSQL: localhost:5432

## API Usage

1. Authentication
    Login:

        ```bash
        curl -X POST http://localhost:5000/login \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "admin123"}'
        
    Response:

        json
        {"token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}
        

2. File Operations
    List files:

        ```bash
        curl -X GET "http://localhost:5000/list?path=/" \
        -H "Authorization: Bearer YOUR_TOKEN"
        

    Upload file:

        ```bash
        curl -X PUT "http://localhost:5000/put?path=/docs&filename=test.txt" \
        -H "Authorization: Bearer YOUR_TOKEN" \
        -d "This is file content"
      

    Download file:

        ```bash
        curl -X GET "http://localhost:5000/get?path=/docs&filename=test.txt" \
        -H "Authorization: Bearer YOUR_TOKEN" \
        --output downloaded.txt


## Default Users:
    admin / admin123 - Full access to all paths
    user1 / user123 - Read access to root, read/write to /public

## Database Schema
    Users Table:
        id, username, password_hash, created_at

    Permissions Table:
        id, user_id, path, can_read, can_write, created_at

    Files Table:
        id, path, filename, content, user_id, created_at, updated_at

## Third-party Libraries
    **Storage Service**:
        Flask (2.3.3)       :   Lightweight web framework for API
        Psycopg2 (2.9.7)    :   PostgreSQL adapter for Python
        Requests (2.31.0)   :   HTTP client for auth service communication
        PyJWT (2.8.0)       :   JWT token handling

    **Auth Service**:
        Flask (2.3.3)   :   Web framework
        Psycopg2 (2.9.7):   Database operations
        PyJWT (2.8.0)   :   Token generation/validation

    ## Justification
        Flask       : Simple, lightweight, perfect for microservices
        Psycopg2    : Standard, well-supported PostgreSQL driver
        Requests    : Simple HTTP client for service communication
        PyJWT       : Industry standard for JWT tokens

## Resources Used
    Flask Documentation: https://flask.palletsprojects.com/

    Psycopg2 Documentation: https://www.psycopg.org/docs/

    Docker Compose Documentation: https://docs.docker.com/compose/

    JWT.io Introduction: https://jwt.io/introduction/

    PostgreSQL Documentation: https://www.postgresql.org/docs/


## Development Time
    Approximately 6-8 hours including:
        - Design and database schema planning
        - Implementation of both services
        - Docker configuration and testing
        - Documentation and bug fixes

## Production Considerations
    - Use proper password hashing (bcrypt)
    - Implement token blacklisting with Redis
    - Add rate limiting
    - Use environment variables for secrets
    - Implement proper error handling and monitoring
    - Add API versioning
    - Implement file size limits and validation
