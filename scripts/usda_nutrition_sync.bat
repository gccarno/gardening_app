@echo off
cd /d C:\Users\gccar\Documents\gardening\garden_app\gardening_app
uv run python scripts/usda_nutrition_sync.py >> logs\usda_nutrition_sync.log 2>&1
