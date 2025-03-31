#!/bin/bash

# Variabler
BACKUP_DIR=~/smartweb_backup
PROJECT_DIR=~/smartweb
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Lista på filer att säkerhetskopiera
FILES=("app.py" "templates/index.html" "static/styles.css")

# Loop för att kopiera varje fil
for file in "${FILES[@]}"
do
  if [ -f "$PROJECT_DIR/$file" ]; then
    # Skapa undermappar vid behov
    mkdir -p "$(dirname "$BACKUP_DIR/$file")"
    cp "$PROJECT_DIR/$file" "$BACKUP_DIR/${file}_$TIMESTAMP"
    echo "Backup av $file klar."
  else
    echo "VARNING: $file finns inte och kunde inte kopieras."
  fi
done
