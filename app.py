import os
from collections import defaultdict
from datetime import date, timedelta
import requests as http
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify
from models import db, Garden, GardenBed, Plant, Task, BedPlant, PlantLibrary

load_dotenv()


_LIBRARY_SEED = [
    # --- Vegetables ---
    dict(name='Tomato', type='vegetable', spacing_in=24, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=70,
         notes='Start indoors 6–8 weeks before last frost. Days to harvest measured from transplant. Stake or cage plants. Consistent watering prevents blossom end rot.'),
    dict(name='Cherry Tomato', type='vegetable', spacing_in=18, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=60,
         notes='More prolific and forgiving than beefsteak types. Start indoors 6–8 weeks before last frost. Days to harvest from transplant.'),
    dict(name='Cucumber', type='vegetable', spacing_in=12, sunlight='Full sun', water='High',
         days_to_germination=7, days_to_harvest=55,
         notes='Direct sow after last frost or start indoors 3–4 weeks early. Trellis to save space. Harvest frequently to encourage production.'),
    dict(name='Zucchini', type='vegetable', spacing_in=36, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=50,
         notes='Direct sow after last frost. One or two plants supply a family. Harvest small (6–8 in) for best flavor.'),
    dict(name='Bell Pepper', type='vegetable', spacing_in=18, sunlight='Full sun', water='Moderate',
         days_to_germination=10, days_to_harvest=75,
         notes='Start indoors 8–10 weeks before last frost. Needs warm soil. Days to harvest from transplant.'),
    dict(name='Jalapeño', type='vegetable', spacing_in=18, sunlight='Full sun', water='Moderate',
         days_to_germination=10, days_to_harvest=75,
         notes='Start indoors 8–10 weeks before last frost. Allow to turn red for extra heat and sweetness.'),
    dict(name='Lettuce', type='vegetable', spacing_in=6, sunlight='Partial shade', water='Moderate',
         days_to_germination=7, days_to_harvest=45,
         notes='Succession sow every 2–3 weeks for continuous harvest. Bolts in heat; best in spring and fall. Cut-and-come-again varieties give multiple harvests.'),
    dict(name='Spinach', type='vegetable', spacing_in=4, sunlight='Partial shade', water='Moderate',
         days_to_germination=7, days_to_harvest=40,
         notes='Cool-season crop; sow in early spring or fall. Bolts quickly in heat. Harvest outer leaves to extend season.'),
    dict(name='Kale', type='vegetable', spacing_in=12, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=55,
         notes='Very cold-hardy; flavor improves after frost. Harvest outer leaves continuously. Can overwinter in mild climates.'),
    dict(name='Arugula', type='vegetable', spacing_in=4, sunlight='Partial shade', water='Moderate',
         days_to_germination=5, days_to_harvest=30,
         notes='Fast-growing cool-season green. Succession sow every 2–3 weeks. Becomes peppery and bolts in heat.'),
    dict(name='Swiss Chard', type='vegetable', spacing_in=6, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=50,
         notes='Heat and cold tolerant. Harvest outer leaves. Colorful stems make it ornamental as well.'),
    dict(name='Carrot', type='vegetable', spacing_in=3, sunlight='Full sun', water='Moderate',
         days_to_germination=14, days_to_harvest=70,
         notes='Direct sow only; does not transplant well. Needs loose, deep, rock-free soil. Thin to 3 in apart for best root development.'),
    dict(name='Radish', type='vegetable', spacing_in=2, sunlight='Full sun', water='Moderate',
         days_to_germination=5, days_to_harvest=25,
         notes='One of the fastest vegetables. Great for marking slow-germinating rows. Sow every 2 weeks for continuous harvest.'),
    dict(name='Beet', type='vegetable', spacing_in=4, sunlight='Full sun', water='Moderate',
         days_to_germination=10, days_to_harvest=55,
         notes='Direct sow. Both roots and greens are edible. Thin and eat thinnings as salad greens.'),
    dict(name='Green Bean', type='vegetable', spacing_in=6, sunlight='Full sun', water='Moderate',
         days_to_germination=8, days_to_harvest=55,
         notes='Direct sow after last frost. Bush types need no support. Pole types need a trellis but produce longer.'),
    dict(name='Pea', type='vegetable', spacing_in=4, sunlight='Full sun', water='Moderate',
         days_to_germination=9, days_to_harvest=60,
         notes='Direct sow as early as soil can be worked — tolerates light frost. Needs trellis or support. Harvest often to encourage production.'),
    dict(name='Broccoli', type='vegetable', spacing_in=18, sunlight='Full sun', water='High',
         days_to_germination=7, days_to_harvest=80,
         notes='Start indoors 6–8 weeks before transplanting. Cool-season crop; bolts in heat. Harvest central head before flowers open; side shoots follow.'),
    dict(name='Cauliflower', type='vegetable', spacing_in=18, sunlight='Full sun', water='High',
         days_to_germination=7, days_to_harvest=85,
         notes='Needs consistent moisture and cool temps. Blanch heads by tying outer leaves over them when head reaches golf-ball size.'),
    dict(name='Cabbage', type='vegetable', spacing_in=18, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=80,
         notes='Start indoors 6–8 weeks early. Cool-season crop. Heads may split if overwatered after a dry period.'),
    dict(name='Eggplant', type='vegetable', spacing_in=18, sunlight='Full sun', water='Moderate',
         days_to_germination=10, days_to_harvest=80,
         notes='Start indoors 8–10 weeks before last frost. Needs warm conditions. Days to harvest from transplant.'),
    dict(name='Onion', type='vegetable', spacing_in=4, sunlight='Full sun', water='Moderate',
         days_to_germination=10, days_to_harvest=100,
         notes='Start from sets or transplants for easier growing. Stop watering when tops begin to fall over. Cure before storing.'),
    dict(name='Garlic', type='vegetable', spacing_in=6, sunlight='Full sun', water='Low',
         days_to_germination=14, days_to_harvest=240,
         notes='Plant cloves in fall for summer harvest. Each clove becomes a full bulb. Harvest when half the leaves have yellowed. Days to harvest counted from fall planting.'),
    dict(name='Corn', type='vegetable', spacing_in=12, sunlight='Full sun', water='High',
         days_to_germination=7, days_to_harvest=75,
         notes='Direct sow after last frost. Plant in blocks (not single rows) of at least 4×4 for good wind pollination. Harvest when silks are brown and kernels squirt milky juice.'),
    dict(name='Pumpkin', type='vegetable', spacing_in=60, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=100,
         notes='Needs a lot of space. Direct sow after last frost or start indoors 3 weeks early. Cure for 10 days after harvest for longer storage.'),
    # --- Herbs ---
    dict(name='Basil', type='herb', spacing_in=12, sunlight='Full sun', water='Moderate',
         days_to_germination=7, days_to_harvest=30,
         notes='Start indoors 4–6 weeks before last frost or direct sow after. Pinch flowers to keep leaves coming. Frost-sensitive; harvest before first frost.'),
    dict(name='Parsley', type='herb', spacing_in=8, sunlight='Full sun', water='Moderate',
         days_to_germination=21, days_to_harvest=70,
         notes='Slow to germinate; soak seeds overnight to speed up. Biennial — best grown as annual. Harvest outer stems first.'),
    dict(name='Cilantro', type='herb', spacing_in=6, sunlight='Partial shade', water='Moderate',
         days_to_germination=7, days_to_harvest=25,
         notes='Cool-season herb that bolts quickly in heat. Succession sow every 3 weeks. Let some bolt to collect coriander seeds.'),
    dict(name='Dill', type='herb', spacing_in=12, sunlight='Full sun', water='Low',
         days_to_germination=7, days_to_harvest=40,
         notes='Direct sow; does not transplant well. Let some go to seed for self-sowing. Attracts beneficial insects.'),
    dict(name='Oregano', type='herb', spacing_in=12, sunlight='Full sun', water='Low',
         days_to_germination=10, days_to_harvest=45,
         notes='Perennial in most zones. Harvest before flowering for peak flavor. Very drought-tolerant once established.'),
    dict(name='Thyme', type='herb', spacing_in=12, sunlight='Full sun', water='Low',
         days_to_germination=14, days_to_harvest=60,
         notes='Perennial. Drought-tolerant once established. Trim after flowering to keep compact.'),
    dict(name='Rosemary', type='herb', spacing_in=24, sunlight='Full sun', water='Low',
         days_to_germination=21, days_to_harvest=90,
         notes='Perennial in zones 7+; grow as annual or bring indoors in colder climates. Very drought-tolerant. Slow from seed; easier from cuttings.'),
    dict(name='Mint', type='herb', spacing_in=18, sunlight='Partial shade', water='Moderate',
         days_to_germination=14, days_to_harvest=30,
         notes='Spreads aggressively via runners; best grown in containers or a contained bed. Perennial. Many varieties available.'),
    dict(name='Chives', type='herb', spacing_in=6, sunlight='Full sun', water='Moderate',
         days_to_germination=14, days_to_harvest=30,
         notes='Perennial. Harvest by cutting leaves to 1 inch above ground. Edible purple flowers. Divide clumps every 2–3 years.'),
    dict(name='Sage', type='herb', spacing_in=18, sunlight='Full sun', water='Low',
         days_to_germination=14, days_to_harvest=75,
         notes='Perennial in zones 5+. Drought-tolerant once established. Harvest lightly the first year. Trim after flowering.'),
]


