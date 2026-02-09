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
