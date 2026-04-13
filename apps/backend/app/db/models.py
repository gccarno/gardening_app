"""
SQLAlchemy models for the garden app — plain SQLAlchemy (no Flask-SQLAlchemy).
These are identical in structure to apps/api/app/db/models.py; the only change
is replacing Flask-SQLAlchemy's db.Model / db.Column / db.relationship with
standard SQLAlchemy equivalents.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Garden(Base):
    __tablename__ = 'garden'

    id                     = Column(Integer, primary_key=True)
    name                   = Column(String(100), nullable=False)
    description            = Column(Text)
    unit                   = Column(String(10), nullable=False, default='ft')
    zip_code               = Column(String(10), nullable=True)
    city                   = Column(String(100), nullable=True)
    state                  = Column(String(50), nullable=True)
    latitude               = Column(Float, nullable=True)
    longitude              = Column(Float, nullable=True)
    usda_zone              = Column(String(10), nullable=True)
    zone_temp_range        = Column(String(50), nullable=True)
    last_frost_date        = Column(Date, nullable=True)
    first_frost_date       = Column(Date, nullable=True)
    frost_free             = Column(Boolean, nullable=True)
    frost_station_id       = Column(String(20), nullable=True)
    frost_station_name     = Column(String(100), nullable=True)
    frost_station_distance_km = Column(Float, nullable=True)
    last_frost_dates_json  = Column(Text, nullable=True)   # JSON {"10%": "MM/DD", ...}
    first_frost_dates_json = Column(Text, nullable=True)   # JSON {"10%": "MM/DD", ...}
    watering_frequency_days = Column(Integer, nullable=True, default=7)
    water_source           = Column(String(30), nullable=True)  # rain/hose/drip/sprinkler
    background_image       = Column(String(200), nullable=True)
    annotations            = Column(Text, nullable=True)

    beds         = relationship('GardenBed', backref='garden', lazy=True)
    plants       = relationship('Plant', backref='garden', lazy=True)
    garden_tasks = relationship('Task', backref='task_garden',
                                foreign_keys='Task.garden_id', lazy=True)
    weather_logs = relationship('WeatherLog', backref='garden_ref',
                                order_by='WeatherLog.date.desc()', lazy=True)

    def __repr__(self):
        return f'<Garden {self.name}>'


class GardenBed(Base):
    __tablename__ = 'garden_bed'

    id          = Column(Integer, primary_key=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text)
    location    = Column(String(200))
    garden_id   = Column(Integer, ForeignKey('garden.id'), nullable=True)
    width_ft    = Column(Float, nullable=False, default=4.0)
    height_ft   = Column(Float, nullable=False, default=8.0)
    depth_ft    = Column(Float, nullable=True)
    pos_x       = Column(Float, nullable=False, default=0.0)
    pos_y       = Column(Float, nullable=False, default=0.0)
    soil_notes  = Column(Text, nullable=True)
    soil_ph     = Column(Float, nullable=True)
    clay_pct    = Column(Float, nullable=True)
    compost_pct = Column(Float, nullable=True)
    sand_pct    = Column(Float, nullable=True)

    bed_plants = relationship('BedPlant', backref='bed', lazy=True, cascade='all, delete-orphan')
    bed_tasks  = relationship('Task', backref='task_bed',
                              foreign_keys='Task.bed_id', lazy=True)

    def __repr__(self):
        return f'<GardenBed {self.name}>'


class Plant(Base):
    __tablename__ = 'plant'

    id               = Column(Integer, primary_key=True)
    name             = Column(String(100), nullable=False)
    type             = Column(String(100))
    notes            = Column(Text)
    planted_date     = Column(Date)
    transplant_date  = Column(Date)
    expected_harvest = Column(Date)
    status           = Column(String(20), nullable=False, default='planning')
    library_id       = Column(Integer, ForeignKey('plant_library.id'), nullable=True)
    garden_id        = Column(Integer, ForeignKey('garden.id'), nullable=True)

    library_entry = relationship('PlantLibrary', backref='plants', lazy=True)
    tasks         = relationship('Task', backref='plant', lazy=True)
    bed_plants    = relationship('BedPlant', backref='plant', lazy=True)

    def __repr__(self):
        return f'<Plant {self.name}>'


class BedPlant(Base):
    __tablename__ = 'bed_plant'

    id             = Column(Integer, primary_key=True)
    bed_id         = Column(Integer, ForeignKey('garden_bed.id'), nullable=False)
    plant_id       = Column(Integer, ForeignKey('plant.id'), nullable=False)
    grid_x         = Column(Integer, nullable=True)
    grid_y         = Column(Integer, nullable=True)
    last_watered   = Column(Date, nullable=True)
    last_fertilized = Column(Date, nullable=True)
    last_harvest   = Column(Date, nullable=True)
    health_notes   = Column(Text, nullable=True)
    stage          = Column(String(20), nullable=True, default='seedling')

    def __repr__(self):
        return f'<BedPlant bed={self.bed_id} plant={self.plant_id}>'


class PlantLibrary(Base):
    __tablename__ = 'plant_library'

    id              = Column(Integer, primary_key=True)
    name            = Column(String(100), nullable=False)
    scientific_name = Column(String(200), nullable=True)
    perenual_id     = Column(Integer, nullable=True)
    image_filename  = Column(String(100), nullable=True)
    type            = Column(String(50))       # vegetable, herb, fruit, flower
    spacing_in      = Column(Integer)
    sunlight        = Column(String(50))
    water           = Column(String(50))
    days_to_germination = Column(Integer)
    days_to_harvest     = Column(Integer)
    notes               = Column(Text)
    difficulty          = Column(String(20))
    min_zone            = Column(Integer)
    max_zone            = Column(Integer)
    temp_min_f          = Column(Integer)
    temp_max_f          = Column(Integer)
    soil_ph_min         = Column(Float)
    soil_ph_max         = Column(Float)
    soil_type           = Column(String(200))
    good_neighbors      = Column(Text)       # JSON array
    bad_neighbors       = Column(Text)       # JSON array
    sow_indoor_weeks    = Column(Integer)    # weeks before last spring frost
    direct_sow_offset   = Column(Integer)   # weeks rel. to last frost (neg=before)
    transplant_offset   = Column(Integer)   # weeks after last frost to transplant
    how_to_grow         = Column(Text)      # JSON {starting,seedling,vegetative,flowering,harvest}
    faqs                = Column(Text)      # JSON [{q,a}]
    nutrition           = Column(Text)      # JSON nutrition data
    usda_fdc_id         = Column(Integer, nullable=True)
    # Permapeople (CC BY-SA 4.0)
    permapeople_id          = Column(Integer, nullable=True)
    permapeople_link        = Column(String(200), nullable=True)
    permapeople_description = Column(Text, nullable=True)
    family                  = Column(String(100), nullable=True)
    layer                   = Column(String(100), nullable=True)
    edible_parts            = Column(String(200), nullable=True)
    # OpenFarm (CC0)
    openfarm_id   = Column(String(30), nullable=True)
    openfarm_slug = Column(String(100), nullable=True)
    # Trefle
    trefle_id             = Column(Integer, nullable=True)
    trefle_slug           = Column(String(100), nullable=True)
    genus                 = Column(String(100), nullable=True)
    edible                = Column(Boolean, nullable=True)
    toxicity              = Column(String(20), nullable=True)
    duration              = Column(String(50), nullable=True)
    ligneous_type         = Column(String(50), nullable=True)
    growth_habit          = Column(String(100), nullable=True)
    growth_form           = Column(String(100), nullable=True)
    growth_rate           = Column(String(50), nullable=True)
    nitrogen_fixation     = Column(String(30), nullable=True)
    vegetable             = Column(Boolean, nullable=True)
    observations          = Column(Text, nullable=True)
    average_height_cm     = Column(Integer, nullable=True)
    maximum_height_cm     = Column(Integer, nullable=True)
    spread_cm             = Column(Integer, nullable=True)
    row_spacing_cm        = Column(Integer, nullable=True)
    minimum_root_depth_cm = Column(Integer, nullable=True)
    soil_nutriments       = Column(Integer, nullable=True)
    soil_salinity         = Column(Integer, nullable=True)
    atmospheric_humidity  = Column(Integer, nullable=True)
    precipitation_min_mm  = Column(Integer, nullable=True)
    precipitation_max_mm  = Column(Integer, nullable=True)
    bloom_months          = Column(Text, nullable=True)   # JSON array
    fruit_months          = Column(Text, nullable=True)   # JSON array
    growth_months         = Column(Text, nullable=True)   # JSON array
    flower_color          = Column(String(100), nullable=True)
    flower_conspicuous    = Column(Boolean, nullable=True)
    foliage_color         = Column(String(100), nullable=True)
    foliage_texture       = Column(String(30), nullable=True)
    leaf_retention        = Column(Boolean, nullable=True)
    fruit_color           = Column(String(100), nullable=True)
    fruit_conspicuous     = Column(Boolean, nullable=True)
    fruit_shape           = Column(String(100), nullable=True)
    seed_persistence      = Column(Boolean, nullable=True)
    # Perenual
    poisonous_to_pets   = Column(Boolean, nullable=True)
    poisonous_to_humans = Column(Boolean, nullable=True)
    drought_tolerant    = Column(Boolean, nullable=True)
    salt_tolerant       = Column(Boolean, nullable=True)
    thorny              = Column(Boolean, nullable=True)
    invasive            = Column(Boolean, nullable=True)
    rare                = Column(Boolean, nullable=True)
    tropical            = Column(Boolean, nullable=True)
    indoor              = Column(Boolean, nullable=True)
    cuisine             = Column(Boolean, nullable=True)
    medicinal           = Column(Boolean, nullable=True)
    attracts            = Column(Text, nullable=True)       # JSON array
    propagation_methods = Column(Text, nullable=True)      # JSON array
    harvest_season      = Column(String(50), nullable=True)
    harvest_method      = Column(String(100), nullable=True)
    fruiting_season     = Column(String(50), nullable=True)
    pruning_months      = Column(Text, nullable=True)      # JSON array

    images = relationship('PlantLibraryImage', backref='library_entry',
                          lazy=True, cascade='all, delete-orphan',
                          order_by='PlantLibraryImage.created_at')

    def __repr__(self):
        return f'<PlantLibrary {self.name}>'


class PlantLibraryImage(Base):
    __tablename__ = 'plant_library_image'

    id               = Column(Integer, primary_key=True)
    plant_library_id = Column(Integer, ForeignKey('plant_library.id'), nullable=False)
    filename         = Column(String(200), nullable=False)
    source           = Column(String(30), nullable=False)  # manual/perenual/wikimedia/inaturalist/openverse/pexels
    source_url       = Column(Text, nullable=True)
    attribution      = Column(Text, nullable=True)
    file_hash        = Column(String(64), unique=True, nullable=False)  # SHA-256
    is_primary       = Column(Boolean, nullable=False, default=False)
    created_at       = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<PlantLibraryImage plant={self.plant_library_id} {self.filename}>'


class CanvasPlant(Base):
    __tablename__ = 'canvas_plant'

    id           = Column(Integer, primary_key=True)
    garden_id    = Column(Integer, ForeignKey('garden.id'), nullable=False)
    library_id   = Column(Integer, ForeignKey('plant_library.id'), nullable=True)
    plant_id     = Column(Integer, ForeignKey('plant.id'), nullable=True)
    pos_x        = Column(Float, nullable=False, default=0.0)
    pos_y        = Column(Float, nullable=False, default=0.0)
    radius_ft    = Column(Float, nullable=False, default=1.0)
    color        = Column(String(20), nullable=True, default='#5a9e54')
    display_mode = Column(String(10), nullable=False, default='color')  # 'color' or 'image'
    custom_image = Column(String(200), nullable=True)
    label        = Column(String(100), nullable=True)

    garden        = relationship('Garden', backref='canvas_plants', lazy=True)
    library_entry = relationship('PlantLibrary', backref='canvas_plants', lazy=True)
    plant         = relationship('Plant', backref='canvas_plants', lazy=True)

    def __repr__(self):
        return f'<CanvasPlant id={self.id}>'


class AppSetting(Base):
    __tablename__ = 'app_setting'

    key   = Column(String(50), primary_key=True)
    value = Column(Text, nullable=True)

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'


class Task(Base):
    __tablename__ = 'task'

    id             = Column(Integer, primary_key=True)
    title          = Column(String(200), nullable=False)
    description    = Column(Text)
    due_date       = Column(Date)
    completed      = Column(Boolean, default=False, nullable=False)
    completed_date = Column(Date, nullable=True)
    task_type      = Column(String(30), nullable=False, default='other')
    # task_type: seeding, transplanting, weeding, watering, fertilizing, mulching, harvest, other
    plant_id  = Column(Integer, ForeignKey('plant.id'), nullable=True)
    garden_id = Column(Integer, ForeignKey('garden.id'), nullable=True)
    bed_id    = Column(Integer, ForeignKey('garden_bed.id'), nullable=True)

    def __repr__(self):
        return f'<Task {self.title}>'


class WeatherLog(Base):
    __tablename__ = 'weather_log'

    id          = Column(Integer, primary_key=True)
    garden_id   = Column(Integer, ForeignKey('garden.id'), nullable=False)
    date        = Column(Date, nullable=False)
    rainfall_in = Column(Float, nullable=True)
    temp_high_f = Column(Float, nullable=True)
    temp_low_f  = Column(Float, nullable=True)
    source      = Column(String(10), nullable=False, default='manual')  # 'manual' or 'api'

    __table_args__ = (
        UniqueConstraint('garden_id', 'date', name='uq_weatherlog_garden_date'),
    )

    def __repr__(self):
        return f'<WeatherLog garden={self.garden_id} date={self.date}>'
