#!/bin/bash
cd "$(dirname "$0")" || exit 1
source venv/bin/activate

BEFORE_PULL=$(git rev-parse HEAD)
git pull https://github.com/wolfricoz/dawnbot --rebase --force --autostash
AFTER_PULL=$(git rev-parse HEAD)

if [ "$BEFORE_PULL" = "$AFTER_PULL" ]; then
    echo "No updates found. Skipping restart."
    exit 0
fi

echo "Updates detected. Installing dependencies..."
if ! pip install -r requirements.txt; then
    echo "pip install failed. Not restarting."
    exit 1
fi

if ! alembic upgrade head; then
    echo "Migration failed. Not restarting."
    exit 1
fi

echo "Restarting dawnbot..."
sudo supervisorctl restart dawnbot