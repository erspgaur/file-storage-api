

## Docker Compose Compatibility

    This validation test feature supports both legacy `docker-compose` and modern `docker compose` commands. The system will automatically detect which command is available on your system.

## Legacy docker-compose (v1)
    The test script will automatically detect and use appropriate commands like these:
        docker-compose up -d
        docker-compose down
        docker-compose logs



## Legacy Docker Compose (v2)
    The test script will automatically detect and use appropriate commands like these:
        docker compose up -d
        docker compose down
        docker compose logs


## Usage Instructions

## Run the comprehensive test:
        ./test_all_scenarios.sh

    
    Or run the quick test:
    
        ./quick_test.sh


## What This Script Tests

    ✅ Authentication & Authorization
        - Login with valid/invalid credentials
        - Token generation and validation
        - Role-based permissions
        - Path-based authorization

    ✅ File Operations
        - File upload (PUT)
        - File listing (LIST)
        - File download (GET)
        - Permission enforcement

    ✅ Error Handling
        - Invalid tokens
        - Missing parameters
        - Permission denied scenarios
        - Malformed requests

    ✅ Logging
        - Service logging verification
        - Combined log format check

    ✅ Integration
        - Service communication
        - Database operations
        - HTTP API compliance

