"""
SQLAlchemy models for the garden app — plain SQLAlchemy (no Flask-SQLAlchemy).
These are identical in structure to apps/api/app/db/models.py; the only change
is replacing Flask-SQLAlchemy's db.Model / db.Column / db.relationship with
standard SQLAlchemy equivalents.
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, backref, relationship


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
    background_color       = Column(String(20), nullable=True)
    background_pattern     = Column(String(30), nullable=True)   # 'grass'|'mulch'|'wood_chips'|'straw'|'dirt'
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
    garden_id   = Column(Integer, ForeignKey('garden.id'), nullable=True, index=True)
    width_ft    = Column(Float, nullable=False, default=4.0)
    height_ft   = Column(Float, nullable=False, default=8.0)
    depth_ft    = Column(Float, nullable=True)
    pos_x       = Column(Float, nullable=False, default=0.0)
    pos_y       = Column(Float, nullable=False, default=0.0)
    soil_notes       = Column(Text, nullable=True)
    soil_ph          = Column(Float, nullable=True)
    clay_pct         = Column(Float, nullable=True)
    compost_pct      = Column(Float, nullable=True)
    sand_pct         = Column(Float, nullable=True)
    color               = Column(String(20), nullable=True)
    background_image    = Column(String(200), nullable=True)
    background_pattern  = Column(String(30), nullable=True)   # 'grass'|'mulch'|'wood_chips'|'straw'|'dirt'
    last_weeded         = Column(Date, nullable=True)

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
    last_watered     = Column(Date, nullable=True)
    watering_amount  = Column(String(20), nullable=True)   # 'light' | 'moderate' | 'heavy'
    last_fertilized  = Column(Date, nullable=True)
    fertilizer_type  = Column(String(50), nullable=True)   # balanced/nitrogen/phosphorus/potassium/organic/other
    fertilizer_npk   = Column(String(20), nullable=True)   # e.g. '10-10-10'
    succession_label = Column(String(50), nullable=True)
    library_id       = Column(Integer, ForeignKey('plant_library.id'), nullable=True, index=True)
    garden_id        = Column(Integer, ForeignKey('garden.id'), nullable=True, index=True)

    library_entry = relationship('PlantLibrary', backref='plants', lazy=True)
    tasks         = relationship('Task', backref='plant', lazy=True)
    bed_plants    = relationship('BedPlant', backref='plant', lazy=True,
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Plant {self.name}>'


class BedPlant(Base):
    __tablename__ = 'bed_plant'

    id             = Column(Integer, primary_key=True)
    bed_id         = Column(Integer, ForeignKey('garden_bed.id'), nullable=False, index=True)
    plant_id       = Column(Integer, ForeignKey('plant.id'), nullable=False, index=True)
    grid_x         = Column(Integer, nullable=True)
    grid_y         = Column(Integer, nullable=True)
    last_watered     = Column(Date, nullable=True)
    watering_amount  = Column(String(20), nullable=True)
    last_fertilized  = Column(Date, nullable=True)
    fertilizer_type  = Column(String(50), nullable=True)
    fertilizer_npk   = Column(String(20), nullable=True)
    last_harvest     = Column(Date, nullable=True)
    health_notes     = Column(Text, nullable=True)
    stage            = Column(String(20), nullable=True, default='seedling')

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

    # Custom / cloned plant tracking
    cloned_from_id = Column(Integer, ForeignKey('plant_library.id'), nullable=True)
    is_custom      = Column(Boolean, default=False)

    images = relationship('PlantLibraryImage', backref='library_entry',
                          lazy=True, cascade='all, delete-orphan',
                          order_by='PlantLibraryImage.created_at')
    cloned_from = relationship('PlantLibrary', remote_side='PlantLibrary.id',
                               foreign_keys='PlantLibrary.cloned_from_id')

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
    garden_id    = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    library_id   = Column(Integer, ForeignKey('plant_library.id'), nullable=True, index=True)
    plant_id     = Column(Integer, ForeignKey('plant.id'), nullable=True, index=True)
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
    plant_id  = Column(Integer, ForeignKey('plant.id'), nullable=True, index=True)
    garden_id = Column(Integer, ForeignKey('garden.id'), nullable=True, index=True)
    bed_id    = Column(Integer, ForeignKey('garden_bed.id'), nullable=True, index=True)

    def __repr__(self):
        return f'<Task {self.title}>'


class WeatherLog(Base):
    __tablename__ = 'weather_log'

    id           = Column(Integer, primary_key=True)
    garden_id    = Column(Integer, ForeignKey('garden.id'), nullable=False)
    date         = Column(Date, nullable=False)
    rainfall_in  = Column(Float, nullable=True)
    temp_high_f  = Column(Float, nullable=True)
    temp_low_f   = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    et0_mm       = Column(Float, nullable=True)
    source       = Column(String(10), nullable=False, default='manual')  # 'manual' or 'api'

    __table_args__ = (
        UniqueConstraint('garden_id', 'date', name='uq_weatherlog_garden_date'),
    )

    def __repr__(self):
        return f'<WeatherLog garden={self.garden_id} date={self.date}>'


class WateringEvent(Base):
    """
    Append-only log of actual watering actions, written alongside the existing
    last_watered/watering_amount mutations on Plant/BedPlant. Kept for 7 days
    operationally (pruned by the nightly ml_snapshot job); the ML flywheel's
    durable record of "was this bed watered" lives in MlWateringSnapshot instead.
    """
    __tablename__ = 'watering_event'

    id         = Column(Integer, primary_key=True)
    garden_id  = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    bed_id     = Column(Integer, ForeignKey('garden_bed.id'), nullable=True, index=True)
    event_date = Column(Date, nullable=False)
    amount     = Column(String(20), nullable=True)   # 'light' | 'moderate' | 'heavy'
    source     = Column(String(10), nullable=False, default='user')  # 'user' or 'bulk'
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<WateringEvent garden={self.garden_id} bed={self.bed_id} date={self.event_date}>'


class MlWateringSnapshot(Base):
    """
    One row per bed per day: the feature vector the watering model saw (or
    would see), what the rule engine and model each said, and — backfilled the
    following night — what actually happened. Never pruned: this is the
    accumulating training/monitoring store (the "flywheel"), separate from the
    7-day operational WeatherLog/WateringEvent window.
    """
    __tablename__ = 'ml_watering_snapshot'

    id            = Column(Integer, primary_key=True)
    garden_id     = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    bed_id        = Column(Integer, ForeignKey('garden_bed.id'), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False)

    # Features
    rain_7d_mm                = Column(Float, nullable=True)
    et0_7d_mm                 = Column(Float, nullable=True)
    temp_high_f               = Column(Float, nullable=True)
    temp_low_f                = Column(Float, nullable=True)
    humidity_pct              = Column(Float, nullable=True)
    forecast_precip_mm_d0     = Column(Float, nullable=True)
    forecast_precip_prob_d0   = Column(Float, nullable=True)
    forecast_precip_mm_d1_d2  = Column(Float, nullable=True)
    forecast_temp_max_c       = Column(Float, nullable=True)
    days_since_watered        = Column(Integer, nullable=True)
    maturity_days             = Column(Integer, nullable=True)
    seedling_frac             = Column(Float, nullable=True)
    kc_avg                    = Column(Float, nullable=True)
    mm_day_avg                = Column(Float, nullable=True)
    sand_pct                  = Column(Float, nullable=True)
    clay_pct                  = Column(Float, nullable=True)
    bed_area_m2                = Column(Float, nullable=True)

    # Engine outputs at snapshot time
    rule_deficit_mm = Column(Float, nullable=True)
    rule_score      = Column(Integer, nullable=True)
    model_pred_mm   = Column(Float, nullable=True)
    model_used      = Column(Boolean, nullable=False, default=False)

    # Labels — backfilled the following night
    watered_next_day  = Column(Boolean, nullable=True)
    watered_amount    = Column(String(20), nullable=True)
    rain_next_day_mm  = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('garden_id', 'bed_id', 'snapshot_date', name='uq_ml_snapshot_garden_bed_date'),
    )

    def __repr__(self):
        return f'<MlWateringSnapshot garden={self.garden_id} bed={self.bed_id} date={self.snapshot_date}>'


class SeedTray(Base):
    __tablename__ = 'seed_tray'

    id                   = Column(Integer, primary_key=True)
    garden_id            = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    library_id           = Column(Integer, ForeignKey('plant_library.id'), nullable=True, index=True)
    plant_name           = Column(String(100), nullable=False)
    slot_number          = Column(Integer, nullable=False)   # 1-24
    sow_date             = Column(Date, nullable=True)
    germination_date     = Column(Date, nullable=True)
    transplant_ready_date = Column(Date, nullable=True)
    # stage: sowing → germinating → seedling → hardening → ready
    stage                = Column(String(20), nullable=False, default='sowing')
    notes                = Column(Text, nullable=True)
    created_at           = Column(DateTime, nullable=False, default=datetime.utcnow)

    garden        = relationship('Garden', backref='seed_trays', lazy=True)
    library_entry = relationship('PlantLibrary', backref='seed_trays', lazy=True)

    def __repr__(self):
        return f'<SeedTray slot={self.slot_number} plant={self.plant_name}>'


OBSERVATION_TYPES = [
    'healthy', 'new_growth', 'flowering', 'harvest_ready',
    'yellowing', 'wilting', 'pest_damage', 'disease',
]


class PlantObservation(Base):
    __tablename__ = 'plant_observation'

    id               = Column(Integer, primary_key=True)
    bed_plant_id     = Column(Integer, ForeignKey('bed_plant.id'), nullable=False, index=True)
    observation_date = Column(Date, nullable=False)
    observation_type = Column(String(30), nullable=False)  # see OBSERVATION_TYPES
    severity         = Column(Integer, nullable=False, default=3)  # 1 (minor) - 5 (severe)
    notes            = Column(Text, nullable=True)
    image_filename   = Column(String(200), nullable=True)
    created_at       = Column(DateTime, nullable=False, default=datetime.utcnow)

    bed_plant = relationship(
        'BedPlant',
        backref=backref('observations', cascade='all, delete-orphan'),
        lazy=True,
    )

    def __repr__(self):
        return f'<PlantObservation bp={self.bed_plant_id} type={self.observation_type}>'


class JournalEntry(Base):
    __tablename__ = 'journal_entry'

    id         = Column(Integer, primary_key=True)
    garden_id  = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    plant_id   = Column(Integer, ForeignKey('plant.id'), nullable=True, index=True)
    entry_date = Column(Date, nullable=False)
    title      = Column(String(200), nullable=False)
    body       = Column(Text, nullable=True)
    tags       = Column(Text, nullable=True)        # JSON array of strings
    image_filename = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    garden = relationship('Garden', backref='journal_entries', lazy=True)
    plant  = relationship('Plant', backref='journal_entries', lazy=True)

    def __repr__(self):
        return f'<JournalEntry {self.title}>'


class CompostBin(Base):
    __tablename__ = 'compost_bin'

    id                   = Column(Integer, primary_key=True)
    garden_id            = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    name                 = Column(String(100), nullable=False)
    started_date         = Column(Date, nullable=True)
    estimated_ready_date = Column(Date, nullable=True)
    # stage: building → active → curing → ready
    stage                = Column(String(20), nullable=False, default='building')
    notes                = Column(Text, nullable=True)
    materials            = Column(Text, nullable=True)  # JSON array: [{material, date_added, quantity_lbs}]
    created_at           = Column(DateTime, nullable=False, default=datetime.utcnow)

    garden = relationship('Garden', backref='compost_bins', lazy=True)

    def __repr__(self):
        return f'<CompostBin {self.name}>'


# ── Auth & sharing ────────────────────────────────────────────────────────────

GARDEN_ROLES = ['viewer', 'editor', 'owner']


class User(Base):
    __tablename__ = 'app_user'  # 'user' is a reserved word in Postgres

    id            = Column(Integer, primary_key=True)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    display_name  = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)

    tokens      = relationship('AuthToken', backref='user',
                               cascade='all, delete-orphan', lazy=True)
    memberships = relationship('GardenMember', backref='user',
                               cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


class AuthToken(Base):
    """Opaque bearer token, stored as a SHA-256 hash. Delete row to revoke."""
    __tablename__ = 'auth_token'

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey('app_user.id'), nullable=False, index=True)
    token_hash   = Column(String(64), nullable=False, unique=True, index=True)
    created_at   = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class GardenMember(Base):
    __tablename__ = 'garden_member'
    __table_args__ = (UniqueConstraint('garden_id', 'user_id', name='uq_garden_member'),)

    id        = Column(Integer, primary_key=True)
    garden_id = Column(Integer, ForeignKey('garden.id'), nullable=False, index=True)
    user_id   = Column(Integer, ForeignKey('app_user.id'), nullable=False, index=True)
    role      = Column(String(10), nullable=False, default='viewer')  # see GARDEN_ROLES

    garden = relationship(
        'Garden',
        backref=backref('members', cascade='all, delete-orphan'),
        lazy=True,
    )

    def __repr__(self):
        return f'<GardenMember g={self.garden_id} u={self.user_id} {self.role}>'


class GuideChunk(Base):
    """A chunk of an indexed growing guide, with its embedding.

    Replaces the ChromaDB store that used to live at apps/api/instance/rag_db/.
    That store was gitignored (so it never reached Render) and opening it pulled
    onnxruntime plus a 79 MB embedding model into the request process. Vectors
    live here instead and embeddings are an API call — see
    apps/ml_service/app/embed_provider.py.

    Built by scripts/build_rag.py; read by the search_growing_guides chat tool.
    """
    __tablename__ = 'guide_chunk'

    id         = Column(Integer, primary_key=True)
    text       = Column(Text, nullable=False)
    source     = Column(String(200))                  # e.g. 'TAMU Easy Gardening Guide'
    plant_name = Column(String(100))                  # '' for the multi-plant books
    region     = Column(String(50), index=True)       # filter key; see _STATE_REGION
    page       = Column(Integer, nullable=True)       # books only; NULL for TAMU guides
    # Width must match EMBED_DIMS. Changing it needs a migration + full re-index.
    embedding  = Column(Vector(768), nullable=False)

    # Declared here as well as in the migration so `alembic check` sees a model
    # that matches the database. The migration builds this index with raw SQL
    # (autogenerate cannot emit an operator class), and without this the check
    # reads the index as drift and tries to drop it.
    __table_args__ = (
        Index(
            'ix_guide_chunk_embedding',
            'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
        ),
    )

    def __repr__(self):
        return f'<GuideChunk {self.id} {self.source!r} p={self.page}>'
