# Ops – drift och tjänster

Den här mappen är för ”hur det körs i verkligheten”: systemd units, env-filer, loggar, och standardkommandon.

## Systemd

- Smartweb (gunicorn/flask): se `smartweb/systemd/` och [ARCHITECTURE_BASELINE.md](../ARCHITECTURE_BASELINE.md)
- Arrigo orchestrator: `/etc/systemd/system/arrigo-orchestrator.service`

### Standardkommandon

```bash
# status
systemctl --no-pager --full status smartweb
systemctl --no-pager --full status arrigo-orchestrator

# loggar
journalctl -u smartweb -n 200 --no-pager
journalctl -u arrigo-orchestrator -n 200 --no-pager

# reload + restart
sudo systemctl daemon-reload
sudo systemctl restart smartweb
sudo systemctl restart arrigo-orchestrator
```

## Miljöfiler

- `/home/runerova/.smartweb.env` (webb/service)
- `/home/runerova/.arrigo.env` (orchestrator/tools)

Regel: env-filer innehåller inte stora dokumentationstexter; de refererar till docs istället.

## Verifiering + varningar

- Manuell smoke test: `smartweb/scripts/verify_runtime.sh`
- Med varning: `smartweb/scripts/verify_runtime_notify.sh`
  - Logg: `smartweb/logs/verify_runtime.log`
  - Syslog: `logger` (syns i `journalctl`)
  - Home Assistant (om konfig finns): notis vid FAIL

### Home Assistant – så får du varningen

1) I Home Assistant UI: Profil → Security → skapa en Long-Lived Access Token.
2) Lägg i `/home/runerova/.smartweb.env`:
   - `SMARTWEB_HA_URL=http://<din-ha>:8123`
   - `SMARTWEB_HA_TOKEN=<din_token>`
3) (Valfritt för push till mobil) sätt `SMARTWEB_HA_NOTIFY_SERVICE=<service>`.

### Autokörning (systemd timer)

Repo-mallar: `smartweb/systemd/verify-runtime.service` och `smartweb/systemd/verify-runtime.timer`.
Install:
```bash
sudo cp /home/runerova/smartweb/systemd/verify-runtime.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now verify-runtime.timer
```

## Node-RED (nästa steg)

Node-RED är superbra för larm/automatik när du redan kör Home Assistant.
Bra första flow: “Inject var 15:e minut → HTTP request till `http://127.0.0.1:8000/` → om fel → HA notify”.
