#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STORAGE_URL="http://localhost:5000"
AUTH_URL="http://localhost:5001"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
REGULAR_USER="user1"
REGULAR_PASS="user123"
TEST_TOKEN=""
ADMIN_TOKEN=""
USER_TOKEN=""

# Counters
PASSED=0
FAILED=0

print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAILED++))
    fi
}

print_info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

wait_for_services() {
    print_info "Waiting for services to be ready..."
    
    until curl -s $STORAGE_URL/health > /dev/null 2>&1; do
        print_warning "Storage service not ready yet, waiting..."
        sleep 5
    done
    
    until curl -s $AUTH_URL/health > /dev/null 2>&1; do
        print_warning "Auth service not ready yet, waiting..."
        sleep 5
    done
    
    print_info "Services are ready!"
}

# Add health check endpoints temporarily
add_health_checks() {
    print_info "Adding temporary health check endpoints..."
    
    # This would be added to both services temporarily
    cat > health_check.py << 'EOF'
from flask import jsonify

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200
EOF
}

test_authentication() {
    echo
    echo "=== AUTHENTICATION TESTS ==="
    
    # Test 1: Login with admin credentials via storage service
    print_info "Testing admin login via storage service..."
    response=$(curl -s -w "%{http_code}" -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$ADMIN_USER\", \"password\": \"$ADMIN_PASS\"}")
    
    status_code=${response: -3}
    response_body=${response%???}
    
    if [ $status_code -eq 200 ]; then
        ADMIN_TOKEN=$(echo $response_body | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        if [ ! -z "$ADMIN_TOKEN" ]; then
            print_result 0 "Admin login successful"
            echo "Admin Token: ${ADMIN_TOKEN:0:20}..."
        else
            print_result 1 "Admin login - token not found in response"
        fi
    else
        print_result 1 "Admin login failed with status $status_code"
    fi
    
    # Test 2: Login with regular user credentials
    print_info "Testing regular user login via storage service..."
    response=$(curl -s -w "%{http_code}" -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$REGULAR_USER\", \"password\": \"$REGULAR_PASS\"}")
    
    status_code=${response: -3}
    response_body=${response%???}
    
    if [ $status_code -eq 200 ]; then
        USER_TOKEN=$(echo $response_body | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        if [ ! -z "$USER_TOKEN" ]; then
            print_result 0 "Regular user login successful"
            echo "User Token: ${USER_TOKEN:0:20}..."
        else
            print_result 1 "User login - token not found in response"
        fi
    else
        print_result 1 "User login failed with status $status_code"
    fi
    
    # Test 3: Login with invalid credentials
    print_info "Testing login with invalid credentials..."
    response=$(curl -s -w "%{http_code}" -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "invalid", "password": "wrong"}')
    
    status_code=${response: -3}
    [ $status_code -eq 401 ] && print_result 0 "Invalid login correctly rejected" || print_result 1 "Invalid login should return 401"
    
    # Test 4: Direct auth service authentication
    print_info "Testing direct auth service authentication..."
    response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authenticate" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$ADMIN_USER\", \"password\": \"$ADMIN_PASS\"}")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "Direct auth service authentication works" || print_result 1 "Direct auth service authentication failed"
}

test_authorization() {
    echo
    echo "=== AUTHORIZATION TESTS ==="
    
    if [ -z "$ADMIN_TOKEN" ]; then
        print_warning "Skipping authorization tests - no admin token"
        return
    fi
    
    # Test 1: Admin authorization check for root path read
    print_info "Testing admin authorization for root path read..."
    response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authorize" \
        -H "Content-Type: application/json" \
        -d "{\"token\": \"$ADMIN_TOKEN\", \"path\": \"/\", \"operation\": \"read\"}")
    
    status_code=${response: -3}
    response_body=${response%???}
    authorized=$(echo $response_body | grep -o '"authorized":true')
    
    if [ $status_code -eq 200 ] && [ ! -z "$authorized" ]; then
        print_result 0 "Admin authorized for root read"
    else
        print_result 1 "Admin should be authorized for root read"
    fi
    
    # Test 2: Admin authorization check for root path write
    print_info "Testing admin authorization for root path write..."
    response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authorize" \
        -H "Content-Type: application/json" \
        -d "{\"token\": \"$ADMIN_TOKEN\", \"path\": \"/\", \"operation\": \"write\"}")
    
    status_code=${response: -3}
    response_body=${response%???}
    authorized=$(echo $response_body | grep -o '"authorized":true')
    
    if [ $status_code -eq 200 ] && [ ! -z "$authorized" ]; then
        print_result 0 "Admin authorized for root write"
    else
        print_result 1 "Admin should be authorized for root write"
    fi
    
    # Test 3: User authorization check for root path write (should fail)
    if [ ! -z "$USER_TOKEN" ]; then
        print_info "Testing user authorization for root path write (should fail)..."
        response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authorize" \
            -H "Content-Type: application/json" \
            -d "{\"token\": \"$USER_TOKEN\", \"path\": \"/\", \"operation\": \"write\"}")
        
        status_code=${response: -3}
        response_body=${response%???}
        authorized=$(echo $response_body | grep -o '"authorized":false')
        
        if [ $status_code -eq 403 ] || [ ! -z "$authorized" ]; then
            print_result 0 "User correctly not authorized for root write"
        else
            print_result 1 "User should not be authorized for root write"
        fi
    fi
    
    # Test 4: Invalid token authorization
    print_info "Testing authorization with invalid token..."
    response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authorize" \
        -H "Content-Type: application/json" \
        -d '{"token": "invalid.token.here", "path": "/", "operation": "read"}')
    
    status_code=${response: -3}
    [ $status_code -eq 401 ] && print_result 0 "Invalid token correctly rejected" || print_result 1 "Invalid token should return 401"
}

test_file_operations() {
    echo
    echo "=== FILE OPERATION TESTS ==="
    
    if [ -z "$ADMIN_TOKEN" ] || [ -z "$USER_TOKEN" ]; then
        print_warning "Skipping file operation tests - missing tokens"
        return
    fi
    
    # Test 1: List files in root path (admin)
    print_info "Testing list files in root path (admin)..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/list?path=/" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "Admin can list root directory" || print_result 1 "Admin should be able to list root directory"
    
    # Test 2: Upload file to root path (admin)
    print_info "Testing file upload to root path (admin)..."
    response=$(curl -s -w "%{http_code}" -X PUT "$STORAGE_URL/put?path=/&filename=admin_file.txt" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "This is a test file from admin")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "Admin can upload file to root" || print_result 1 "Admin should be able to upload to root"
    
    # Test 3: Upload file to root path (user - should fail)
    print_info "Testing file upload to root path (user - should fail)..."
    response=$(curl -s -w "%{http_code}" -X PUT "$STORAGE_URL/put?path=/&filename=user_file.txt" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "This is a test file from user")
    
    status_code=${response: -3}
    [ $status_code -eq 403 ] && print_result 0 "User correctly cannot upload to root" || print_result 1 "User should not be able to upload to root"
    
    # Test 4: Upload file to public path (user - should succeed)
    print_info "Testing file upload to public path (user - should succeed)..."
    response=$(curl -s -w "%{http_code}" -X PUT "$STORAGE_URL/put?path=/public&filename=user_public_file.txt" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "This is a user file in public directory")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "User can upload to public directory" || print_result 1 "User should be able to upload to public directory"
    
    # Test 5: List files in public path (user)
    print_info "Testing list files in public path (user)..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/list?path=/public" \
        -H "Authorization: Bearer $USER_TOKEN")
    
    status_code=${response: -3}
    response_body=${response%???}
    has_file=$(echo $response_body | grep -o "user_public_file.txt")
    
    if [ $status_code -eq 200 ] && [ ! -z "$has_file" ]; then
        print_result 0 "User can list public directory and see uploaded file"
    else
        print_result 1 "User should see uploaded file in public directory"
    fi
    
    # Test 6: Download file (admin)
    print_info "Testing file download (admin)..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/get?path=/&filename=admin_file.txt" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -o /tmp/downloaded_admin_file.txt)
    
    status_code=$?
    content=$(cat /tmp/downloaded_admin_file.txt 2>/dev/null)
    
    if [ -f "/tmp/downloaded_admin_file.txt" ] && [ "$content" = "This is a test file from admin" ]; then
        print_result 0 "Admin can download uploaded file"
    else
        print_result 1 "Admin should be able to download uploaded file"
    fi
    
    # Test 7: User downloading admin's file from root (should fail due to path permissions)
    print_info "Testing user downloading admin's file from root (should fail)..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/get?path=/&filename=admin_file.txt" \
        -H "Authorization: Bearer $USER_TOKEN")
    
    status_code=${response: -3}
    [ $status_code -eq 403 ] && print_result 0 "User correctly cannot access root files" || print_result 1 "User should not access root files"
    
    # Test 8: Admin downloading user's public file (should succeed)
    print_info "Testing admin downloading user's public file..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/get?path=/public&filename=user_public_file.txt" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -o /tmp/downloaded_public_file.txt)
    
    status_code=$?
    content=$(cat /tmp/downloaded_public_file.txt 2>/dev/null)
    
    if [ -f "/tmp/downloaded_public_file.txt" ] && [ "$content" = "This is a user file in public directory" ]; then
        print_result 0 "Admin can download user's public file"
    else
        print_result 1 "Admin should be able to download public files"
    fi
    
    # Cleanup test files
    rm -f /tmp/downloaded_*.txt
}