def _seed_library():
    if PlantLibrary.query.count() == 0:
        for entry in _LIBRARY_SEED:
            db.session.add(PlantLibrary(**entry))
        db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garden.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_library()

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

    def _apply_zip(garden, zip_code):
        """Fetch USDA zone + city/state for zip_code and apply to garden object."""
        zip_code = zip_code.strip()
        if not zip_code:
            return
        try:
            z = http.get(f'https://phzmapi.org/{zip_code}.json', timeout=6)
            z.raise_for_status()
            zdata = z.json()
            garden.usda_zone = zdata.get('zone')
            garden.zone_temp_range = zdata.get('temperature_range')
            coords = zdata.get('coordinates', {})
            garden.latitude = float(coords.get('lat', 0)) or None
            garden.longitude = float(coords.get('lon', 0)) or None
        except Exception:
            pass
        try:
            p = http.get(f'http://api.zippopotam.us/us/{zip_code}', timeout=6)
            p.raise_for_status()
            pdata = p.json()
            place = (pdata.get('places') or [{}])[0]
            garden.city = place.get('place name')
            garden.state = place.get('state abbreviation')
            if not garden.latitude:
                garden.latitude = float(place.get('latitude', 0)) or None
                garden.longitude = float(place.get('longitude', 0)) or None
        except Exception:
            pass
        garden.zip_code = zip_code

    @app.route('/gardens', methods=['GET', 'POST'])
    def gardens():
        if request.method == 'POST':
            garden = Garden(
                name=request.form['name'],
                description=request.form.get('description'),
                unit=request.form.get('unit', 'ft'),
            )
            db.session.add(garden)
            db.session.flush()  # get garden.id before commit
            zip_code = request.form.get('zip_code', '').strip()
            if zip_code:
                _apply_zip(garden, zip_code)
            db.session.commit()
            return redirect(url_for('garden_detail', garden_id=garden.id))
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

    # frost dates keyed by zone number (strip letter suffix)
    _FROST_DATES = {
        '1': ('Jun 15', 'Aug 15'), '2': ('Jun 1',  'Sep 1'),
        '3': ('May 15', 'Sep 15'), '4': ('May 1',  'Oct 1'),
        '5': ('Apr 15', 'Oct 15'), '6': ('Apr 1',  'Oct 31'),
        '7': ('Mar 15', 'Nov 15'), '8': ('Feb 15', 'Dec 1'),
        '9': ('Jan 31', 'Dec 15'), '10': ('rare',  'rare'),
        '11': ('none',  'none'),   '12': ('none',  'none'),
        '13': ('none',  'none'),
    }

    _WMO = {
        0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
        45: 'Fog', 48: 'Icy fog',
        51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
        61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
        71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains',
        80: 'Light showers', 81: 'Showers', 82: 'Heavy showers',
        85: 'Snow showers', 86: 'Heavy snow showers',
        95: 'Thunderstorm', 96: 'Thunderstorm w/ hail', 99: 'Thunderstorm w/ heavy hail',
    }

    @app.route('/gardens/<int:garden_id>/location', methods=['POST'])
    def set_garden_location(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        zip_code = request.form.get('zip_code', '').strip()
        if zip_code:
            _apply_zip(garden, zip_code)
        db.session.commit()
        return redirect(url_for('garden_detail', garden_id=garden_id))

    @app.route('/api/gardens/<int:garden_id>/weather')
    def api_garden_weather(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        if not garden.latitude or not garden.longitude:
            return jsonify({'error': 'no_location'}), 404
        try:
            resp = http.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': garden.latitude,
                'longitude': garden.longitude,
                'current': 'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,uv_index_max',
                'temperature_unit': 'fahrenheit',
                'wind_speed_unit': 'mph',
                'precipitation_unit': 'inch',
                'forecast_days': 7,
                'timezone': 'auto',
            }, timeout=8)
            resp.raise_for_status()
        except http.exceptions.RequestException as e:
            return jsonify({'error': str(e)}), 502
        data = resp.json()
        cur = data.get('current', {})
        daily = data.get('daily', {})
        zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
        frost = _FROST_DATES.get(zone_num, ('unknown', 'unknown'))
        days = []
        dates = daily.get('time', [])
        for i, d in enumerate(dates):
            days.append({
                'date': d,
                'high': daily['temperature_2m_max'][i],
                'low':  daily['temperature_2m_min'][i],
                'precip_prob': daily['precipitation_probability_max'][i],
                'uv': daily.get('uv_index_max', [None]*7)[i],
                'condition': _WMO.get(daily['weather_code'][i], 'Unknown'),
            })
        return jsonify({
            'current': {
                'temp': cur.get('temperature_2m'),
                'humidity': cur.get('relative_humidity_2m'),
                'precipitation': cur.get('precipitation'),
                'wind_speed': cur.get('wind_speed_10m'),
                'condition': _WMO.get(cur.get('weather_code'), 'Unknown'),
            },
            'daily': days,
            'frost': {'last_spring': frost[0], 'first_fall': frost[1]},
        })

    @app.route('/planner')
    def planner_index():
        first = Garden.query.order_by(Garden.name).first()
        if first:
            return redirect(url_for('planner', garden_id=first.id))
        return redirect(url_for('gardens'))

    @app.route('/gardens/<int:garden_id>/planner')
    def planner(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        all_gardens = Garden.query.order_by(Garden.name).all()
        library_plants = PlantLibrary.query.order_by(PlantLibrary.name).all()

        # Collect all plants in this garden: directly assigned + in a bed of this garden
        direct = Plant.query.filter_by(garden_id=garden_id).all()
        in_bed_ids = (db.session.query(BedPlant.plant_id)
                      .join(GardenBed, BedPlant.bed_id == GardenBed.id)
                      .filter(GardenBed.garden_id == garden_id)
                      .distinct())
        in_bed = Plant.query.filter(Plant.id.in_(in_bed_ids)).all()

        seen = set()
        combined = []
        for p in sorted(direct + in_bed, key=lambda x: x.name.lower()):
            if p.id not in seen:
                seen.add(p.id)
                combined.append(p)

        # Group by name; attach bed info per plant
        groups = defaultdict(list)
        for p in combined:
            beds_for_plant = [bp.bed for bp in p.bed_plants if bp.bed.garden_id == garden_id]
            groups[p.name].append({'plant': p, 'beds': beds_for_plant})
        garden_plant_groups = [
            {'name': name, 'instances': instances}
            for name, instances in groups.items()
        ]

        px_per_unit = 60
        return render_template('planner.html', garden=garden, all_gardens=all_gardens,
                               library_plants=library_plants,
                               garden_plant_groups=garden_plant_groups,
                               px_per_unit=px_per_unit)

    # --- Garden Beds ---

    @app.route('/beds', methods=['GET', 'POST'])
    def beds():
        all_gardens = Garden.query.order_by(Garden.name).all()
        garden_id = request.args.get('garden_id', type=int)

        if request.method == 'POST':
            width = request.form.get('width_ft')
            height = request.form.get('height_ft')
            depth = request.form.get('depth_ft')
            gid = request.form.get('garden_id', type=int)
            bed = GardenBed(
                name=request.form['name'],
                description=request.form.get('description'),
                location=request.form.get('location'),
                width_ft=float(width) if width else 4.0,
                height_ft=float(height) if height else 8.0,
                depth_ft=float(depth) if depth else None,
                soil_notes=request.form.get('soil_notes'),
                garden_id=gid,
            )
            db.session.add(bed)
            db.session.commit()
            return redirect(url_for('beds', garden_id=gid))

        q = GardenBed.query
        if garden_id:
            q = q.filter_by(garden_id=garden_id)
        all_beds = q.order_by(GardenBed.name).all()
        selected_garden = Garden.query.get(garden_id) if garden_id else None
        return render_template('beds.html', beds=all_beds, all_gardens=all_gardens,
                               garden_id=garden_id, selected_garden=selected_garden)

    @app.route('/beds/<int:bed_id>')
    def bed_detail(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        library_plants = PlantLibrary.query.order_by(PlantLibrary.name).all()
        return render_template('bed_detail.html', bed=bed, library_plants=library_plants)

    @app.route('/beds/<int:bed_id>/delete', methods=['POST'])
    def delete_bed(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        db.session.delete(bed)
        db.session.commit()
        return redirect(url_for('beds'))

    @app.route('/api/beds/<int:bed_id>/delete', methods=['POST'])
    def api_delete_bed(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        db.session.delete(bed)
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/beds/<int:bed_id>/edit', methods=['POST'])
    def edit_bed(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        depth = request.form.get('depth_ft')
        bed.name = request.form['name']
        bed.location = request.form.get('location')
        bed.description = request.form.get('description')
        bed.depth_ft = float(depth) if depth else None
        bed.soil_notes = request.form.get('soil_notes')
        db.session.commit()
        return redirect(url_for('bed_detail', bed_id=bed.id))

    # --- Plants ---

    @app.route('/plants', methods=['GET', 'POST'])
    def plants():
        tab = request.args.get('tab', 'planning')
        garden_id = request.args.get('garden_id', type=int)
        all_gardens = Garden.query.order_by(Garden.name).all()
        selected_garden = Garden.query.get(garden_id) if garden_id else None

        if request.method == 'POST':
            planted = request.form.get('planted_date')
            harvest = request.form.get('expected_harvest')
            status = request.form.get('status', 'planning')
            gid = request.form.get('garden_id', type=int) or garden_id
            plant = Plant(
                name=request.form['name'],
                type=request.form.get('type'),
                notes=request.form.get('notes'),
                planted_date=date.fromisoformat(planted) if planted else None,
                expected_harvest=date.fromisoformat(harvest) if harvest else None,
                status=status,
                garden_id=gid,
            )
            db.session.add(plant)
            db.session.commit()
            return redirect(url_for('plants', tab=status, garden_id=gid))

        base_q = Plant.query
        if garden_id:
            base_q = base_q.filter_by(garden_id=garden_id)

        planning_plants = base_q.filter_by(status='planning').order_by(Plant.name).all()
        growing_plants  = base_q.filter_by(status='growing').order_by(Plant.name).all()
        library_plants  = PlantLibrary.query.order_by(PlantLibrary.name).all()

        # Build smart reminders
        today = date.today()
        reminders = []

        for p in growing_plants:
            if p.expected_harvest:
                days_left = (p.expected_harvest - today).days
                if days_left <= 7:
                    reminders.append({
                        'icon': '🌽',
                        'label': 'Harvest overdue' if days_left < 0 else f'Harvest in {days_left} day{"s" if days_left != 1 else ""}',
                        'plant_name': p.name,
                        'detail': p.expected_harvest.strftime('%b %d'),
                        'urgent': days_left < 0,
                        'plant_id': p.id,
                    })

        bp_q = BedPlant.query
        if garden_id:
            bp_q = bp_q.join(GardenBed).filter(GardenBed.garden_id == garden_id)

        for bp in bp_q.all():
            if bp.last_watered and (today - bp.last_watered).days >= 3:
                days_since = (today - bp.last_watered).days
                reminders.append({
                    'icon': '💧',
                    'label': f'Water {bp.plant.name}',
                    'plant_name': bp.plant.name,
                    'detail': f'Last watered {days_since} day{"s" if days_since != 1 else ""} ago in {bp.bed.name}',
                    'urgent': days_since >= 7,
                    'plant_id': bp.plant.id,
                })
            if bp.last_fertilized and (today - bp.last_fertilized).days >= 14:
                days_since = (today - bp.last_fertilized).days
                reminders.append({
                    'icon': '🌿',
                    'label': f'Fertilize {bp.plant.name}',
                    'plant_name': bp.plant.name,
                    'detail': f'Last fertilized {days_since} days ago in {bp.bed.name}',
                    'urgent': days_since >= 21,
                    'plant_id': bp.plant.id,
                })

        tasks = Task.query.filter_by(completed=False).order_by(Task.due_date.asc().nullslast()).all()

        return render_template('plants.html',
            tab=tab,
            garden_id=garden_id,
            all_gardens=all_gardens,
            selected_garden=selected_garden,
            planning_plants=planning_plants,
            growing_plants=growing_plants,
            library_plants=library_plants,
            reminders=reminders,
            tasks=tasks,
            today=today,
        )

    @app.route('/plants/<int:plant_id>/set-status', methods=['POST'])
    def set_plant_status(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        new_status = request.form.get('status')
        garden_id = request.form.get('garden_id', type=int) or plant.garden_id
        if new_status in ('planning', 'growing'):
            plant.status = new_status
            if new_status == 'growing' and not plant.planted_date:
                plant.planted_date = date.today()
            db.session.commit()
        return redirect(url_for('plants', tab=new_status or plant.status, garden_id=garden_id))

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

    @app.route('/api/plants/<int:plant_id>/delete', methods=['POST'])
    def api_delete_plant(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        db.session.delete(plant)
        db.session.commit()
        return jsonify({'ok': True})

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

    # --- Plant Library ---

    PERENUAL_KEY = os.getenv('PERENUAL_API_KEY', '')



    @app.route('/library')
    def library():
        entries = PlantLibrary.query.order_by(PlantLibrary.type, PlantLibrary.name).all()
        return render_template('library.html', entries=entries)

    @app.route('/library/<int:entry_id>')
    def library_detail(entry_id):
        import json as _json
        entry = PlantLibrary.query.get_or_404(entry_id)

        def _parse(col):
            try:
                return _json.loads(col) if col else None
            except Exception:
                return None

        good_neighbors = _parse(entry.good_neighbors)
        bad_neighbors  = _parse(entry.bad_neighbors)
        how_to_grow    = _parse(entry.how_to_grow)
        faqs           = _parse(entry.faqs)
        nutrition      = _parse(entry.nutrition)

        # Planting calendar: compute month labels for every zone using frost dates
        calendar_rows = []
        if entry.sow_indoor_weeks is not None or entry.direct_sow_offset is not None or entry.transplant_offset is not None:
            from datetime import datetime, timedelta
            def _frost_date(month_day_str):
                if month_day_str in ('none', 'rare', 'unknown'):
                    return None
                try:
                    return datetime.strptime(f'{month_day_str} 2024', '%b %d %Y')
                except Exception:
                    return None

            for zone_num in range(1, 14):
                last_spring, first_fall = _FROST_DATES.get(str(zone_num), ('unknown', 'unknown'))
                frost = _frost_date(last_spring)
                if not frost:
                    continue
                row = {'zone': zone_num}
                if entry.sow_indoor_weeks is not None:
                    d = frost - timedelta(weeks=entry.sow_indoor_weeks)
                    row['start_indoors'] = d.strftime('%b %d')
                if entry.direct_sow_offset is not None:
                    d = frost + timedelta(weeks=entry.direct_sow_offset)
                    row['direct_sow'] = d.strftime('%b %d')
                if entry.transplant_offset is not None:
                    d = frost + timedelta(weeks=entry.transplant_offset)
                    row['transplant'] = d.strftime('%b %d')
                row['last_frost'] = last_spring
                row['first_fall_frost'] = first_fall
                calendar_rows.append(row)

        # Default selected zone — use first garden with a zone set
        selected_zone = None
        g = Garden.query.filter(Garden.usda_zone.isnot(None)).first()
        if g and g.usda_zone:
            z = ''.join(filter(str.isdigit, g.usda_zone))
            selected_zone = int(z) if z else None

        tab = request.args.get('tab', 'overview')
        all_gardens = Garden.query.order_by(Garden.name).all()
        return render_template('library_detail.html',
            entry=entry,
            tab=tab,
            good_neighbors=good_neighbors,
            bad_neighbors=bad_neighbors,
            how_to_grow=how_to_grow,
            faqs=faqs,
            nutrition=nutrition,
            calendar_rows=calendar_rows,
            selected_zone=selected_zone,
            all_gardens=all_gardens,
        )

    @app.route('/library/<int:entry_id>/add', methods=['POST'])
    def library_add_plant(entry_id):
        entry = PlantLibrary.query.get_or_404(entry_id)
        garden_id = request.form.get('garden_id', type=int) or None
        plant = Plant(
            name=entry.name,
            type=entry.type,
            library_id=entry.id,
            garden_id=garden_id,
            status='planning',
        )
        db.session.add(plant)
        db.session.commit()
        return redirect(url_for('plants', tab='planning', garden_id=garden_id))

    def _download_plant_image(perenual_id, image_url):
        """Download image from URL, save to static/plant_images/<perenual_id>.jpg.
        Returns filename on success, None on failure."""
        import re
        filename = f'{perenual_id}.jpg'
        dest = os.path.join(app.static_folder, 'plant_images', filename)
        if os.path.exists(dest):
            return filename
        try:
            r = http.get(image_url, timeout=10, stream=True)
            r.raise_for_status()
            content_type = r.headers.get('content-type', '')
            ext = '.jpg'
            if 'png' in content_type:
                ext = '.png'
            elif 'webp' in content_type:
                ext = '.webp'
            filename = f'{perenual_id}{ext}'
            dest = os.path.join(app.static_folder, 'plant_images', filename)
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return filename
        except Exception:
            return None

    def _perenual_get(path, params):
        """Make a Perenual API call; return (data, err_type, err_msg)."""
        if not PERENUAL_KEY:
            return None, 'config', 'PERENUAL_API_KEY is not configured.'
        params['key'] = PERENUAL_KEY
        try:
            resp = http.get(f'https://perenual.com/api/{path}', params=params, timeout=8)
        except http.exceptions.Timeout:
            return None, 'network', 'Request to Perenual timed out. Check your connection.'
        except http.exceptions.RequestException as e:
            return None, 'network', f'Network error: {e}'
        if resp.status_code == 429:
            return None, 'rate_limit', (
                'Perenual daily request limit reached (100 requests/day on the free plan). '
                'Try again tomorrow or upgrade your plan at perenual.com.'
            )
        if resp.status_code == 401:
            return None, 'auth', 'Invalid Perenual API key. Check your .env file.'
        if not resp.ok:
            return None, 'api', f'Perenual returned an error (HTTP {resp.status_code}).'
        data = resp.json()
        # Free tier wraps paywalled data in upgrade messages
        if isinstance(data, dict) and 'Upgrade Plans' in str(data.get('message', '')):
            return None, 'rate_limit', (
                'This data requires a Perenual premium plan. '
                'Visit perenual.com/subscription-api-pricing to upgrade.'
            )
        return data, None, None

    @app.route('/api/perenual/search')
    def api_perenual_search():
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'results': []})
        data, err_type, err_msg = _perenual_get('species-list', {'q': q, 'page': 1})
        if err_type:
            return jsonify({'error': err_type, 'message': err_msg}), (429 if err_type == 'rate_limit' else 502)
        results = []
        for p in data.get('data', []):
            name = p.get('common_name') or (p.get('scientific_name') or [None])[0]
            if not name or 'Upgrade Plans' in str(name):
                continue
            sunlight = ', '.join(p.get('sunlight') or [])
            if 'Upgrade Plans' in sunlight:
                sunlight = ''
            results.append({
                'perenual_id': p.get('id'),
                'name': name,
                'scientific_name': (p.get('scientific_name') or [None])[0],
                'sunlight': sunlight,
                'watering': p.get('watering'),
                'cycle': p.get('cycle'),
                'image': (p.get('default_image') or {}).get('thumbnail'),
            })
        return jsonify({'results': results})

    @app.route('/api/perenual/fetch-image/<int:entry_id>', methods=['POST'])
    def api_perenual_fetch_image(entry_id):
        """Fetch image from Perenual and save locally. Called when no local image exists."""
        entry = PlantLibrary.query.get_or_404(entry_id)
        if not entry.perenual_id:
            return jsonify({'error': 'no_id', 'message': 'No Perenual ID for this plant.'}), 404
        if entry.image_filename:
            return jsonify({'ok': True, 'filename': entry.image_filename})
        data, err_type, err_msg = _perenual_get(f'species/details/{entry.perenual_id}', {})
        if err_type:
            return jsonify({'error': err_type, 'message': err_msg}), (429 if err_type == 'rate_limit' else 502)
        img = data.get('default_image') or {}
        url = img.get('small_url') or img.get('thumbnail')
        if not url or 'Upgrade Plans' in str(url):
            return jsonify({'error': 'no_image', 'message': 'No image available.'}), 404
        filename = _download_plant_image(entry.perenual_id, url)
        if not filename:
            return jsonify({'error': 'download', 'message': 'Failed to download image.'}), 502
        entry.image_filename = filename
        db.session.commit()
        return jsonify({'ok': True, 'filename': filename})

    @app.route('/api/perenual/save', methods=['POST'])
    def api_perenual_save():
        data = request.get_json(force=True)
        if not data or not data.get('name'):
            return jsonify({'error': 'name required'}), 400
        existing = PlantLibrary.query.filter(
            db.func.lower(PlantLibrary.name) == data['name'].lower()
        ).first()
        if existing:
            return jsonify({'ok': True, 'id': existing.id, 'existing': True})
        water_map = {'minimum': 'Low', 'average': 'Moderate', 'frequent': 'High'}
        water = water_map.get((data.get('watering') or '').lower())
        sunlight = data.get('sunlight') or None
        if sunlight and 'Upgrade Plans' in sunlight:
            sunlight = None
        perenual_id = data.get('perenual_id') or None
        image_filename = None
        if perenual_id and data.get('image'):
            image_filename = _download_plant_image(perenual_id, data['image'])
        entry = PlantLibrary(
            name=data['name'],
            scientific_name=data.get('scientific_name') or None,
            perenual_id=perenual_id,
            image_filename=image_filename,
            type=data.get('cycle') or None,
            sunlight=sunlight,
            water=water,
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({'ok': True, 'id': entry.id, 'existing': False})

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

    def _plant_from_library(library_id):
        """Find or create a Plant instance for a given PlantLibrary entry."""
        entry = PlantLibrary.query.get(library_id)
        if not entry:
            return None
        plant = Plant(name=entry.name, type=entry.type, library_id=entry.id)
        db.session.add(plant)
        db.session.flush()
        return plant

    @app.route('/api/bedplants', methods=['POST'])
    def api_create_bedplant():
        data = request.get_json(force=True)
        if not data or 'bed_id' not in data:
            return jsonify({'error': 'bed_id required'}), 400
        if 'library_id' in data:
            plant = _plant_from_library(int(data['library_id']))
            if not plant:
                return jsonify({'error': 'library entry not found'}), 404
        elif 'plant_id' in data:
            plant = Plant.query.get_or_404(int(data['plant_id']))
        else:
            return jsonify({'error': 'library_id or plant_id required'}), 400
        bp = BedPlant(bed_id=int(data['bed_id']), plant_id=plant.id)
        db.session.add(bp)
        db.session.commit()
        entry = plant.library_entry
        return jsonify({
            'ok': True, 'id': bp.id,
            'plant': {
                'id': plant.id, 'name': plant.name,
                'image_filename': entry.image_filename if entry else None,
            }
        })

    @app.route('/api/bedplants/<int:bp_id>/delete', methods=['POST'])
    def api_delete_bedplant(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        db.session.delete(bp)
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/beds/<int:bed_id>/grid')
    def api_bed_grid(bed_id):
        bed = GardenBed.query.get_or_404(bed_id)
        placed = []
        for bp in bed.bed_plants:
            if bp.grid_x is None or bp.grid_y is None:
                continue
            entry = bp.plant.library_entry if bp.plant else None
            placed.append({
                'id': bp.id, 'plant_id': bp.plant_id,
                'plant_name': bp.plant.name if bp.plant else '?',
                'image_filename': entry.image_filename if entry else None,
                'grid_x': bp.grid_x, 'grid_y': bp.grid_y,
            })
        return jsonify({
            'bed': {'id': bed.id, 'name': bed.name, 'width_ft': bed.width_ft, 'height_ft': bed.height_ft},
            'placed': placed,
        })

    @app.route('/api/beds/<int:bed_id>/grid-plant', methods=['POST'])
    def api_bed_grid_plant(bed_id):
        GardenBed.query.get_or_404(bed_id)
        data = request.get_json(force=True)
        if not data or 'grid_x' not in data or 'grid_y' not in data:
            return jsonify({'error': 'grid_x and grid_y required'}), 400
        grid_x, grid_y = int(data['grid_x']), int(data['grid_y'])
        if BedPlant.query.filter_by(bed_id=bed_id, grid_x=grid_x, grid_y=grid_y).first():
            return jsonify({'error': 'cell already occupied'}), 409
        if 'library_id' in data:
            plant = _plant_from_library(int(data['library_id']))
            if not plant:
                return jsonify({'error': 'library entry not found'}), 404
        elif 'plant_id' in data:
            plant = Plant.query.get_or_404(int(data['plant_id']))
        else:
            return jsonify({'error': 'library_id or plant_id required'}), 400
        bp = BedPlant(bed_id=bed_id, plant_id=plant.id, grid_x=grid_x, grid_y=grid_y)
        db.session.add(bp)
        db.session.commit()
        entry = plant.library_entry
        return jsonify({
            'ok': True, 'id': bp.id,
            'plant_name': plant.name,
            'image_filename': entry.image_filename if entry else None,
            'spacing_in': entry.spacing_in if entry and entry.spacing_in else 12,
        })

    @app.route('/api/bedplants/<int:bp_id>/care', methods=['POST'])
    def api_bedplant_care(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        data = request.get_json(force=True)
        if 'last_watered' in data:
            bp.last_watered = date.fromisoformat(data['last_watered']) if data['last_watered'] else None
        if 'last_fertilized' in data:
            bp.last_fertilized = date.fromisoformat(data['last_fertilized']) if data['last_fertilized'] else None
        if 'health_notes' in data:
            bp.health_notes = data['health_notes'] or None
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/bedplants/<int:bp_id>')
    def api_bedplant_detail(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        entry = bp.plant.library_entry if bp.plant else None
        return jsonify({
            'id': bp.id,
            'plant_name': bp.plant.name if bp.plant else '?',
            'image_filename': entry.image_filename if entry else None,
            'scientific_name': entry.scientific_name if entry else None,
            'spacing_in': entry.spacing_in if entry else None,
            'sunlight': entry.sunlight if entry else None,
            'water': entry.water if entry else None,
            'days_to_harvest': entry.days_to_harvest if entry else None,
            'last_watered': bp.last_watered.isoformat() if bp.last_watered else None,
            'last_fertilized': bp.last_fertilized.isoformat() if bp.last_fertilized else None,
            'health_notes': bp.health_notes or '',
        })

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
