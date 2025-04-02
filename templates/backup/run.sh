#!/bin/bash
cd /home/runerova/smartweb
source /home/runerova/myenv/bin/activate
exec gunicorn -w 4 -b 0.0.0.0:8000 app:app