test_error_scenarios() {
    echo
    echo "=== ERROR SCENARIO TESTS ==="
    
    # Test 1: Access without token
    print_info "Testing access without authentication token..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/list?path=/")
    status_code=${response: -3}
    [ $status_code -eq 401 ] && print_result 0 "Access without token correctly rejected" || print_result 1 "Should require authentication token"
    
    # Test 2: Access with invalid token
    print_info "Testing access with invalid token..."
    response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/list?path=/" \
        -H "Authorization: Bearer invalid.token.here")
    status_code=${response: -3}
    [ $status_code -eq 401 ] && print_result 0 "Invalid token correctly rejected" || print_result 1 "Should reject invalid tokens"
    
    # Test 3: Missing path parameter
    if [ ! -z "$ADMIN_TOKEN" ]; then
        print_info "Testing missing path parameter..."
        response=$(curl -s -w "%{http_code}" -X GET "$STORAGE_URL/list" \
            -H "Authorization: Bearer $ADMIN_TOKEN")
        status_code=${response: -3}
        [ $status_code -eq 400 ] && print_result 0 "Missing path parameter correctly handled" || print_result 1 "Should require path parameter"
    fi
    
    # Test 4: Invalid operation to auth service
    print_info "Testing invalid operation to auth service..."
    response=$(curl -s -w "%{http_code}" -X POST "$AUTH_URL/authorize" \
        -H "Content-Type: application/json" \
        -d '{"token": "some.token", "path": "/", "operation": "invalid_op"}')
    status_code=${response: -3}
    [ $status_code -eq 400 ] && print_result 0 "Invalid operation correctly rejected" || print_result 1 "Should reject invalid operations"
    
    # Test 5: Malformed JSON
    print_info "Testing malformed JSON request..."
    response=$(curl -s -w "%{http_code}" -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": }')
    status_code=${response: -3}
    [ $status_code -eq 400 ] && print_result 0 "Malformed JSON correctly rejected" || print_result 1 "Should reject malformed JSON"
}

