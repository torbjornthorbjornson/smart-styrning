#!/bin/bash

PROJECT_DIR=~/smartweb
#!/bin/bash

# Ange den nya backup-mappen utanför smartweb
BACKUP_DIR="/home/runerova/backups"

# Ange var backup-skriptet finns
BACKUP_SCRIPT="/home/runerova/smartweb/backup_smartweb.sh"

# Skapa backup-mappen om den inte redan finns
mkdir -p "$BACKUP_DIR"

echo "Startar automatisk backup vid ändring..."

# Övervaka ändringar i de specificerade filerna
inotifywait -m -e modify,create,delete --format '%w%f' \
    "/home/runerova/smartweb/app.py" \
    "/home/runerova/smartweb/templates/index.html" \
    "/home/runerova/smartweb/static/styles.css" \
| while read FILE
do
    echo "$(date +"%Y-%m-%d %H:%M:%S"): Ändring detekterad i $FILE"
    bash "$BACKUP_SCRIPT"  # Kör backup-skriptet
done
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


