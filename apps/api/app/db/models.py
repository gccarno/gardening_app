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
    # Permapeople (CC BY-SA 4.0 — https://permapeople.org)
    permapeople_id          = db.Column(db.Integer, nullable=True)
    permapeople_link        = db.Column(db.String(200), nullable=True)
    permapeople_description = db.Column(db.Text, nullable=True)
    family                  = db.Column(db.String(100), nullable=True)
    layer                   = db.Column(db.String(100), nullable=True)
    edible_parts            = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<PlantLibrary {self.name}>'


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
