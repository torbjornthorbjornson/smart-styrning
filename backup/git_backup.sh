#!/bin/bash
cd /home/runerova/smartweb

# Ladda GitHub-token från säker plats om den finns
TOKEN_FILE="/home/runerova/.github_token"
if [ -f "$TOKEN_FILE" ]; then
    export GITHUB_TOKEN=$(cat $TOKEN_FILE)
fi

# Lägg till alla ändringar
git add .

# Skapa commit-meddelande med datum/tid
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Automatisk backup: $TIMESTAMP"

# Pusha till GitHub – token används automatiskt om behövs
git push
#!/bin/bash
cd /home/runerova/smartweb

# Lägg till alla ändringar
git add .

# Skapa commit-meddelande med datum/tid
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Automatisk backup: $TIMESTAMP"

# Skicka till GitHub
git push

