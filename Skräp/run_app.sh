#!/bin/bash
# Skript för att köra Python-applikationen med rätt miljö

echo "Aktiverar den virtuella miljön..."
source /home/runerova/myenv/bin/activate
echo "Kör Python-skriptet..."
python /home/runerova/spotpris.py

echo "Avaktiverar den virtuella miljön..."
deactivate

echo "Applikationen har avslutats korrekt."
