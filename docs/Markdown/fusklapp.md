# ===============================
# Lathund – Smart fastighetsstyrning
# ===============================

# 🔧 MariaDB
sudo systemctl start mariadb
sudo systemctl stop mariadb
sudo systemctl restart mariadb
sudo systemctl status mariadb

# Logga in i databasen (använder ~/.my.cnf)
mysql smart_styrning

# Vanliga SQL-frågor
SHOW TABLES;
SELECT COUNT(*) FROM electricity_prices;
SELECT COUNT(*) FROM weather;
SELECT MIN(datetime), MAX(datetime) FROM electricity_prices;

# 🌐 Gunicorn / Flask (smartweb)
sudo systemctl start smartweb
sudo systemctl stop smartweb
sudo systemctl restart smartweb
sudo systemctl status smartweb
journalctl -u smartweb -n 50

# ⚡ Spotpris
python3 ~/smartweb/spotpris.py
tail -n 50 ~/smartweb/spotpris_info.log
tail -n 50 ~/smartweb/spotpris_error.log
bash ~/smartweb/tools/push_prices.sh
bash ~/smartweb/tools/push_prices_tomorrow.sh

# 🌦️ Väder
python3 ~/smartweb/weather.py
mysql smart_styrning -e "SELECT * FROM weather ORDER BY timestamp DESC LIMIT 5;"

# ⏱️ Cron-jobb
crontab -l
crontab -e

# 💾 Git & backup
cd ~/smartweb
git add .
git commit -m "Backup $(date +%F_%T)"
git push
git log --oneline --graph --decorate -n 10

# 📜 Logrotate
sudo logrotate -d /etc/logrotate.d/smartweb
sudo logrotate -f /etc/logrotate.d/smartweb
