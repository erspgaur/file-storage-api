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
ADMIN_TOKEN=""
USER_TOKEN=""

# Docker compose command detection
DOCKER_COMPOSE_CMD=""

# Counters
PASSED=0
FAILED=0

# Function to detect and set docker compose command
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
        print_info "Using docker-compose command"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
        print_info "Using docker compose command"
    else
        print_warning "Neither 'docker-compose' nor 'docker compose' commands found"
        return 1
    fi
    return 0
}

# Function to run docker compose commands
docker_compose() {
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        detect_docker_compose || return 1
    fi
    # Split the command string into array and execute
    eval $DOCKER_COMPOSE_CMD "$@"
}

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
    
    # Detect docker compose command first
    if ! detect_docker_compose; then
        print_warning "Docker compose not available, trying direct HTTP checks..."
    fi
    
    # Wait for storage service
    for i in {1..30}; do
        if curl -s $STORAGE_URL/health > /dev/null 2>&1; then
            break
        fi
        if [ $i -eq 30 ]; then
            print_warning "Storage service not ready after 30 attempts"
            return 1
        fi
        sleep 2
    done
    
    # Wait for auth service
    for i in {1..30}; do
        if curl -s $AUTH_URL/health > /dev/null 2>&1; then
            break
        fi
        if [ $i -eq 30 ]; then
            print_warning "Auth service not ready after 30 attempts"
            return 1
        fi
        sleep 2
    done
    
    print_info "Services are ready!"
    return 0
}

