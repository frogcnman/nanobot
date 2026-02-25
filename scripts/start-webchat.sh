#!/bin/bash
# Start nanobot Web Chat

cd "$(dirname "$0")/.."

# Default values
export API_BASE_URL="${API_BASE_URL:-}"
export API_KEY="${API_KEY:-}"
export MODEL="${MODEL:-}"
export SYSTEM_PROMPT="${SYSTEM_PROMPT:-}"

# Start the server
echo "Starting nanobot Web Chat..."
echo "Access at: http://localhost:8081"

python3 -m nanobot.webchat
