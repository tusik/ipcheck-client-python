#!/bin/bash
kill -9 $(ps -ef | grep 'python3 ping.py' | grep -v grep | awk '{print $2}')
git pull
nohup python3 ping.py &