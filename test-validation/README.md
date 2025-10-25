## Usage Instructions

## Make scripts executable:

        ```bash
        chmod +x test_all_scenarios.sh quick_test.sh make_executable.sh
    
    Run the comprehensive test:
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

