# Database Model

## ER Diagram

```mermaid
erDiagram
    Garden {
        int id PK
        string name
        string description
        string unit
        string zip_code
        string city
        string state
        float latitude
        float longitude
        string usda_zone
        string zone_temp_range
        date last_frost_date
        int watering_frequency_days
        string water_source
        string background_image
        text annotations
    }

    GardenBed {
        int id PK
        string name
        string description
        string location
        int garden_id FK
        float width_ft
        float height_ft
        float depth_ft
        float pos_x
        float pos_y
        text soil_notes
        float soil_ph
        float clay_pct
        float compost_pct
        float sand_pct
    }

    Plant {
        int id PK
        string name
        string type
        text notes
        date planted_date
        date transplant_date
        date expected_harvest
        string status
        int library_id FK
        int garden_id FK
    }

    BedPlant {
        int id PK
        int bed_id FK
        int plant_id FK
        int grid_x
        int grid_y
        date last_watered
        date last_fertilized
        date last_harvest
        text health_notes
        string stage
    }

    PlantLibrary {
        int id PK
        string name
        string scientific_name
        int perenual_id
        string image_filename
        string type
        int spacing_in
        string sunlight
        string water
        int days_to_germination
        int days_to_harvest
        text notes
        string difficulty
        int min_zone
        int max_zone
        int temp_min_f
        int temp_max_f
        float soil_ph_min
        float soil_ph_max
        string soil_type
        text good_neighbors
        text bad_neighbors
        int sow_indoor_weeks
        int direct_sow_offset
        int transplant_offset
        text how_to_grow
        text faqs
        text nutrition
        int permapeople_id
        string permapeople_link
        text permapeople_description
        string family
        string layer
        string edible_parts
    }

    CanvasPlant {
        int id PK
        int garden_id FK
        int library_id FK
        int plant_id FK
        float pos_x
        float pos_y
        float radius_ft
        string color
        string display_mode
        string custom_image
        string label
    }

    Task {
        int id PK
        string title
        text description
        date due_date
        bool completed
        date completed_date
        string task_type
        int plant_id FK
        int garden_id FK
        int bed_id FK
    }

    WeatherLog {
        int id PK
        int garden_id FK
        date date
        float rainfall_in
        float temp_high_f
        float temp_low_f
        string source
    }

    Garden ||--o{ GardenBed : "has"
    Garden ||--o{ Plant : "has"
    Garden ||--o{ CanvasPlant : "has"
    Garden ||--o{ Task : "has"
    Garden ||--o{ WeatherLog : "logs"

    GardenBed ||--o{ BedPlant : "contains"
    GardenBed ||--o{ Task : "has"

    Plant ||--o{ BedPlant : "placed via"
    Plant ||--o{ CanvasPlant : "placed via"
    Plant ||--o{ Task : "has"
    Plant }o--o| PlantLibrary : "based on"

    PlantLibrary ||--o{ CanvasPlant : "template for"
```

---

## Model Reference

### Garden
Top-level container. Each garden has a location (zip code → lat/lon, USDA zone, frost dates) used by the weather panel and planting calendar. The `annotations` field stores JSON for SVG drawing shapes on the planner canvas. `background_image` is a filename in `static/garden_backgrounds/`.

### GardenBed
A physical raised bed belonging to a garden. Positioned on the planner canvas via `pos_x`/`pos_y` (in feet). Dimensions (`width_ft`, `height_ft`) define the interactive plant grid. Soil data: free-text `soil_notes` plus structured `soil_ph`, `clay_pct`, `compost_pct`, `sand_pct`.

### Plant
A specific plant instance within a garden. Always linked to a `PlantLibrary` entry (`library_id`) for growing specs. Tracks lifecycle: `planted_date`, `transplant_date`, `expected_harvest`. `status` values: `planning`, `active`, `harvested`, `removed`.

### BedPlant *(association)*
Many-to-many link between `Plant` and `GardenBed`. Each row represents one placement of a plant inside a bed at grid coordinates (`grid_x`, `grid_y`, in inches from bed origin). Per-placement care tracking: last watered/fertilized/harvested, health notes, and growth `stage` (`seedling` → `growing` → `harvesting` → `done`).

### PlantLibrary
Shared reference catalog (~44 plants seeded). Contains growing specs (spacing, sunlight, water needs, days to germination/harvest), zone/temperature ranges, soil preferences, companion planting data (JSON arrays in `good_neighbors`/`bad_neighbors`), and how-to-grow guides (JSON). Enriched from Perenual API and Permapeople (CC BY-SA 4.0).

### CanvasPlant
A free-placed plant circle on the planner canvas — not inside any bed grid. Positioned by `pos_x`/`pos_y` (feet) with `radius_ft`. Display is either a `color` fill or an `image` (library image or custom upload in `static/canvas_plant_images/`). Optionally linked to a `Plant` instance and/or `PlantLibrary` entry.

### Task
To-do items scoped to any combination of garden, bed, and/or plant. `task_type` values: `seeding`, `transplanting`, `watering`, `fertilizing`, `weeding`, `mulching`, `harvest`, `pruning`, `other`. Tracks completion date separately from the `completed` flag.

### WeatherLog
Daily weather snapshots per garden. Unique constraint on `(garden_id, date)` prevents duplicates. `source` is `'api'` (fetched automatically) or `'manual'`. Used to calculate 7-day rainfall totals shown in the planner info panel.

---

## Key Design Notes

- **Plants are placed two ways:** inside a bed grid (`BedPlant`) or freely on the canvas (`CanvasPlant`). Both can reference the same `Plant` instance and `PlantLibrary` entry.
- **No migrations framework** — new columns are added via `ALTER TABLE` in `create_app()` on startup (`apps/api/app/main.py`).
- **PlantLibrary is shared** across all gardens. Edits to it (spacing, notes, image) affect every garden's display.
- **SQLite** database at `instance/garden.db`. Delete the file to fully reset (stops Flask first — the file is locked on Windows while running).
