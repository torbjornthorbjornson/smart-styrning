#!/bin/bash
# Wrapper så systemd alltid kan köra /home/runerova/smartweb/run.sh
# Den faktiska implementationen ligger i scripts/run.sh
set -euo pipefail
exec /home/runerova/smartweb/scripts/run.sh
