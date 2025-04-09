#!/bin/bash
fuser -k 8000/tcp     # Dödar tidigare Gunicorn-processer som körs på port 8000
cd /home/runerova/smartweb
source /home/runerova/myenv/bin/activate
exec gunicorn -w 4 -b 0.0.0.0:8000 app:app
