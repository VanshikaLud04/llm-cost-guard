#!/bin/bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 latency_test_server.py &
SERVER_PID=$!
sleep 2
ab -c 10 -n 500 http://127.0.0.1:8000/baseline > base_light.txt
ab -c 10 -n 500 http://127.0.0.1:8000/wrapped > wrap_light.txt
kill $SERVER_PID
grep "Time per request:" base_light.txt wrap_light.txt
