from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Garden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(10), nullable=False, default='ft')
    zip_code = db.Column(db.String(10), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    usda_zone = db.Column(db.String(10), nullable=True)
    zone_temp_range = db.Column(db.String(50), nullable=True)
    last_frost_date = db.Column(db.Date, nullable=True)
    first_frost_date = db.Column(db.Date, nullable=True)
    frost_free = db.Column(db.Boolean, nullable=True)
    frost_station_id = db.Column(db.String(20), nullable=True)
    frost_station_name = db.Column(db.String(100), nullable=True)
    frost_station_distance_km = db.Column(db.Float, nullable=True)
    last_frost_dates_json = db.Column(db.Text, nullable=True)   # JSON {"10%": "MM/DD", ...}
    first_frost_dates_json = db.Column(db.Text, nullable=True)  # JSON {"10%": "MM/DD", ...}
    watering_frequency_days = db.Column(db.Integer, nullable=True, default=7)
    water_source = db.Column(db.String(30), nullable=True)  # rain/hose/drip/sprinkler
    background_image = db.Column(db.String(200), nullable=True)
    annotations = db.Column(db.Text, nullable=True)
    beds = db.relationship('GardenBed', backref='garden', lazy=True)
    plants = db.relationship('Plant', backref='garden', lazy=True)
    garden_tasks = db.relationship('Task', backref='task_garden',
                                   foreign_keys='Task.garden_id', lazy=True)
    weather_logs = db.relationship('WeatherLog', backref='garden_ref',
                                   order_by='WeatherLog.date.desc()', lazy=True)

    def __repr__(self):
        return f'<Garden {self.name}>'


class GardenBed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=True)
    width_ft = db.Column(db.Float, nullable=False, default=4.0)
    height_ft = db.Column(db.Float, nullable=False, default=8.0)
    depth_ft = db.Column(db.Float, nullable=True)
    pos_x = db.Column(db.Float, nullable=False, default=0.0)
    pos_y = db.Column(db.Float, nullable=False, default=0.0)
    soil_notes = db.Column(db.Text, nullable=True)
    soil_ph = db.Column(db.Float, nullable=True)
    clay_pct = db.Column(db.Float, nullable=True)
    compost_pct = db.Column(db.Float, nullable=True)
    sand_pct = db.Column(db.Float, nullable=True)
    bed_plants = db.relationship('BedPlant', backref='bed', lazy=True, cascade='all, delete-orphan')
    bed_tasks = db.relationship('Task', backref='task_bed',
                                foreign_keys='Task.bed_id', lazy=True)

    def __repr__(self):
        return f'<GardenBed {self.name}>'


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    planted_date = db.Column(db.Date)
    transplant_date = db.Column(db.Date)
    expected_harvest = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='planning')
    library_id = db.Column(db.Integer, db.ForeignKey('plant_library.id'), nullable=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=True)
    library_entry = db.relationship('PlantLibrary', backref='plants', lazy=True)
    tasks = db.relationship('Task', backref='plant', lazy=True)
    bed_plants = db.relationship('BedPlant', backref='plant', lazy=True)

    def __repr__(self):
        return f'<Plant {self.name}>'


