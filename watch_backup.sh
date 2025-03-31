#!/bin/bash

PROJECT_DIR=~/smartweb
BACKUP_SCRIPT=$PROJECT_DIR/backup_smartweb.sh

echo "Startar automatisk backup vid ändring..."
inotifywait -m -e modify,create,delete --format '%w%f' \
    "$PROJECT_DIR/app.py" \
    "$PROJECT_DIR/templates/index.html" \
    "$PROJECT_DIR/static/styles.css" \
| while read FILE
do
    echo "$(date +"%Y-%m-%d %H:%M:%S"): Ändring detekterad i $FILE"
    bash "$BACKUP_SCRIPT"
done


