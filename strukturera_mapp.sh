#!/bin/bash
echo "📁 Skapar strukturer..."
mkdir -p backup logs scripts docs systemd

echo "📦 Flyttar backupfiler..."
mv *.backup* backup/ 2>/dev/null
mv *.save* backup/ 2>/dev/null
mv *backup*.sh backup/ 2>/dev/null
mv git_backup* backup/ 2>/dev/null

echo "📜 Flyttar loggfiler..."
mv *.log logs/ 2>/dev/null

echo "📜 Flyttar script..."
mv run.sh scripts/ 2>/dev/null
mv run.sh.save* scripts/ 2>/dev/null
mv importera_eldagar.sh scripts/ 2>/dev/null
mv watch_backup.sh scripts/ 2>/dev/null
mv git_tagga_stabil.sh scripts/ 2>/dev/null

echo "🧠 Flyttar dokumentation..."
mv *.txt docs/ 2>/dev/null
mv vision.txt docs/ 2>/dev/null
mv git_kommandon* docs/ 2>/dev/null

echo "⚙️ Flyttar systemd-tjänster..."
mv gunicorn.service* systemd/ 2>/dev/null

echo "✅ Klart! Struktur uppdaterad."
