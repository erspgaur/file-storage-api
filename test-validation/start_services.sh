#!/bin/bash

echo "Starting File Storage API Services..."

# Detect docker compose command
if command -v docker-compose &> /dev/null; then
    echo "Using docker-compose command"
    docker-compose up --build -d
elif docker compose version &> /dev/null; then
    echo "Using docker compose command" 
    docker compose up --build -d
else
    echo "Error: Neither 'docker-compose' nor 'docker compose' commands found"
    echo "Please install Docker Compose:"
    echo "  Legacy: https://docs.docker.com/compose/install/"
    echo "  Modern: https://docs.docker.com/compose/install/compose-plugin/"
    exit 1
fi

echo "Services started successfully!"
echo "Run tests with: ./test_all_scenarios.sh"