test_authentication() {
    echo
    echo "=== AUTHENTICATION TESTS ==="
    
    # Test 1: Login with admin credentials via storage service
    print_info "Testing admin login via storage service..."
    response=$(curl -s -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$ADMIN_USER\", \"password\": \"$ADMIN_PASS\"}" \
        -w "%{http_code}")
    
    status_code=${response: -3}
    response_body=${response%???}
    
    if [ $status_code -eq 200 ]; then
        ADMIN_TOKEN=$(echo $response_body | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
        if [ ! -z "$ADMIN_TOKEN" ]; then
            print_result 0 "Admin login successful"
            echo "Admin Token: ${ADMIN_TOKEN:0:20}..."
        else
            print_result 1 "Admin login - token not found in response"
            echo "Response: $response_body"
        fi
    else
        print_result 1 "Admin login failed with status $status_code"
        echo "Response: $response_body"
    fi
    
    # Test 2: Login with regular user credentials
    print_info "Testing regular user login via storage service..."
    response=$(curl -s -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$REGULAR_USER\", \"password\": \"$REGULAR_PASS\"}" \
        -w "%{http_code}")
    
    status_code=${response: -3}
    response_body=${response%???}
    
    if [ $status_code -eq 200 ]; then
        USER_TOKEN=$(echo $response_body | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
        if [ ! -z "$USER_TOKEN" ]; then
            print_result 0 "Regular user login successful"
            echo "User Token: ${USER_TOKEN:0:20}..."
        else
            print_result 1 "User login - token not found in response"
        fi
    else
        print_result 1 "User login failed with status $status_code"
    fi
}

test_file_operations() {
    echo
    echo "=== FILE OPERATION TESTS ==="
    
    if [ -z "$ADMIN_TOKEN" ] || [ -z "$USER_TOKEN" ]; then
        print_warning "Skipping file operation tests - missing tokens"
        return
    fi
    
    # Test 1: Upload file to root path (admin)
    print_info "Testing file upload to root path (admin)..."
    response=$(curl -s -X PUT "$STORAGE_URL/put?path=/&filename=admin_file.txt" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "This is a test file from admin" \
        -w "%{http_code}")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "Admin can upload file to root" || print_result 1 "Admin should be able to upload to root"
    
    # Test 2: User downloading admin's file from root (should fail - FIXED)
    print_info "Testing user downloading admin's file from root (should fail)..."
    response=$(curl -s -X GET "$STORAGE_URL/get?path=/&filename=admin_file.txt" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -w "%{http_code}")
    
    status_code=${response: -3}
    if [ $status_code -eq 403 ] || [ $status_code -eq 404 ]; then
        print_result 0 "User correctly cannot access admin's root files"
    else
        print_result 1 "User should not access admin's root files (got status: $status_code)"
    fi
    
    # Test 3: Upload file to public path (user - should succeed)
    print_info "Testing file upload to public path (user - should succeed)..."
    response=$(curl -s -X PUT "$STORAGE_URL/put?path=/public&filename=user_public_file.txt" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "This is a user file in public directory" \
        -w "%{http_code}")
    
    status_code=${response: -3}
    [ $status_code -eq 200 ] && print_result 0 "User can upload to public directory" || print_result 1 "User should be able to upload to public directory"
    
    # Test 4: Admin downloading user's public file (should succeed)
    print_info "Testing admin downloading user's public file..."
    response=$(curl -s -X GET "$STORAGE_URL/get?path=/public&filename=user_public_file.txt" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -o /tmp/downloaded_public_file.txt \
        -w "%{http_code}")
    
    status_code=${response: -3}
    content=$(cat /tmp/downloaded_public_file.txt 2>/dev/null)
    
    if [ -f "/tmp/downloaded_public_file.txt" ] && [ "$content" = "This is a user file in public directory" ]; then
        print_result 0 "Admin can download user's public file"
    else
        print_result 1 "Admin should be able to download public files (status: $status_code)"
    fi
    
    # Cleanup
    rm -f /tmp/downloaded_public_file.txt
}

test_logging() {
    echo
    echo "=== LOGGING TESTS ==="
    
    print_info "Generating test traffic for logging verification..."
    
    # Generate multiple requests to ensure logs are produced
    curl -s -X POST "$STORAGE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "admin123"}' > /dev/null
    
    curl -s -X POST "$AUTH_URL/authenticate" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "admin123"}' > /dev/null
    
    # Wait for logs to be written
    sleep 3
    
    # Check storage service logs
    print_info "Checking storage service logs..."
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        storage_logs=$(docker_compose logs storage --tail=50 2>/dev/null)
    else
        storage_logs=$(docker logs file-storage-api-storage-1 --tail=50 2>/dev/null)
    fi
    
    if [ ! -z "$storage_logs" ] && [ $(echo "$storage_logs" | wc -l) -gt 5 ]; then
        print_result 0 "Storage service is logging to stdout"
        echo "Recent storage logs:"
        echo "$storage_logs" | tail -3
    else
        print_result 1 "Storage service should log to stdout"
        print_warning "No storage logs found"
        # Debug: check if container is running
        print_info "Checking storage container status..."
        if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
            docker_compose ps storage
        else
            docker ps | grep storage
        fi
    fi
    
    # Check auth service logs
    print_info "Checking auth service logs..."
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        auth_logs=$(docker_compose logs auth --tail=50 2>/dev/null)
    else
        auth_logs=$(docker logs file-storage-api-auth-1 --tail=50 2>/dev/null)
    fi
    
    if [ ! -z "$auth_logs" ] && [ $(echo "$auth_logs" | wc -l) -gt 5 ]; then
        print_result 0 "Auth service is logging to stdout"
        echo "Recent auth logs:"
        echo "$auth_logs" | tail -3
    else
        print_result 1 "Auth service should log to stdout"
        print_warning "No auth logs found"
        # Debug: check if container is running
        print_info "Checking auth container status..."
        if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
            docker_compose ps auth
        else
            docker ps | grep auth
        fi
    fi
}

summary() {
    echo
    echo "=== TEST SUMMARY ==="
    echo -e "Total Tests: $((PASSED + FAILED))"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}🎉 All tests passed!${NC}"
    else
        echo -e "${YELLOW}⚠ Some tests failed.${NC}"
    fi
}

check_services_running() {
    print_info "Checking if services are running..."
    
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        if docker_compose ps | grep -q "Up"; then
            return 0
        else
            print_warning "Docker containers don't appear to be running."
            echo "Start them with: docker-compose up -d  OR  docker compose up -d"
            return 1
        fi
    else
        # Fallback to direct docker check
        if docker ps | grep -q "file-storage-api"; then
            return 0
        else
            print_warning "Docker containers don't appear to be running."
            echo "Start them with: docker-compose up -d  OR  docker compose up -d"
            return 1
        fi
    fi
}

main() {
    echo "File Storage API Test Suite"
    echo "==========================="
    
    # Check if services are running
    if ! check_services_running; then
        exit 1
    fi
    
    # Check if services are ready
    if ! wait_for_services; then
        echo "Please start services with: docker-compose up -d  OR  docker compose up -d"
        exit 1
    fi
    
    test_authentication
    test_file_operations
    test_logging
    summary
}

main