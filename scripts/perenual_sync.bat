@echo off
cd /d C:\Users\gccar\Documents\gardening\garden_app\gardening_app
uv run python scripts/perenual_sync.py >> logs\perenual_sync.log 2>&1
