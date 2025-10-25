#!/bin/bash

echo "Stopping File Storage API Services..."

# Detect docker compose command
if command -v docker-compose &> /dev/null; then
    echo "Using docker-compose command"
    docker-compose down
elif docker compose version &> /dev/null; then
    echo "Using docker compose command"
    docker compose down
else
    echo "Error: Neither 'docker-compose' nor 'docker compose' commands found"
    exit 1
fi

echo "Services stopped successfully!"