class BedPlant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bed_id = db.Column(db.Integer, db.ForeignKey('garden_bed.id'), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    grid_x = db.Column(db.Integer, nullable=True)
    grid_y = db.Column(db.Integer, nullable=True)
    last_watered = db.Column(db.Date, nullable=True)
    last_fertilized = db.Column(db.Date, nullable=True)
    last_harvest = db.Column(db.Date, nullable=True)
    health_notes = db.Column(db.Text, nullable=True)
    stage = db.Column(db.String(20), nullable=True, default='seedling')

    def __repr__(self):
        return f'<BedPlant bed={self.bed_id} plant={self.plant_id}>'


class PlantLibrary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    scientific_name = db.Column(db.String(200), nullable=True)
    perenual_id = db.Column(db.Integer, nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)
    type = db.Column(db.String(50))          # vegetable, herb, fruit, flower
    spacing_in = db.Column(db.Integer)
    sunlight = db.Column(db.String(50))
    water = db.Column(db.String(50))
    days_to_germination = db.Column(db.Integer)
    days_to_harvest = db.Column(db.Integer)
    notes = db.Column(db.Text)
    # Extended info
    difficulty = db.Column(db.String(20))
    min_zone = db.Column(db.Integer)
    max_zone = db.Column(db.Integer)
    temp_min_f = db.Column(db.Integer)
    temp_max_f = db.Column(db.Integer)
    soil_ph_min = db.Column(db.Float)
    soil_ph_max = db.Column(db.Float)
    soil_type = db.Column(db.String(200))
    good_neighbors = db.Column(db.Text)       # JSON array
    bad_neighbors = db.Column(db.Text)        # JSON array
    sow_indoor_weeks = db.Column(db.Integer)  # weeks before last spring frost
    direct_sow_offset = db.Column(db.Integer) # weeks rel. to last frost (neg=before)
    transplant_offset = db.Column(db.Integer) # weeks after last frost to transplant
    how_to_grow = db.Column(db.Text)          # JSON {starting,seedling,vegetative,flowering,harvest}
    faqs = db.Column(db.Text)                 # JSON [{q,a}]
    nutrition = db.Column(db.Text)            # JSON nutrition data
    usda_fdc_id = db.Column(db.Integer, nullable=True)  # USDA FoodData Central ID
    # Permapeople (CC BY-SA 4.0 — https://permapeople.org)
    permapeople_id          = db.Column(db.Integer, nullable=True)
    permapeople_link        = db.Column(db.String(200), nullable=True)
    permapeople_description = db.Column(db.Text, nullable=True)
    family                  = db.Column(db.String(100), nullable=True)
    layer                   = db.Column(db.String(100), nullable=True)
    edible_parts            = db.Column(db.String(200), nullable=True)
    # OpenFarm (CC0 — archived via Wayback Machine)
    openfarm_id             = db.Column(db.String(30), nullable=True)
    openfarm_slug           = db.Column(db.String(100), nullable=True)
    # Trefle (https://trefle.io)
    trefle_id             = db.Column(db.Integer, nullable=True)
    trefle_slug           = db.Column(db.String(100), nullable=True)
    toxicity              = db.Column(db.String(20), nullable=True)    # none/low/medium/high
    duration              = db.Column(db.String(50), nullable=True)    # Annual/Biennial/Perennial
    ligneous_type         = db.Column(db.String(50), nullable=True)    # liana/subshrub/shrub/tree/parasite
    growth_habit          = db.Column(db.String(100), nullable=True)
    growth_form           = db.Column(db.String(100), nullable=True)
    growth_rate           = db.Column(db.String(50), nullable=True)    # slow/moderate/fast
    nitrogen_fixation     = db.Column(db.String(30), nullable=True)
    vegetable             = db.Column(db.Boolean, nullable=True)
    observations          = db.Column(db.Text, nullable=True)
    average_height_cm     = db.Column(db.Integer, nullable=True)
    maximum_height_cm     = db.Column(db.Integer, nullable=True)
    spread_cm             = db.Column(db.Integer, nullable=True)
    row_spacing_cm        = db.Column(db.Integer, nullable=True)
    minimum_root_depth_cm = db.Column(db.Integer, nullable=True)
    soil_nutriments       = db.Column(db.Integer, nullable=True)       # 0–10 (oligotrophic→hypereutrophic)
    soil_salinity         = db.Column(db.Integer, nullable=True)       # 0–10 (untolerant→hyperhaline)
    atmospheric_humidity  = db.Column(db.Integer, nullable=True)       # 0–10 (≤10%→≥90%)
    precipitation_min_mm  = db.Column(db.Integer, nullable=True)
    precipitation_max_mm  = db.Column(db.Integer, nullable=True)
    bloom_months          = db.Column(db.Text, nullable=True)          # JSON array e.g. [5,6,7]
    fruit_months          = db.Column(db.Text, nullable=True)          # JSON array
    growth_months         = db.Column(db.Text, nullable=True)          # JSON array
    flower_color          = db.Column(db.String(100), nullable=True)
    flower_conspicuous    = db.Column(db.Boolean, nullable=True)
    foliage_color         = db.Column(db.String(100), nullable=True)
    foliage_texture       = db.Column(db.String(30), nullable=True)    # fine/medium/coarse
    leaf_retention        = db.Column(db.Boolean, nullable=True)       # True=evergreen
    fruit_color           = db.Column(db.String(100), nullable=True)
    fruit_conspicuous     = db.Column(db.Boolean, nullable=True)
    fruit_shape           = db.Column(db.String(100), nullable=True)
    seed_persistence      = db.Column(db.Boolean, nullable=True)
    # Perenual (https://perenual.com)
    poisonous_to_pets    = db.Column(db.Boolean, nullable=True)
    poisonous_to_humans  = db.Column(db.Boolean, nullable=True)
    drought_tolerant     = db.Column(db.Boolean, nullable=True)
    salt_tolerant        = db.Column(db.Boolean, nullable=True)
    thorny               = db.Column(db.Boolean, nullable=True)
    invasive             = db.Column(db.Boolean, nullable=True)
    rare                 = db.Column(db.Boolean, nullable=True)
    tropical             = db.Column(db.Boolean, nullable=True)
    indoor               = db.Column(db.Boolean, nullable=True)
    cuisine              = db.Column(db.Boolean, nullable=True)
    medicinal            = db.Column(db.Boolean, nullable=True)
    attracts             = db.Column(db.Text, nullable=True)       # JSON array e.g. ["bees","butterflies"]
    propagation_methods  = db.Column(db.Text, nullable=True)       # JSON array e.g. ["Seed","Division"]
    harvest_season       = db.Column(db.String(50), nullable=True) # Spring/Summer/Fall/Winter
    harvest_method       = db.Column(db.String(100), nullable=True)
    fruiting_season      = db.Column(db.String(50), nullable=True)
    pruning_months       = db.Column(db.Text, nullable=True)       # JSON array of month names
    images = db.relationship('PlantLibraryImage', backref='library_entry',
                             lazy=True, cascade='all, delete-orphan',
                             order_by='PlantLibraryImage.created_at')

    def __repr__(self):
        return f'<PlantLibrary {self.name}>'


class PlantLibraryImage(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    plant_library_id = db.Column(db.Integer, db.ForeignKey('plant_library.id'), nullable=False)
    filename         = db.Column(db.String(200), nullable=False)
    source           = db.Column(db.String(30), nullable=False)  # manual, perenual, wikimedia, inaturalist, openverse, pexels
    source_url       = db.Column(db.Text, nullable=True)
    attribution      = db.Column(db.Text, nullable=True)         # e.g. "Author / CC-BY-SA 4.0"
    file_hash        = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 hex
    is_primary       = db.Column(db.Boolean, nullable=False, default=False)
    created_at       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<PlantLibraryImage plant={self.plant_library_id} {self.filename}>'


class CanvasPlant(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    garden_id    = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=False)
    library_id   = db.Column(db.Integer, db.ForeignKey('plant_library.id'), nullable=True)
    plant_id     = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=True)
    pos_x        = db.Column(db.Float, nullable=False, default=0.0)    # feet from canvas origin
    pos_y        = db.Column(db.Float, nullable=False, default=0.0)    # feet from canvas origin
    radius_ft    = db.Column(db.Float, nullable=False, default=1.0)    # radius in feet
    color        = db.Column(db.String(20), nullable=True, default='#5a9e54')
    display_mode = db.Column(db.String(10), nullable=False, default='color')  # 'color' or 'image'
    custom_image = db.Column(db.String(200), nullable=True)            # filename in static/canvas_plant_images/
    label        = db.Column(db.String(100), nullable=True)

    garden        = db.relationship('Garden', backref='canvas_plants', lazy=True)
    library_entry = db.relationship('PlantLibrary', backref='canvas_plants', lazy=True)
    plant         = db.relationship('Plant', backref='canvas_plants', lazy=True)

    def __repr__(self):
        return f'<CanvasPlant id={self.id}>'


class AppSetting(db.Model):
    """Single-user app settings stored as key/value pairs."""
    key   = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_date = db.Column(db.Date, nullable=True)
    task_type = db.Column(db.String(30), nullable=False, default='other')
    # task_type values: seeding, transplanting, weeding, watering, fertilizing, mulching, harvest, other
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=True)
    bed_id = db.Column(db.Integer, db.ForeignKey('garden_bed.id'), nullable=True)

    def __repr__(self):
        return f'<Task {self.title}>'


class WeatherLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('garden.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    rainfall_in = db.Column(db.Float, nullable=True)
    temp_high_f = db.Column(db.Float, nullable=True)
    temp_low_f = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(10), nullable=False, default='manual')
    # source: 'manual' or 'api'
    __table_args__ = (db.UniqueConstraint('garden_id', 'date',
                                          name='uq_weatherlog_garden_date'),)

    def __repr__(self):
        return f'<WeatherLog garden={self.garden_id} date={self.date}>'
