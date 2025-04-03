#!/bin/bash
for i in {0..9}; do
  datum=$(date -d "today - $i day" +%F)
  echo "⏳ Hämtar elpriser för: $datum"
  python3 spotpris.py --datum $datum
done
