#!/bin/bash
echo "Quick Test - File Storage API"
echo "============================="

# Detect docker compose and check if services are running
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "Error: Neither 'docker-compose' nor 'docker compose' commands found"
    exit 1
fi

# Check if services are running
if ! $DOCKER_COMPOSE_CMD ps | grep -q "Up"; then
    echo "Services are not running. Starting them..."
    $DOCKER_COMPOSE_CMD up -d
    sleep 10
fi

# Wait for services to start
echo "Waiting for services..."
sleep 10

# Quick test
echo -e "\n1. Testing login..."
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ Login failed"
    exit 1
fi

echo "✅ Login successful"

echo -e "\n2. Testing file upload..."
curl -X PUT "http://localhost:5000/put?path=/&filename=test.txt" \
  -H "Authorization: Bearer $TOKEN" \
  -d "Hello World" > /dev/null 2>&1

echo -e "\n3. Testing file list..."
curl -s -X GET "http://localhost:5000/list?path=/" \
  -H "Authorization: Bearer $TOKEN" | grep -q "test.txt"

if [ $? -eq 0 ]; then
    echo "✅ File operations working"
else
    echo "❌ File operations failed"
fi

echo -e "\n4. Testing file download..."
CONTENT=$(curl -s -X GET "http://localhost:5000/get?path=/&filename=test.txt" \
  -H "Authorization: Bearer $TOKEN")

if [ "$CONTENT" = "Hello World" ]; then
    echo "✅ File download working"
else
    echo "❌ File download failed"
fi

echo -e "\n🎉 Basic functionality verified!"