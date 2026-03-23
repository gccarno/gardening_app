from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class GardenBed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    plants = db.relationship('Plant', backref='bed', lazy=True)

    def __repr__(self):
        return f'<GardenBed {self.name}>'


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    planted_date = db.Column(db.Date)
    expected_harvest = db.Column(db.Date)
    bed_id = db.Column(db.Integer, db.ForeignKey('garden_bed.id'), nullable=True)
    tasks = db.relationship('Task', backref='plant', lazy=True)

    def __repr__(self):
        return f'<Plant {self.name}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=True)

    def __repr__(self):
        return f'<Task {self.title}>'