test_logging() {
    echo
    echo "=== LOGGING TESTS ==="
    
    print_info "Checking if services are writing logs..."
    
    # Check storage service logs
    storage_logs=$(docker-compose logs storage 2>/dev/null | wc -l)
    if [ $storage_logs -gt 10 ]; then
        print_result 0 "Storage service is logging to stdout"
    else
        print_result 1 "Storage service should log to stdout"
    fi
    
    # Check auth service logs
    auth_logs=$(docker-compose logs auth 2>/dev/null | wc -l)
    if [ $auth_logs -gt 10 ]; then
        print_result 0 "Auth service is logging to stdout"
    else
        print_result 1 "Auth service should log to stdout"
    fi
    
    # Check for combined log format (approximate check)
    combined_format=$(docker-compose logs storage 2>/dev/null | head -5 | grep -E "[0-9]{4}-[0-9]{2}-[0-9]{2}.*(GET|POST|PUT).*[0-9]{3}" | wc -l)
    if [ $combined_format -gt 0 ]; then
        print_result 0 "Logs appear to be in combined format"
    else
        print_warning "Cannot verify combined log format automatically"
    fi
}

summary() {
    echo
    echo "=== TEST SUMMARY ==="
    echo -e "Total Tests: $((PASSED + FAILED))"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}🎉 All tests passed! The implementation meets all requirements.${NC}"
    else
        echo -e "${YELLOW}⚠ Some tests failed. Check the implementation.${NC}"
    fi
    
    echo
    echo "=== RECOMMENDED MANUAL TESTS ==="
    echo "1. Verify database persistence: stop and start containers, check if files remain"
    echo "2. Test concurrent file operations"
    echo "3. Verify error logs are written to stderr"
    echo "4. Test with different file types and sizes"
    echo "5. Verify token expiration behavior"
}

main() {
    echo "File Storage API Comprehensive Test Suite"
    echo "========================================="
    
    # # Check if docker-compose is running
    # alias docker-compose='docker compose'
    # if ! docker-compose ps | grep -q "Up"; then
    #     print_warning "Docker containers don't appear to be running."
    #     echo "Start them with: docker-compose up -d"
    #     echo "Then run this test script again."
    #     exit 1
    # fi
    
    wait_for_services
    test_authentication
    test_authorization
    test_file_operations
    test_error_scenarios
    test_logging
    summary
}

# Run main function
main