@echo off
cd /d C:\Users\gccar\Documents\gardening\garden_app\gardening_app
uv run python scripts/generate_plant_images.py ^
    --backend diffusers ^
    --hf-model sd-turbo ^
    --prompt 0 ^
    --time-limit 60 ^
    --delay 0 ^
    2>&1
