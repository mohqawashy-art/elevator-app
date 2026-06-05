#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate
elif [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
python import_real_data.py "${1:-$HOME/Downloads}"
echo "افتح صفحة العملاء وتاب الخريطة لتحديد المواقع تلقائياً"
