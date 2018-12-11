#!/bin/bash
kill -9 $(ps -ef | grep 'python3 ping.py' | grep -v grep | awk '{print $2}')
git fetch --all
git reset --hard origin/master 
git pull
nohup python3 ping.py > nohup2.out 2>&1&