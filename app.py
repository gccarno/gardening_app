from datetime import date
from flask import Flask, render_template, request, redirect, url_for
from models import db, GardenBed, Plant, Task


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

    # --- Garden Beds ---

    @app.route('/beds', methods=['GET', 'POST'])
    def beds():
        if request.method == 'POST':
            bed = GardenBed(
                name=request.form['name'],
                description=request.form.get('description'),
                location=request.form.get('location'),
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
                bed_id=request.form.get('bed_id') or None,
            )
            db.session.add(plant)
            db.session.commit()
            return redirect(url_for('plants'))
        all_plants = Plant.query.order_by(Plant.name).all()
        all_beds = GardenBed.query.order_by(GardenBed.name).all()
        return render_template('plants.html', plants=all_plants, beds=all_beds)

    @app.route('/plants/<int:plant_id>')
    def plant_detail(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        all_beds = GardenBed.query.order_by(GardenBed.name).all()
        return render_template('plant_detail.html', plant=plant, beds=all_beds)

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

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
