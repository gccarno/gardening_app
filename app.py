from datetime import date
from flask import Flask, render_template, request, redirect, url_for, jsonify
from models import db, Garden, GardenBed, Plant, Task, BedPlant


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garden.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # --- Dashboard ---

    @app.route('/')
    def index():
        upcoming_tasks = (
            Task.query
            .filter_by(completed=False)
            .order_by(Task.due_date.asc().nullslast())
            .limit(5)
            .all()
        )
        recent_plants = Plant.query.order_by(Plant.id.desc()).limit(5).all()
        return render_template('index.html', upcoming_tasks=upcoming_tasks, recent_plants=recent_plants)

    # --- Gardens ---

    @app.route('/gardens', methods=['GET', 'POST'])
    def gardens():
        if request.method == 'POST':
            garden = Garden(
                name=request.form['name'],
                description=request.form.get('description'),
                unit=request.form.get('unit', 'ft'),
            )
            db.session.add(garden)
            db.session.commit()
            return redirect(url_for('gardens'))
        all_gardens = Garden.query.order_by(Garden.name).all()
        return render_template('gardens.html', gardens=all_gardens)

    @app.route('/gardens/<int:garden_id>')
    def garden_detail(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        return render_template('garden_detail.html', garden=garden)

    @app.route('/gardens/<int:garden_id>/edit', methods=['POST'])
    def edit_garden(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        garden.name = request.form['name']
        garden.description = request.form.get('description')
        garden.unit = request.form.get('unit', 'ft')
        db.session.commit()
        return redirect(url_for('garden_detail', garden_id=garden.id))

    @app.route('/gardens/<int:garden_id>/delete', methods=['POST'])
    def delete_garden(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        db.session.delete(garden)
        db.session.commit()
        return redirect(url_for('gardens'))

    @app.route('/gardens/<int:garden_id>/planner')
    def planner(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        all_plants = Plant.query.order_by(Plant.name).all()
        px_per_unit = 60
        return render_template('planner.html', garden=garden, all_plants=all_plants, px_per_unit=px_per_unit)

    # --- Garden Beds ---

    @app.route('/beds', methods=['GET', 'POST'])
    def beds():
        if request.method == 'POST':
            width = request.form.get('width_ft')
            height = request.form.get('height_ft')
            bed = GardenBed(
                name=request.form['name'],
                description=request.form.get('description'),
                location=request.form.get('location'),
                width_ft=float(width) if width else 4.0,
                height_ft=float(height) if height else 8.0,
            )
            db.session.add(bed)
            db.session.commit()
            return redirect(url_for('beds'))
        all_beds = GardenBed.query.order_by(GardenBed.name).all()
        return render_template('beds.html', beds=all_beds)

    @app.route('/beds/<int:bed_id>')
    def bed_detail(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        return render_template('bed_detail.html', bed=bed)

    @app.route('/beds/<int:bed_id>/delete', methods=['POST'])
    def delete_bed(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        db.session.delete(bed)
        db.session.commit()
        return redirect(url_for('beds'))

    @app.route('/beds/<int:bed_id>/edit', methods=['POST'])
    def edit_bed(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        bed.name = request.form['name']
        bed.location = request.form.get('location')
        bed.description = request.form.get('description')
        db.session.commit()
        return redirect(url_for('bed_detail', bed_id=bed.id))

    # --- Plants ---

    @app.route('/plants', methods=['GET', 'POST'])
    def plants():
        if request.method == 'POST':
            planted = request.form.get('planted_date')
            harvest = request.form.get('expected_harvest')
            plant = Plant(
                name=request.form['name'],
                type=request.form.get('type'),
                notes=request.form.get('notes'),
                planted_date=date.fromisoformat(planted) if planted else None,
                expected_harvest=date.fromisoformat(harvest) if harvest else None,
            )
            db.session.add(plant)
            db.session.commit()
            return redirect(url_for('plants'))
        all_plants = Plant.query.order_by(Plant.name).all()
        return render_template('plants.html', plants=all_plants)

    @app.route('/plants/<int:plant_id>')
    def plant_detail(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        return render_template('plant_detail.html', plant=plant)

    @app.route('/plants/<int:plant_id>/edit', methods=['POST'])
    def edit_plant(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        planted = request.form.get('planted_date')
        harvest = request.form.get('expected_harvest')
        plant.name = request.form['name']
        plant.type = request.form.get('type')
        plant.notes = request.form.get('notes')
        plant.planted_date = date.fromisoformat(planted) if planted else None
        plant.expected_harvest = date.fromisoformat(harvest) if harvest else None
        db.session.commit()
        return redirect(url_for('plant_detail', plant_id=plant.id))

    @app.route('/plants/<int:plant_id>/delete', methods=['POST'])
    def delete_plant(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        db.session.delete(plant)
        db.session.commit()
        return redirect(url_for('plants'))

    # --- Tasks ---

    @app.route('/tasks', methods=['GET', 'POST'])
    def tasks():
        if request.method == 'POST':
            due = request.form.get('due_date')
            task = Task(
                title=request.form['title'],
                description=request.form.get('description'),
                due_date=date.fromisoformat(due) if due else None,
                plant_id=request.form.get('plant_id') or None,
            )
            db.session.add(task)
            db.session.commit()
            return redirect(url_for('tasks'))
        all_tasks = Task.query.order_by(Task.completed.asc(), Task.due_date.asc().nullslast()).all()
        all_plants = Plant.query.order_by(Plant.name).all()
        return render_template('tasks.html', tasks=all_tasks, plants=all_plants)

    @app.route('/tasks/<int:task_id>')
    def task_detail(task_id):
        task = Task.query.get_or_404(task_id)
        all_plants = Plant.query.order_by(Plant.name).all()
        return render_template('task_detail.html', task=task, plants=all_plants)

    @app.route('/tasks/<int:task_id>/edit', methods=['POST'])
    def edit_task(task_id):
        task = Task.query.get_or_404(task_id)
        due = request.form.get('due_date')
        task.title = request.form['title']
        task.description = request.form.get('description')
        task.due_date = date.fromisoformat(due) if due else None
        task.plant_id = request.form.get('plant_id') or None
        db.session.commit()
        return redirect(url_for('task_detail', task_id=task.id))

    @app.route('/tasks/<int:task_id>/complete', methods=['POST'])
    def complete_task(task_id):
        task = Task.query.get_or_404(task_id)
        task.completed = not task.completed
        db.session.commit()
        return redirect(url_for('tasks'))

    @app.route('/tasks/<int:task_id>/delete', methods=['POST'])
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        db.session.delete(task)
        db.session.commit()
        return redirect(url_for('tasks'))

    # --- JSON API ---

    @app.route('/api/beds', methods=['POST'])
    def api_create_bed():
        data = request.get_json(force=True)
        if not data or not data.get('name'):
            return jsonify({'error': 'name required'}), 400
        garden_id = data.get('garden_id')
        if not garden_id:
            return jsonify({'error': 'garden_id required'}), 400
        bed = GardenBed(
            name=data['name'],
            width_ft=float(data.get('width_ft', 4.0)),
            height_ft=float(data.get('height_ft', 8.0)),
            garden_id=int(garden_id),
        )
        db.session.add(bed)
        db.session.commit()
        return jsonify({'ok': True, 'bed': {
            'id': bed.id,
            'name': bed.name,
            'width_ft': bed.width_ft,
            'height_ft': bed.height_ft,
        }})

    @app.route('/api/beds/<int:bed_id>/position', methods=['POST'])
    def api_bed_position(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        data = request.get_json(force=True)
        if data is None or 'x' not in data or 'y' not in data:
            return jsonify({'error': 'x and y required'}), 400
        bed.pos_x = float(data['x'])
        bed.pos_y = float(data['y'])
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/beds/<int:bed_id>/assign-garden', methods=['POST'])
    def api_bed_assign_garden(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        data = request.get_json(force=True)
        if not data or 'garden_id' not in data:
            return jsonify({'error': 'garden_id required'}), 400
        bed.garden_id = int(data['garden_id'])
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/bedplants', methods=['POST'])
    def api_create_bedplant():
        data = request.get_json(force=True)
        if not data or 'bed_id' not in data or 'plant_id' not in data:
            return jsonify({'error': 'bed_id and plant_id required'}), 400
        bp = BedPlant(bed_id=int(data['bed_id']), plant_id=int(data['plant_id']))
        db.session.add(bp)
        db.session.commit()
        return jsonify({'ok': True, 'id': bp.id})

    @app.route('/api/bedplants/<int:bp_id>/delete', methods=['POST'])
    def api_delete_bedplant(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        db.session.delete(bp)
        db.session.commit()
        return jsonify({'ok': True})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
