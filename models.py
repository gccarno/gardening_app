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
    beds = db.relationship('GardenBed', backref='garden', lazy=True)

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
    bed_plants = db.relationship('BedPlant', backref='bed', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<GardenBed {self.name}>'


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    planted_date = db.Column(db.Date)
    expected_harvest = db.Column(db.Date)
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

    def __repr__(self):
        return f'<BedPlant bed={self.bed_id} plant={self.plant_id}>'


class PlantLibrary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    scientific_name = db.Column(db.String(200), nullable=True)
    perenual_id = db.Column(db.Integer, nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)
    type = db.Column(db.String(50))          # vegetable, herb, fruit, flower
    spacing_in = db.Column(db.Integer)       # recommended spacing in inches
    sunlight = db.Column(db.String(50))      # Full sun, Partial shade, Full shade
    water = db.Column(db.String(50))         # Low, Moderate, High
    days_to_germination = db.Column(db.Integer)
    days_to_harvest = db.Column(db.Integer)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<PlantLibrary {self.name}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=True)

    def __repr__(self):
        return f'<Task {self.title}>'
