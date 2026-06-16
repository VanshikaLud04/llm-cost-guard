#!/bin/bash
export REDIS_URL=redis://localhost:6379/0
echo "Starting test server..."
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 latency_test_server.py &
SERVER_PID=$!

# Wait for server to be ready
sleep 3

echo "Running baseline test..."
ab -c 20 -n 1000 http://127.0.0.1:8000/baseline > baseline_results.txt

echo "Running wrapped test..."
ab -c 20 -n 1000 http://127.0.0.1:8000/wrapped > wrapped_results.txt

echo "Stopping test server..."
kill $SERVER_PID
echo "Done."
