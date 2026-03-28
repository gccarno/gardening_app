import hashlib
import os
from collections import defaultdict
from datetime import date, timedelta
import requests as http
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from .db.models import db, Garden, GardenBed, Plant, Task, BedPlant, PlantLibrary, PlantLibraryImage, WeatherLog, CanvasPlant, AppSetting

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
    _here     = os.path.dirname(os.path.abspath(__file__))   # apps/api/app/
    _api_root = os.path.dirname(_here)                        # apps/api/
    app = Flask(
        __name__,
        static_folder=os.path.join(_api_root, 'static'),
        template_folder=os.path.join(_api_root, 'templates'),
        instance_path=os.path.join(_api_root, 'instance'),
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garden.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Add columns if they don't exist yet (no migrations setup)
        # IMPORTANT: plant_library migrations must run before _seed_library()
        with db.engine.connect() as conn:
            cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(garden)"))]
            if 'background_image' not in cols:
                conn.execute(db.text("ALTER TABLE garden ADD COLUMN background_image VARCHAR(200)"))
                conn.commit()
            if 'annotations' not in cols:
                conn.execute(db.text("ALTER TABLE garden ADD COLUMN annotations TEXT"))
                conn.commit()
            bed_cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(garden_bed)"))]
            for col, ddl in [
                ('soil_ph',     'ALTER TABLE garden_bed ADD COLUMN soil_ph FLOAT'),
                ('clay_pct',    'ALTER TABLE garden_bed ADD COLUMN clay_pct FLOAT'),
                ('compost_pct', 'ALTER TABLE garden_bed ADD COLUMN compost_pct FLOAT'),
                ('sand_pct',    'ALTER TABLE garden_bed ADD COLUMN sand_pct FLOAT'),
            ]:
                if col not in bed_cols:
                    conn.execute(db.text(ddl))
                    conn.commit()
            bp_cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(bed_plant)"))]
            if 'stage' not in bp_cols:
                conn.execute(db.text("ALTER TABLE bed_plant ADD COLUMN stage VARCHAR(20)"))
                conn.commit()
            lib_cols = [row[1] for row in conn.execute(db.text("PRAGMA table_info(plant_library)"))]
            for col, ddl in [
                ('openfarm_id',             'ALTER TABLE plant_library ADD COLUMN openfarm_id VARCHAR(30)'),
                ('openfarm_slug',           'ALTER TABLE plant_library ADD COLUMN openfarm_slug VARCHAR(100)'),
                ('trefle_id',               'ALTER TABLE plant_library ADD COLUMN trefle_id INTEGER'),
                ('trefle_slug',             'ALTER TABLE plant_library ADD COLUMN trefle_slug VARCHAR(100)'),
                ('toxicity',                'ALTER TABLE plant_library ADD COLUMN toxicity VARCHAR(20)'),
                ('duration',                'ALTER TABLE plant_library ADD COLUMN duration VARCHAR(50)'),
                ('ligneous_type',           'ALTER TABLE plant_library ADD COLUMN ligneous_type VARCHAR(50)'),
                ('growth_habit',            'ALTER TABLE plant_library ADD COLUMN growth_habit VARCHAR(100)'),
                ('growth_form',             'ALTER TABLE plant_library ADD COLUMN growth_form VARCHAR(100)'),
                ('growth_rate',             'ALTER TABLE plant_library ADD COLUMN growth_rate VARCHAR(50)'),
                ('nitrogen_fixation',       'ALTER TABLE plant_library ADD COLUMN nitrogen_fixation VARCHAR(30)'),
                ('vegetable',               'ALTER TABLE plant_library ADD COLUMN vegetable BOOLEAN'),
                ('observations',            'ALTER TABLE plant_library ADD COLUMN observations TEXT'),
                ('average_height_cm',       'ALTER TABLE plant_library ADD COLUMN average_height_cm INTEGER'),
                ('maximum_height_cm',       'ALTER TABLE plant_library ADD COLUMN maximum_height_cm INTEGER'),
                ('spread_cm',               'ALTER TABLE plant_library ADD COLUMN spread_cm INTEGER'),
                ('row_spacing_cm',          'ALTER TABLE plant_library ADD COLUMN row_spacing_cm INTEGER'),
                ('minimum_root_depth_cm',   'ALTER TABLE plant_library ADD COLUMN minimum_root_depth_cm INTEGER'),
                ('soil_nutriments',         'ALTER TABLE plant_library ADD COLUMN soil_nutriments INTEGER'),
                ('soil_salinity',           'ALTER TABLE plant_library ADD COLUMN soil_salinity INTEGER'),
                ('atmospheric_humidity',    'ALTER TABLE plant_library ADD COLUMN atmospheric_humidity INTEGER'),
                ('precipitation_min_mm',    'ALTER TABLE plant_library ADD COLUMN precipitation_min_mm INTEGER'),
                ('precipitation_max_mm',    'ALTER TABLE plant_library ADD COLUMN precipitation_max_mm INTEGER'),
                ('bloom_months',            'ALTER TABLE plant_library ADD COLUMN bloom_months TEXT'),
                ('fruit_months',            'ALTER TABLE plant_library ADD COLUMN fruit_months TEXT'),
                ('growth_months',           'ALTER TABLE plant_library ADD COLUMN growth_months TEXT'),
                ('flower_color',            'ALTER TABLE plant_library ADD COLUMN flower_color VARCHAR(100)'),
                ('flower_conspicuous',      'ALTER TABLE plant_library ADD COLUMN flower_conspicuous BOOLEAN'),
                ('foliage_color',           'ALTER TABLE plant_library ADD COLUMN foliage_color VARCHAR(100)'),
                ('foliage_texture',         'ALTER TABLE plant_library ADD COLUMN foliage_texture VARCHAR(30)'),
                ('leaf_retention',          'ALTER TABLE plant_library ADD COLUMN leaf_retention BOOLEAN'),
                ('fruit_color',             'ALTER TABLE plant_library ADD COLUMN fruit_color VARCHAR(100)'),
                ('fruit_conspicuous',       'ALTER TABLE plant_library ADD COLUMN fruit_conspicuous BOOLEAN'),
                ('fruit_shape',             'ALTER TABLE plant_library ADD COLUMN fruit_shape VARCHAR(100)'),
                ('seed_persistence',        'ALTER TABLE plant_library ADD COLUMN seed_persistence BOOLEAN'),
            ]:
                if col not in lib_cols:
                    conn.execute(db.text(ddl))
                    conn.commit()
        _seed_library()

        # Backfill existing image_filename values into PlantLibraryImage
        _img_dir = os.path.join(app.static_folder, 'plant_images')
        for entry in PlantLibrary.query.filter(PlantLibrary.image_filename.isnot(None)).all():
            if entry.images:
                continue
            fn = entry.image_filename
            fpath = os.path.join(_img_dir, fn)
            if not os.path.exists(fpath):
                continue
            with open(fpath, 'rb') as _f:
                fhash = hashlib.sha256(_f.read()).hexdigest()
            if PlantLibraryImage.query.filter_by(file_hash=fhash).first():
                continue
            source = 'perenual' if fn.split('.')[0].isdigit() else 'manual'
            db.session.add(PlantLibraryImage(
                plant_library_id=entry.id,
                filename=fn,
                source=source,
                file_hash=fhash,
                is_primary=True,
            ))
        db.session.commit()

    # --- Dashboard ---

    # Planting hints by month (Northern Hemisphere)
    _PLANTING_HINTS = {
        1:  ('Plan & Order',    'Order seeds and sketch your layout for the coming season.',
             'Onions, celery, peppers — start indoors late month'),
        2:  ('Start Indoors',   'Begin slow-growing crops under lights.',
             'Tomatoes, peppers, eggplant'),
        3:  ('Sow Cool Crops',  'Direct-sow cold-tolerant crops when soil is workable.',
             'Peas, spinach, lettuce, kale, carrots'),
        4:  ('Harden & Plant',  'Harden off starts; transplant cold-hardy crops.',
             'Broccoli, cabbage, onion sets, lettuce'),
        5:  ('Peak Planting',   'Last frost passes for most zones — time for warm-season crops.',
             'Tomatoes, basil, beans, squash, cucumbers'),
        6:  ('Direct Sow',      'Sow warm-season crops; succession-plant salad greens.',
             'Beans, cucumbers, squash, corn, herbs'),
        7:  ('Maintain',        'Harvest regularly; start fall brassica seeds indoors.',
             'Broccoli, kale, chard — start for fall'),
        8:  ('Fall Prep',       'Sow fast-maturing crops for a fall harvest.',
             'Carrots, radishes, arugula, spinach'),
        9:  ('Fall Planting',   'Plant garlic and overwintering crops before first frost.',
             'Garlic, spinach, kale, cover crops'),
        10: ('Wrap Up',         'Plant spring bulbs and cover crops to protect soil.',
             'Garlic, cover crops, spring bulbs'),
        11: ('Rest & Compost',  'Mulch beds, add compost, and plan for next year.',
             'Cover crops, soil amendments'),
        12: ('Plan Ahead',      'Review the season and browse seed catalogs.',
             'Start planning and ordering seeds'),
    }

    def _get_season(today):
        m, d = today.month, today.day
        if (m == 12 and d >= 21) or m in (1, 2) or (m == 3 and d < 20):
            return 'Winter', '❄️'
        if (m == 3 and d >= 20) or m in (4, 5) or (m == 6 and d < 21):
            return 'Spring', '🌸'
        if (m == 6 and d >= 21) or m in (7, 8) or (m == 9 and d < 22):
            return 'Summer', '☀️'
        return 'Fall', '🍂'

    @app.route('/')
    def index():
        all_gardens = Garden.query.order_by(Garden.name).all()
        # Resolve selected/default garden
        setting = AppSetting.query.get('default_garden_id')
        default_gid = int(setting.value) if setting and setting.value else None
        selected = (Garden.query.get(default_gid) if default_gid
                    else (all_gardens[0] if all_gardens else None))

        # Base queries — scoped to selected garden
        q_beds   = GardenBed.query
        q_plants = Plant.query
        q_tasks  = Task.query.filter_by(completed=False)
        if selected:
            q_beds   = q_beds.filter_by(garden_id=selected.id)
            q_plants = q_plants.filter_by(garden_id=selected.id)
            q_tasks  = q_tasks.filter_by(garden_id=selected.id)

        metrics = {
            'bed_count':     q_beds.count(),
            'plant_count':   q_plants.count(),
            'task_count':    q_tasks.count(),
            'plants_active': q_plants.filter_by(status='active').count(),
            'overdue_tasks': q_tasks.filter(Task.due_date < date.today()).count(),
        }

        upcoming_tasks = (q_tasks
                          .order_by(Task.due_date.asc().nullslast())
                          .limit(5).all())
        recent_plants = q_plants.order_by(Plant.id.desc()).limit(5).all()

        # Recent activity — completed tasks in the last 14 days
        activity_cutoff = date.today() - timedelta(days=14)
        q_done = Task.query.filter(
            Task.completed == True,
            Task.completed_date >= activity_cutoff,
        )
        if selected:
            q_done = q_done.filter_by(garden_id=selected.id)
        recent_activity = q_done.order_by(Task.completed_date.desc()).limit(8).all()

        # Season + planting hints
        today_dt = date.today()
        season, season_icon = _get_season(today_dt)
        hint_action, hint_text, hint_crops = _PLANTING_HINTS[today_dt.month]

        # Frost date context
        frost_context = None
        if selected and selected.last_frost_date:
            days = (selected.last_frost_date - today_dt).days
            if days > 0:
                frost_context = f'Last frost in {days} day{"s" if days != 1 else ""} ({selected.last_frost_date.strftime("%b %d")})'
            elif days >= -30:
                frost_context = f'Last frost passed {-days} day{"s" if days != -1 else ""} ago'

        return render_template('index.html',
            all_gardens=all_gardens, selected=selected,
            metrics=metrics, upcoming_tasks=upcoming_tasks, recent_plants=recent_plants,
            recent_activity=recent_activity,
            season=season, season_icon=season_icon,
            hint_action=hint_action, hint_text=hint_text, hint_crops=hint_crops,
            frost_context=frost_context,
            today=today_dt)

    @app.route('/settings/default-garden', methods=['POST'])
    def set_default_garden():
        gid = request.form.get('garden_id', '').strip()
        setting = AppSetting.query.get('default_garden_id')
        if setting is None:
            setting = AppSetting(key='default_garden_id', value=gid or None)
            db.session.add(setting)
        else:
            setting.value = gid or None
        db.session.commit()
        return redirect(url_for('index'))

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

    def _rainfall_summary(garden_id, days=7):
        cutoff = date.today() - timedelta(days=days)
        logs = WeatherLog.query.filter(
            WeatherLog.garden_id == garden_id,
            WeatherLog.date >= cutoff,
        ).all()
        total = sum(l.rainfall_in or 0 for l in logs)
        return {'total_in': round(total, 2), 'days_with_data': len(logs)}

    @app.route('/gardens/<int:garden_id>')
    def garden_detail(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        rainfall_7d  = _rainfall_summary(garden_id, 7)
        rainfall_14d = _rainfall_summary(garden_id, 14)
        return render_template('garden_detail.html', garden=garden,
                               rainfall_7d=rainfall_7d, rainfall_14d=rainfall_14d)

    @app.route('/gardens/<int:garden_id>/edit', methods=['POST'])
    def edit_garden(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        garden.name = request.form['name']
        garden.description = request.form.get('description')
        garden.unit = request.form.get('unit', 'ft')
        f = request.form.get('last_frost_date')
        garden.last_frost_date = date.fromisoformat(f) if f else None
        garden.watering_frequency_days = request.form.get('watering_frequency_days', type=int) or 7
        garden.water_source = request.form.get('water_source') or None
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

    @app.route('/api/gardens/<int:garden_id>/tasks')
    def api_garden_tasks(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        plant_ids = [p.id for p in garden.plants]
        bed_ids = [b.id for b in garden.beds]
        tasks = (Task.query
                 .filter(
                     db.or_(
                         Task.plant_id.in_(plant_ids),
                         Task.garden_id == garden_id,
                         Task.bed_id.in_(bed_ids),
                     ),
                     Task.completed == False,
                 )
                 .order_by(Task.due_date)
                 .limit(20).all())
        return jsonify([{
            'id': t.id,
            'title': t.title,
            'task_type': t.task_type,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'plant_name': t.plant.name if t.plant else None,
            'scope': 'plant' if t.plant_id else ('bed' if t.bed_id else 'garden'),
        } for t in tasks])

    @app.route('/api/gardens/<int:garden_id>/quick-task', methods=['POST'])
    def api_quick_task(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        data = request.get_json() or {}
        task_type = data.get('task_type', 'other')
        plant_id = data.get('plant_id')
        bed_id = data.get('bed_id')
        title = data.get('title')
        description = data.get('description')
        due_date_override = data.get('due_date')  # explicit date from custom form
        due_date = None

        plant = Plant.query.get(plant_id) if plant_id else None
        lib = plant.library_entry if plant else None

        # Auto-calculate due date
        frost = garden.last_frost_date
        if not frost and garden.usda_zone:
            # Fall back to _FROST_DATES lookup
            zone_num = ''.join(filter(str.isdigit, garden.usda_zone or ''))
            spring_str, _ = _FROST_DATES.get(zone_num, (None, None))
            if spring_str and spring_str not in ('none', 'rare', 'unknown'):
                from datetime import datetime
                try:
                    frost = datetime.strptime(f'{spring_str} {date.today().year}', '%b %d %Y').date()
                except ValueError:
                    frost = None

        if task_type == 'seeding' and lib and lib.sow_indoor_weeks and frost:
            due_date = frost - timedelta(weeks=lib.sow_indoor_weeks)
        elif task_type == 'transplanting' and lib and lib.transplant_offset and frost:
            due_date = frost + timedelta(weeks=lib.transplant_offset)
        elif task_type == 'harvest':
            if plant and plant.planted_date and lib and lib.days_to_harvest:
                due_date = plant.planted_date + timedelta(days=lib.days_to_harvest)
            elif plant and plant.expected_harvest:
                due_date = plant.expected_harvest

        # Explicit due_date from client overrides auto-calculated
        if due_date_override:
            try:
                due_date = date.fromisoformat(due_date_override)
            except ValueError:
                pass

        # Auto-title
        if not title:
            plant_name = plant.name if plant else ''
            type_labels = {
                'seeding': f'Seed {plant_name}'.strip(),
                'transplanting': f'Transplant {plant_name}'.strip(),
                'harvest': f'Harvest {plant_name}'.strip(),
                'watering': f'Water {plant_name or garden.name}'.strip(),
                'fertilizing': f'Fertilize {plant_name or garden.name}'.strip(),
                'mulching': f'Mulch {plant_name or garden.name}'.strip(),
                'weeding': f'Weed {garden.name}',
                'pruning': f'Prune {plant_name or garden.name}'.strip(),
            }
            title = type_labels.get(task_type, 'Task')

        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            due_date=due_date,
            plant_id=plant_id,
            garden_id=garden_id,
            bed_id=bed_id,
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({'ok': True, 'task_id': task.id,
                        'due_date': due_date.isoformat() if due_date else None})

    @app.route('/api/gardens/<int:garden_id>/bulk-care', methods=['POST'])
    def api_bulk_care(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        data = request.get_json() or {}
        action = data.get('action')
        if action not in ('water', 'fertilize', 'mulch'):
            return jsonify({'error': 'Invalid action'}), 400
        care_date_str = data.get('date')
        care_date = date.fromisoformat(care_date_str) if care_date_str else date.today()
        create_task = data.get('create_task', True)

        bed_ids = [b.id for b in garden.beds]
        bps = BedPlant.query.filter(BedPlant.bed_id.in_(bed_ids)).all() if bed_ids else []
        field_map = {'water': 'last_watered', 'fertilize': 'last_fertilized'}

        if action in field_map:
            for bp in bps:
                setattr(bp, field_map[action], care_date)

        if create_task:
            type_map = {'water': 'watering', 'fertilize': 'fertilizing', 'mulch': 'mulching'}
            task = Task(
                title=f'{action.capitalize()} all plants — {garden.name}',
                task_type=type_map[action],
                garden_id=garden_id,
                due_date=care_date,
                completed=True,
                completed_date=care_date,
            )
            db.session.add(task)

        db.session.commit()
        return jsonify({'ok': True, 'updated': len(bps)})

    @app.route('/api/gardens/<int:garden_id>/fetch-weather', methods=['POST'])
    def api_fetch_weather_history(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        if not garden.latitude or not garden.longitude:
            return jsonify({'error': 'no_location'}), 400
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=13)
        try:
            resp = http.get('https://archive-api.open-meteo.com/v1/archive', params={
                'latitude': garden.latitude,
                'longitude': garden.longitude,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'daily': 'precipitation_sum,temperature_2m_max,temperature_2m_min',
                'temperature_unit': 'fahrenheit',
                'precipitation_unit': 'inch',
                'timezone': 'auto',
            }, timeout=10)
            resp.raise_for_status()
            daily = resp.json().get('daily', {})
        except Exception as e:
            return jsonify({'error': str(e)}), 502

        created = 0
        for i, d_str in enumerate(daily.get('time', [])):
            d = date.fromisoformat(d_str)
            WeatherLog.query.filter_by(garden_id=garden_id, date=d).delete()
            log = WeatherLog(
                garden_id=garden_id,
                date=d,
                rainfall_in=daily['precipitation_sum'][i],
                temp_high_f=daily['temperature_2m_max'][i],
                temp_low_f=daily['temperature_2m_min'][i],
                source='api',
            )
            db.session.add(log)
            created += 1
        db.session.commit()
        rainfall_7d = _rainfall_summary(garden_id, 7)
        return jsonify({'ok': True, 'days_saved': created, 'rainfall_7d': rainfall_7d})

    @app.route('/api/gardens/<int:garden_id>/watering-status')
    def api_watering_status(garden_id):
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(app.root_path).parents[2])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from apps.ml_service.app.watering_engine import (
            fetch_forecast_today, get_watering_recommendations,
        )

        garden = Garden.query.get_or_404(garden_id)

        # Load weather logs for the last 14 days
        cutoff = date.today() - timedelta(days=14)
        weather_logs = (WeatherLog.query
                        .filter(WeatherLog.garden_id == garden_id,
                                WeatherLog.date >= cutoff)
                        .all())

        # Today's forecast (best-effort; skip if no coordinates)
        forecast_today = None
        if garden.latitude and garden.longitude:
            forecast_today = fetch_forecast_today(garden.latitude, garden.longitude)

        beds = get_watering_recommendations(garden, weather_logs, forecast_today)
        return jsonify({
            'garden_id':       garden_id,
            'date':            date.today().isoformat(),
            'has_weather_data': len(weather_logs) > 0,
            'forecast_today':  forecast_today,
            'beds':            beds,
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

        import json as _json
        canvas_plants = CanvasPlant.query.filter_by(garden_id=garden_id).all()
        canvas_plants_json = _json.dumps([{
            'id':           cp.id,
            'pos_x':        cp.pos_x,
            'pos_y':        cp.pos_y,
            'radius_ft':    cp.radius_ft,
            'color':        cp.color or '#5a9e54',
            'display_mode': cp.display_mode or 'color',
            'library_id':   cp.library_id,
            'plant_id':     cp.plant_id,
            'name':         cp.label or (cp.library_entry.name if cp.library_entry else (cp.plant.name if cp.plant else '?')),
            'image_filename': cp.custom_image or (cp.library_entry.image_filename if cp.library_entry else None),
            'custom_image': cp.custom_image,
        } for cp in canvas_plants])
        garden_json = _json.dumps({
            'id': garden.id,
            'name': garden.name,
            'city': garden.city or '',
            'state': garden.state or '',
            'zip_code': garden.zip_code or '',
            'usda_zone': garden.usda_zone or '',
            'zone_temp_range': garden.zone_temp_range or '',
            'unit': garden.unit or 'ft',
            'latitude': garden.latitude,
            'longitude': garden.longitude,
            'last_frost_date': garden.last_frost_date.isoformat() if garden.last_frost_date else None,
            'watering_frequency_days': garden.watering_frequency_days,
            'rainfall_7d': _rainfall_summary(garden.id, 7),
        })
        px_per_unit = 60
        return render_template('planner.html', garden=garden, all_gardens=all_gardens,
                               library_plants=library_plants,
                               garden_plant_groups=garden_plant_groups,
                               px_per_unit=px_per_unit,
                               garden_json=garden_json,
                               canvas_plants_json=canvas_plants_json)

    @app.route('/api/gardens/<int:garden_id>/upload-background', methods=['POST'])
    def upload_garden_background(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        f = request.files.get('image')
        if not f or not f.filename:
            return jsonify({'error': 'No file provided'}), 400
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            return jsonify({'error': 'Unsupported file type'}), 400
        bg_dir = os.path.join(app.static_folder, 'garden_backgrounds')
        os.makedirs(bg_dir, exist_ok=True)
        # Remove old file if different extension
        if garden.background_image:
            old_path = os.path.join(bg_dir, garden.background_image)
            if os.path.exists(old_path):
                os.remove(old_path)
        filename = f'garden_{garden_id}{ext}'
        f.save(os.path.join(bg_dir, filename))
        garden.background_image = filename
        db.session.commit()
        return jsonify({'filename': filename,
                        'url': url_for('static', filename=f'garden_backgrounds/{filename}')})

    @app.route('/api/gardens/<int:garden_id>/remove-background', methods=['POST'])
    def remove_garden_background(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        if garden.background_image:
            bg_dir = os.path.join(app.static_folder, 'garden_backgrounds')
            old_path = os.path.join(bg_dir, garden.background_image)
            if os.path.exists(old_path):
                os.remove(old_path)
            garden.background_image = None
            db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/gardens/<int:garden_id>/annotations')
    def api_get_annotations(garden_id):
        import json as _json
        garden = Garden.query.get_or_404(garden_id)
        shapes = _json.loads(garden.annotations or '[]')
        return jsonify({'shapes': shapes})

    @app.route('/api/gardens/<int:garden_id>/annotations', methods=['POST'])
    def api_save_annotations(garden_id):
        import json as _json
        garden = Garden.query.get_or_404(garden_id)
        data = request.get_json(force=True)
        garden.annotations = _json.dumps(data.get('shapes', []))
        db.session.commit()
        return jsonify({'ok': True})

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
        next_url = request.form.get('next') or url_for('beds')
        db.session.delete(bed)
        db.session.commit()
        return redirect(next_url)

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
        soil_ph = request.form.get('soil_ph')
        bed.soil_ph = float(soil_ph) if soil_ph else None
        clay_pct = request.form.get('clay_pct')
        bed.clay_pct = float(clay_pct) if clay_pct else None
        compost_pct = request.form.get('compost_pct')
        bed.compost_pct = float(compost_pct) if compost_pct else None
        sand_pct = request.form.get('sand_pct')
        bed.sand_pct = float(sand_pct) if sand_pct else None
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
        next_url = request.form.get('next') or url_for('plants')
        db.session.delete(plant)
        db.session.commit()
        return redirect(next_url)

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
                task_type=request.form.get('task_type') or 'other',
                plant_id=request.form.get('plant_id') or None,
                garden_id=request.form.get('garden_id') or None,
                bed_id=request.form.get('bed_id') or None,
            )
            db.session.add(task)
            db.session.commit()
            return redirect(url_for('tasks'))
        all_tasks = Task.query.order_by(Task.completed.asc(), Task.due_date.asc().nullslast()).all()
        all_plants = Plant.query.order_by(Plant.name).all()
        all_gardens = Garden.query.order_by(Garden.name).all()
        all_beds = GardenBed.query.order_by(GardenBed.name).all()
        return render_template('tasks.html', tasks=all_tasks, plants=all_plants,
                               all_gardens=all_gardens, all_beds=all_beds)

    @app.route('/tasks/<int:task_id>')
    def task_detail(task_id):
        task = Task.query.get_or_404(task_id)
        all_plants = Plant.query.order_by(Plant.name).all()
        all_gardens = Garden.query.order_by(Garden.name).all()
        all_beds = GardenBed.query.order_by(GardenBed.name).all()
        return render_template('task_detail.html', task=task, plants=all_plants,
                               all_gardens=all_gardens, all_beds=all_beds)

    @app.route('/tasks/<int:task_id>/edit', methods=['POST'])
    def edit_task(task_id):
        task = Task.query.get_or_404(task_id)
        due = request.form.get('due_date')
        task.title = request.form['title']
        task.description = request.form.get('description')
        task.due_date = date.fromisoformat(due) if due else None
        task.task_type = request.form.get('task_type') or 'other'
        task.plant_id = request.form.get('plant_id') or None
        task.garden_id = request.form.get('garden_id') or None
        task.bed_id = request.form.get('bed_id') or None
        db.session.commit()
        return redirect(url_for('task_detail', task_id=task.id))

    @app.route('/tasks/<int:task_id>/complete', methods=['POST'])
    def complete_task(task_id):
        task = Task.query.get_or_404(task_id)
        task.completed = not task.completed
        task.completed_date = date.today() if task.completed else None
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
    PERMAPEOPLE_KEY_ID     = os.getenv('X-Permapeople-Key-Id', '')
    PERMAPEOPLE_KEY_SECRET = os.getenv('X-Permapeople-Key-Secret', '')



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

        _MONTH_NAMES = {
            'jan':'January','feb':'February','mar':'March','apr':'April',
            'may':'May','jun':'June','jul':'July','aug':'August',
            'sep':'September','oct':'October','nov':'November','dec':'December'
        }
        def _months(col):
            raw = _parse(col)
            if not raw:
                return None
            return ', '.join(_MONTH_NAMES.get(str(m).lower(), str(m)) for m in raw)

        bloom_months  = _months(entry.bloom_months)
        fruit_months  = _months(entry.fruit_months)
        growth_months = _months(entry.growth_months)

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
        back = request.args.get('back')
        all_gardens = Garden.query.order_by(Garden.name).all()
        return render_template('library_detail.html',
            entry=entry,
            tab=tab,
            back=back,
            good_neighbors=good_neighbors,
            bad_neighbors=bad_neighbors,
            how_to_grow=how_to_grow,
            faqs=faqs,
            nutrition=nutrition,
            calendar_rows=calendar_rows,
            selected_zone=selected_zone,
            all_gardens=all_gardens,
            bloom_months=bloom_months,
            fruit_months=fruit_months,
            growth_months=growth_months,
        )

    @app.route('/library/<int:entry_id>/edit', methods=['GET', 'POST'])
    def library_edit(entry_id):
        entry = PlantLibrary.query.get_or_404(entry_id)
        if request.method == 'POST':
            f = request.form
            entry.name                  = f.get('name', entry.name).strip()
            entry.scientific_name       = f.get('scientific_name', '').strip() or None
            entry.type                  = f.get('type', entry.type)
            entry.difficulty            = f.get('difficulty', '').strip() or None
            entry.family                = f.get('family', '').strip() or None
            entry.layer                 = f.get('layer', '').strip() or None
            entry.edible_parts          = f.get('edible_parts', '').strip() or None
            entry.sunlight              = f.get('sunlight', '').strip() or None
            entry.water                 = f.get('water', '').strip() or None
            entry.spacing_in            = f.get('spacing_in', type=int) or None
            entry.days_to_germination   = f.get('days_to_germination', type=int) or None
            entry.days_to_harvest       = f.get('days_to_harvest', type=int) or None
            entry.min_zone              = f.get('min_zone', type=int) or None
            entry.max_zone              = f.get('max_zone', type=int) or None
            entry.temp_min_f            = f.get('temp_min_f', type=int) or None
            entry.temp_max_f            = f.get('temp_max_f', type=int) or None
            entry.soil_ph_min           = f.get('soil_ph_min', type=float) or None
            entry.soil_ph_max           = f.get('soil_ph_max', type=float) or None
            entry.soil_type             = f.get('soil_type', '').strip() or None
            entry.sow_indoor_weeks      = f.get('sow_indoor_weeks', type=int) or None
            entry.direct_sow_offset     = f.get('direct_sow_offset', type=int) if f.get('direct_sow_offset', '').strip() != '' else None
            entry.transplant_offset     = f.get('transplant_offset', type=int) if f.get('transplant_offset', '').strip() != '' else None
            entry.notes                 = f.get('notes', '').strip() or None
            entry.permapeople_description = f.get('permapeople_description', '').strip() or None
            # JSON fields — validate before saving
            import json as _json
            for field in ('good_neighbors', 'bad_neighbors', 'how_to_grow', 'faqs', 'nutrition'):
                raw = f.get(field, '').strip()
                if raw:
                    try:
                        _json.loads(raw)
                        setattr(entry, field, raw)
                    except ValueError:
                        pass   # ignore invalid JSON; keep existing value
                else:
                    setattr(entry, field, None)
            db.session.commit()
            return redirect(url_for('library_detail', entry_id=entry.id))
        return render_template('library_edit.html', entry=entry)

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

    def _ext_from_content_type(content_type):
        if 'png' in content_type:
            return '.png'
        if 'webp' in content_type:
            return '.webp'
        return '.jpg'

    def _save_plant_image(entry, img_bytes, source, ext='.jpg',
                          source_url=None, attribution=None, make_primary=False):
        """Hash-check img_bytes, save to plant_images/, insert PlantLibraryImage row.
        Returns (PlantLibraryImage row, was_duplicate).  Caller must commit."""
        fhash = hashlib.sha256(img_bytes).hexdigest()
        existing = PlantLibraryImage.query.filter_by(file_hash=fhash).first()
        if existing:
            return existing, True
        count = PlantLibraryImage.query.filter_by(
            plant_library_id=entry.id, source=source
        ).count()
        filename = f'{entry.id}_{source}_{count + 1}{ext}'
        dest = os.path.join(app.static_folder, 'plant_images', filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(img_bytes)
        has_primary = PlantLibraryImage.query.filter_by(
            plant_library_id=entry.id, is_primary=True
        ).first() is not None
        is_primary = make_primary or not has_primary
        img_row = PlantLibraryImage(
            plant_library_id=entry.id,
            filename=filename,
            source=source,
            source_url=source_url,
            attribution=attribution,
            file_hash=fhash,
            is_primary=is_primary,
        )
        db.session.add(img_row)
        if is_primary:
            entry.image_filename = filename
        return img_row, False

    def _download_plant_image(perenual_id, image_url):
        """Legacy helper: download from URL, save as <perenual_id>.jpg.
        Returns filename on success, None on failure. Does NOT insert PlantLibraryImage row."""
        filename = f'{perenual_id}.jpg'
        dest = os.path.join(app.static_folder, 'plant_images', filename)
        if os.path.exists(dest):
            return filename
        try:
            r = http.get(image_url, timeout=10, stream=True)
            r.raise_for_status()
            content_type = r.headers.get('content-type', '')
            ext = _ext_from_content_type(content_type)
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
        try:
            r = http.get(url, timeout=10)
            r.raise_for_status()
            ext = _ext_from_content_type(r.headers.get('content-type', ''))
            img_row, _ = _save_plant_image(entry, r.content, 'perenual',
                                           ext=ext, source_url=url)
            db.session.commit()
        except Exception:
            return jsonify({'error': 'download', 'message': 'Failed to download image.'}), 502
        return jsonify({'ok': True, 'filename': img_row.filename})

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
        entry = PlantLibrary(
            name=data['name'],
            scientific_name=data.get('scientific_name') or None,
            perenual_id=perenual_id,
            type=data.get('cycle') or None,
            sunlight=sunlight,
            water=water,
        )
        db.session.add(entry)
        db.session.flush()  # get entry.id before downloading image
        if perenual_id and data.get('image'):
            try:
                r = http.get(data['image'], timeout=10)
                r.raise_for_status()
                ext = _ext_from_content_type(r.headers.get('content-type', ''))
                _save_plant_image(entry, r.content, 'perenual',
                                  ext=ext, source_url=data['image'])
            except Exception:
                pass  # image fetch failure is non-fatal
        db.session.commit()
        return jsonify({'ok': True, 'id': entry.id, 'existing': False})

    def _permapeople_post(path, body):
        """POST to Permapeople API; return (data, err_type, err_msg)."""
        if not PERMAPEOPLE_KEY_ID or not PERMAPEOPLE_KEY_SECRET:
            return None, 'config', 'Permapeople credentials not configured.'
        headers = {
            'x-permapeople-key-id': PERMAPEOPLE_KEY_ID,
            'x-permapeople-key-secret': PERMAPEOPLE_KEY_SECRET,
            'Content-Type': 'application/json',
        }
        try:
            resp = http.post(f'https://permapeople.org/api/{path}', json=body, headers=headers, timeout=8)
        except http.exceptions.Timeout:
            return None, 'network', 'Request to Permapeople timed out.'
        except http.exceptions.RequestException as e:
            return None, 'network', f'Network error: {e}'
        if resp.status_code == 401:
            return None, 'auth', 'Invalid Permapeople credentials.'
        if not resp.ok:
            return None, 'api', f'Permapeople returned HTTP {resp.status_code}.'
        return resp.json(), None, None

    @app.route('/api/permapeople/search', methods=['POST'])
    def api_permapeople_search():
        body = request.get_json(force=True) or {}
        q = (body.get('q') or '').strip()
        if not q:
            return jsonify({'results': []})
        data, err_type, err_msg = _permapeople_post('search', {'q': q})
        if err_type:
            return jsonify({'error': err_type, 'message': err_msg}), 502
        results = []
        for p in data.get('plants', []):
            kv = {item['key']: item['value'] for item in (p.get('data') or []) if 'key' in item}
            results.append({
                'permapeople_id': p.get('id'),
                'name': p.get('name'),
                'scientific_name': p.get('scientific_name'),
                'description': p.get('description'),
                'link': p.get('link'),
                'water': kv.get('Water requirement'),
                'sunlight': kv.get('Light requirement'),
                'zone': kv.get('USDA Hardiness zone'),
                'family': kv.get('Family'),
                'layer': kv.get('Layer'),
            })
        return jsonify({'results': results})

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
        bed = GardenBed.query.get_or_404(bed_id)
        data = request.get_json(force=True)
        if not data or 'grid_x' not in data or 'grid_y' not in data:
            return jsonify({'error': 'grid_x and grid_y required'}), 400
        grid_x, grid_y = int(data['grid_x']), int(data['grid_y'])
        spacing_in = int(data.get('spacing_in', 12))

        # Bounds check: plant footprint must fit within bed dimensions
        bed_w_in = bed.width_ft * 12
        bed_h_in = bed.height_ft * 12
        if grid_x + spacing_in > bed_w_in or grid_y + spacing_in > bed_h_in:
            return jsonify({'error': 'plant does not fit within bed bounds'}), 400

        # Overlap check: no other plant's footprint may intersect
        for existing in bed.bed_plants:
            if existing.grid_x is None or existing.grid_y is None:
                continue
            ex_entry = existing.plant.library_entry if existing.plant else None
            ex_spacing = ex_entry.spacing_in if ex_entry and ex_entry.spacing_in else 12
            # AABB overlap test
            if not (grid_x >= existing.grid_x + ex_spacing or
                    existing.grid_x >= grid_x + spacing_in or
                    grid_y >= existing.grid_y + ex_spacing or
                    existing.grid_y >= grid_y + spacing_in):
                return jsonify({'error': 'overlaps existing plant'}), 409

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
            'plant_id': plant.id,
            'library_id': plant.library_id,
            'plant_name': plant.name,
            'image_filename': entry.image_filename if entry else None,
            'spacing_in': entry.spacing_in if entry and entry.spacing_in else 12,
        })

    @app.route('/api/bedplants/<int:bp_id>/care', methods=['POST'])
    def api_bedplant_care(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        data = request.get_json(force=True)
        def _d(val):
            return date.fromisoformat(val) if val else None
        if 'last_watered'    in data: bp.last_watered    = _d(data['last_watered'])
        if 'last_fertilized' in data: bp.last_fertilized = _d(data['last_fertilized'])
        if 'last_harvest'    in data: bp.last_harvest    = _d(data['last_harvest'])
        if 'health_notes'    in data: bp.health_notes    = data['health_notes'] or None
        # Also save plant-level fields
        if bp.plant:
            if 'planted_date'    in data: bp.plant.planted_date    = _d(data['planted_date'])
            if 'transplant_date' in data: bp.plant.transplant_date = _d(data['transplant_date'])
            if 'plant_notes'     in data: bp.plant.notes           = data['plant_notes'] or None
        if 'stage' in data: bp.stage = data['stage'] or None
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/bedplants/bulk-care', methods=['POST'])
    def api_bedplants_bulk_care():
        data = request.get_json(force=True)
        ids = data.get('ids', [])
        def _d(val):
            return date.fromisoformat(val) if val else None
        updated = 0
        for bp_id in ids:
            bp = BedPlant.query.get(bp_id)
            if not bp:
                continue
            if 'last_watered'    in data: bp.last_watered    = _d(data['last_watered'])
            if 'last_fertilized' in data: bp.last_fertilized = _d(data['last_fertilized'])
            if 'last_harvest'    in data: bp.last_harvest    = _d(data['last_harvest'])
            if 'health_notes'    in data: bp.health_notes    = data['health_notes'] or None
            if 'stage'           in data: bp.stage           = data['stage'] or None
            if bp.plant:
                if 'planted_date'    in data: bp.plant.planted_date    = _d(data['planted_date'])
                if 'transplant_date' in data: bp.plant.transplant_date = _d(data['transplant_date'])
                if 'plant_notes'     in data: bp.plant.notes           = data['plant_notes'] or None
            updated += 1
        db.session.commit()
        return jsonify({'ok': True, 'updated': updated})

    @app.route('/api/bedplants/<int:bp_id>')
    def api_bedplant_detail(bp_id):
        bp = BedPlant.query.get_or_404(bp_id)
        entry = bp.plant.library_entry if bp.plant else None
        plant = bp.plant
        return jsonify({
            'id': bp.id,
            'plant_id': plant.id if plant else None,
            'plant_name': plant.name if plant else '?',
            'image_filename': entry.image_filename if entry else None,
            'scientific_name': entry.scientific_name if entry else None,
            'spacing_in': entry.spacing_in if entry else None,
            'sunlight': entry.sunlight if entry else None,
            'water': entry.water if entry else None,
            'days_to_harvest': entry.days_to_harvest if entry else None,
            'planted_date':    plant.planted_date.isoformat()    if plant and plant.planted_date    else None,
            'transplant_date': plant.transplant_date.isoformat() if plant and plant.transplant_date else None,
            'plant_notes':     plant.notes or '',
            'last_watered':    bp.last_watered.isoformat()    if bp.last_watered    else None,
            'last_fertilized': bp.last_fertilized.isoformat() if bp.last_fertilized else None,
            'last_harvest':    bp.last_harvest.isoformat()    if bp.last_harvest    else None,
            'health_notes':    bp.health_notes or '',
            'stage':           bp.stage or 'seedling',
        })

    @app.route('/api/plants/<int:plant_id>/detail')
    def api_plant_detail(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        entry = plant.library_entry
        # Find first BedPlant for this plant (if any)
        bp = plant.bed_plants[0] if plant.bed_plants else None
        return jsonify({
            'id': plant.id,
            'plant_name': plant.name,
            'bp_id': bp.id if bp else None,
            'image_filename': entry.image_filename if entry else None,
            'scientific_name': entry.scientific_name if entry else None,
            'spacing_in': entry.spacing_in if entry else None,
            'sunlight': entry.sunlight if entry else None,
            'water': entry.water if entry else None,
            'days_to_harvest': entry.days_to_harvest if entry else None,
            'planted_date':    plant.planted_date.isoformat()    if plant.planted_date    else None,
            'transplant_date': plant.transplant_date.isoformat() if plant.transplant_date else None,
            'plant_notes':     plant.notes or '',
            'last_watered':    bp.last_watered.isoformat()    if bp and bp.last_watered    else None,
            'last_fertilized': bp.last_fertilized.isoformat() if bp and bp.last_fertilized else None,
            'last_harvest':    bp.last_harvest.isoformat()    if bp and bp.last_harvest    else None,
            'health_notes':    bp.health_notes or '' if bp else '',
        })

    @app.route('/api/plants/<int:plant_id>/care', methods=['POST'])
    def api_plant_care(plant_id):
        plant = Plant.query.get_or_404(plant_id)
        data = request.get_json(force=True)
        def _d(val):
            return date.fromisoformat(val) if val else None
        if 'planted_date'    in data: plant.planted_date    = _d(data['planted_date'])
        if 'transplant_date' in data: plant.transplant_date = _d(data['transplant_date'])
        if 'plant_notes'     in data: plant.notes           = data['plant_notes'] or None
        db.session.commit()
        return jsonify({'ok': True})

    # ── Canvas Plants ──────────────────────────────────────────────────────────

    def _cp_color_for_type(plant_type):
        return {
            'vegetable': '#5a9e54',
            'herb':      '#8bc34a',
            'fruit':     '#ff8c42',
            'flower':    '#e91e8c',
        }.get((plant_type or '').lower(), '#5a9e54')

    def _serialize_cp(cp):
        lib = cp.library_entry
        return {
            'id':           cp.id,
            'pos_x':        cp.pos_x,
            'pos_y':        cp.pos_y,
            'radius_ft':    cp.radius_ft,
            'color':        cp.color or '#5a9e54',
            'display_mode': cp.display_mode or 'color',
            'library_id':   cp.library_id,
            'plant_id':     cp.plant_id,
            'name':         cp.label or (lib.name if lib else (cp.plant.name if cp.plant else '?')),
            'image_filename': cp.custom_image or (lib.image_filename if lib else None),
            'custom_image': cp.custom_image,
            'scientific_name': lib.scientific_name if lib else None,
            'sunlight':     lib.sunlight   if lib else None,
            'water':        lib.water      if lib else None,
            'spacing_in':   lib.spacing_in if lib else None,
            'lib_notes':    lib.notes      if lib else None,
            'planted_date':    cp.plant.planted_date.isoformat()    if cp.plant and cp.plant.planted_date    else None,
            'transplant_date': cp.plant.transplant_date.isoformat() if cp.plant and cp.plant.transplant_date else None,
            'plant_notes':     cp.plant.notes or ''                 if cp.plant                              else '',
        }

    @app.route('/api/gardens/<int:garden_id>/canvas-plants', methods=['GET'])
    def api_canvas_plants_list(garden_id):
        Garden.query.get_or_404(garden_id)
        cps = CanvasPlant.query.filter_by(garden_id=garden_id).all()
        return jsonify([_serialize_cp(cp) for cp in cps])

    @app.route('/api/gardens/<int:garden_id>/canvas-plants', methods=['POST'])
    def api_canvas_plants_create(garden_id):
        garden = Garden.query.get_or_404(garden_id)
        data = request.get_json(force=True)
        library_id = data.get('library_id')
        plant_id   = data.get('plant_id')
        pos_x      = float(data.get('pos_x', 0))
        pos_y      = float(data.get('pos_y', 0))

        lib = PlantLibrary.query.get(library_id) if library_id else None
        plant = Plant.query.get(plant_id) if plant_id else None

        # Create a Plant record if dragged from library with no existing plant
        if lib and not plant:
            plant = Plant(name=lib.name, library_id=lib.id, garden_id=garden_id, status='planning')
            db.session.add(plant)
            db.session.flush()

        # Default radius from library spacing (spacing is diameter, halved for radius)
        if lib and lib.spacing_in:
            radius_ft = round((lib.spacing_in / 12) / 2, 2)
        else:
            radius_ft = 1.0
        radius_ft = max(0.25, radius_ft)

        color = _cp_color_for_type(lib.type if lib else None)

        cp = CanvasPlant(
            garden_id=garden_id,
            library_id=library_id,
            plant_id=plant.id if plant else None,
            pos_x=pos_x,
            pos_y=pos_y,
            radius_ft=radius_ft,
            color=color,
            display_mode='color',
        )
        db.session.add(cp)
        db.session.commit()
        return jsonify({'ok': True, 'canvas_plant': _serialize_cp(cp)})

    @app.route('/api/canvas-plants/<int:cp_id>', methods=['GET'])
    def api_canvas_plant_detail(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        return jsonify(_serialize_cp(cp))

    @app.route('/api/canvas-plants/<int:cp_id>/position', methods=['POST'])
    def api_canvas_plant_position(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        data = request.get_json(force=True)
        cp.pos_x = float(data.get('x', cp.pos_x))
        cp.pos_y = float(data.get('y', cp.pos_y))
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/canvas-plants/<int:cp_id>/radius', methods=['POST'])
    def api_canvas_plant_radius(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        data = request.get_json(force=True)
        cp.radius_ft = max(0.1, float(data.get('radius_ft', cp.radius_ft)))
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/canvas-plants/<int:cp_id>/appearance', methods=['POST'])
    def api_canvas_plant_appearance(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        data = request.get_json(force=True)
        if 'color'        in data: cp.color        = data['color'] or cp.color
        if 'display_mode' in data: cp.display_mode = data['display_mode'] or cp.display_mode
        if 'label'        in data: cp.label        = data['label'] or None
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/canvas-plants/<int:cp_id>/upload-image', methods=['POST'])
    def api_canvas_plant_upload_image(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        f = request.files.get('image')
        if not f or not f.filename:
            return jsonify({'error': 'No file provided'}), 400
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            return jsonify({'error': 'Unsupported file type'}), 400
        img_dir = os.path.join(app.static_folder, 'canvas_plant_images')
        os.makedirs(img_dir, exist_ok=True)
        # Remove old custom image if present
        if cp.custom_image:
            old_path = os.path.join(img_dir, cp.custom_image)
            if os.path.exists(old_path):
                os.remove(old_path)
        filename = f'cp_{cp_id}{ext}'
        f.save(os.path.join(img_dir, filename))
        cp.custom_image  = filename
        cp.display_mode  = 'image'
        db.session.commit()
        return jsonify({'ok': True, 'filename': filename, 'url': f'/static/canvas_plant_images/{filename}'})

    @app.route('/api/canvas-plants/<int:cp_id>/save-image-to-library', methods=['POST'])
    def api_canvas_plant_save_image_to_library(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        if not cp.custom_image or not cp.library_id:
            return jsonify({'error': 'No custom image or library entry'}), 400
        lib = PlantLibrary.query.get_or_404(cp.library_id)
        src = os.path.join(app.static_folder, 'canvas_plant_images', cp.custom_image)
        if not os.path.exists(src):
            return jsonify({'error': 'Image file not found'}), 404
        ext = os.path.splitext(cp.custom_image)[1]
        with open(src, 'rb') as f:
            img_bytes = f.read()
        img_row, was_dup = _save_plant_image(lib, img_bytes, 'manual',
                                             ext=ext, make_primary=True)
        db.session.commit()
        return jsonify({'ok': True, 'library_image': img_row.filename})

    # --- Library image management ---

    @app.route('/api/library/<int:entry_id>/images', methods=['GET'])
    def api_library_images_list(entry_id):
        entry = PlantLibrary.query.get_or_404(entry_id)
        return jsonify([{
            'id': img.id,
            'filename': img.filename,
            'source': img.source,
            'attribution': img.attribution,
            'is_primary': img.is_primary,
            'created_at': img.created_at.isoformat(),
        } for img in entry.images])

    @app.route('/api/library/<int:entry_id>/images', methods=['POST'])
    def api_library_images_add(entry_id):
        entry = PlantLibrary.query.get_or_404(entry_id)
        # Accept file upload or JSON {url, source, attribution}
        if request.files.get('file'):
            f = request.files['file']
            ext = os.path.splitext(secure_filename(f.filename))[1].lower() or '.jpg'
            img_bytes = f.read()
            source = request.form.get('source', 'manual')
            attribution = request.form.get('attribution') or None
            source_url = None
        else:
            data = request.get_json(force=True) or {}
            url = data.get('url', '').strip()
            if not url:
                return jsonify({'error': 'url or file required'}), 400
            source = data.get('source', 'manual')
            attribution = data.get('attribution') or None
            try:
                r = http.get(url, timeout=15)
                r.raise_for_status()
                ext = _ext_from_content_type(r.headers.get('content-type', ''))
                img_bytes = r.content
            except Exception as e:
                return jsonify({'error': 'download', 'message': str(e)}), 502
            source_url = url
        img_row, was_dup = _save_plant_image(entry, img_bytes, source, ext=ext,
                                             source_url=source_url, attribution=attribution)
        db.session.commit()
        return jsonify({
            'ok': True,
            'image_id': img_row.id,
            'filename': img_row.filename,
            'was_duplicate': was_dup,
        })

    @app.route('/api/library/images/<int:image_id>/set-primary', methods=['POST'])
    def api_library_image_set_primary(image_id):
        img = PlantLibraryImage.query.get_or_404(image_id)
        PlantLibraryImage.query.filter_by(
            plant_library_id=img.plant_library_id, is_primary=True
        ).update({'is_primary': False})
        img.is_primary = True
        entry = PlantLibrary.query.get(img.plant_library_id)
        entry.image_filename = img.filename
        db.session.commit()
        return jsonify({'ok': True, 'filename': img.filename})

    @app.route('/api/library/images/<int:image_id>/delete', methods=['POST'])
    def api_library_image_delete(image_id):
        img = PlantLibraryImage.query.get_or_404(image_id)
        was_primary = img.is_primary
        plant_library_id = img.plant_library_id
        filename = img.filename
        db.session.delete(img)
        db.session.flush()
        # Delete file from disk if no other row references it
        remaining = PlantLibraryImage.query.filter_by(filename=filename).count()
        if remaining == 0:
            fpath = os.path.join(app.static_folder, 'plant_images', filename)
            if os.path.exists(fpath):
                os.remove(fpath)
        new_primary_filename = None
        if was_primary:
            next_img = PlantLibraryImage.query.filter_by(
                plant_library_id=plant_library_id
            ).order_by(PlantLibraryImage.created_at).first()
            if next_img:
                next_img.is_primary = True
                new_primary_filename = next_img.filename
            entry = PlantLibrary.query.get(plant_library_id)
            entry.image_filename = new_primary_filename
        db.session.commit()
        return jsonify({'ok': True, 'new_primary_filename': new_primary_filename})

    @app.route('/api/library/<int:entry_id>/quick-edit', methods=['POST'])
    def api_library_quick_edit(entry_id):
        lib = PlantLibrary.query.get_or_404(entry_id)
        data = request.get_json(force=True)
        if 'sunlight'   in data and data['sunlight']   is not None: lib.sunlight   = data['sunlight']
        if 'water'      in data and data['water']      is not None: lib.water      = data['water']
        if 'spacing_in' in data and data['spacing_in'] is not None: lib.spacing_in = int(data['spacing_in'])
        if 'notes'      in data and data['notes']      is not None: lib.notes      = data['notes']
        db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/canvas-plants/<int:cp_id>/delete', methods=['POST'])
    def api_canvas_plant_delete(cp_id):
        cp = CanvasPlant.query.get_or_404(cp_id)
        if cp.custom_image:
            img_path = os.path.join(app.static_folder, 'canvas_plant_images', cp.custom_image)
            if os.path.exists(img_path):
                os.remove(img_path)
        db.session.delete(cp)
        db.session.commit()
        return jsonify({'ok': True})

    # ── Plant Recommendations ─────────────────────────────────────────────────

    @app.route('/api/recommendations')
    def api_recommendations():
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(app.root_path).parents[2])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from apps.ml_service.app.recommender import recommend

        garden_id = request.args.get('garden_id', type=int)
        top_n     = request.args.get('top_n', 5, type=int)

        garden = Garden.query.get(garden_id) if garden_id else None

        # Build context from garden data
        zone_str = (garden.usda_zone or '') if garden else ''
        zone_num_str = ''.join(c for c in zone_str if c.isdigit())
        zone_int = int(zone_num_str) if zone_num_str else None

        phs = [b.soil_ph for b in garden.beds if b.soil_ph] if garden else []
        avg_ph = sum(phs) / len(phs) if phs else None

        current_plant_names = []
        if garden:
            for p in garden.plants:
                if p.library_entry:
                    current_plant_names.append(p.library_entry.name)

        context = {
            'zone':                zone_int,
            'sunlight_hours':      6,           # default; no garden-level field yet
            'current_month':       date.today().month,
            'soil_ph':             avg_ph,
            'preferred_types':     ['vegetable', 'herb'],
            'current_plant_names': current_plant_names,
        }

        # Serialise PlantLibrary rows, excluding plants already in this garden
        existing_names = set(current_plant_names)
        all_lib = PlantLibrary.query.order_by(PlantLibrary.name).all()
        plants_data = []
        for p in all_lib:
            if p.name in existing_names:
                continue
            primary_img = next((img for img in p.images if img.is_primary), None)
            if not primary_img and p.images:
                primary_img = p.images[0]
            plants_data.append({
                'id':              p.id,
                'name':            p.name,
                'type':            p.type,
                'min_zone':        p.min_zone,
                'max_zone':        p.max_zone,
                'sunlight':        p.sunlight,
                'soil_ph_min':     p.soil_ph_min,
                'soil_ph_max':     p.soil_ph_max,
                'good_neighbors':  p.good_neighbors,
                'difficulty':      p.difficulty,
                'days_to_harvest': p.days_to_harvest,
                'fruit_months':    p.fruit_months,
                'bloom_months':    p.bloom_months,
                'growth_months':   p.growth_months,
                'image_filename':  primary_img.filename if primary_img else p.image_filename,
            })

        results = recommend(plants_data, context, top_n)

        # Attach image URLs
        for rec in results:
            fn = rec.get('image_filename')
            rec['image_url'] = (
                url_for('static', filename=f'plant_images/{fn}') if fn else None
            )

        return jsonify({'recommendations': results, 'context': {
            'zone': zone_int, 'month': context['current_month'],
        }})

    # ── AI Chat ───────────────────────────────────────────────────────────────

    @app.route('/api/chat', methods=['POST'])
    def api_chat():
        import sys as _sys
        from pathlib import Path as _Path
        _root = str(_Path(app.root_path).parents[2])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from apps.ml_service.app.recommender import recommend

        data                 = request.get_json(force=True)
        user_msg             = (data.get('message') or '').strip()
        garden_id            = data.get('garden_id')
        conversation_history = data.get('conversation_history') or []

        if not user_msg:
            return jsonify({'reply': 'Please type a message first.'}), 400

        # Build garden context for the system prompt
        garden = Garden.query.get(garden_id) if garden_id else None
        today  = date.today()
        season, _ = _get_season(today)

        zone_str     = (garden.usda_zone or 'unknown') if garden else 'unknown'
        zone_num_str = ''.join(c for c in zone_str if c.isdigit())
        zone_int     = int(zone_num_str) if zone_num_str else None

        garden_name    = garden.name if garden else 'your garden'
        current_plants: list[str] = []
        if garden:
            for p in garden.plants:
                current_plants.append(p.library_entry.name if p.library_entry else p.name)

        # Get top 3 recommendations to give the assistant context
        rec_names: list[str] = []
        try:
            phs    = [b.soil_ph for b in garden.beds if b.soil_ph] if garden else []
            avg_ph = sum(phs) / len(phs) if phs else None
            existing = set(current_plants)
            all_lib = PlantLibrary.query.all()
            plants_data = []
            for p in all_lib:
                if p.name in existing:
                    continue
                plants_data.append({
                    'id': p.id, 'name': p.name, 'type': p.type,
                    'min_zone': p.min_zone, 'max_zone': p.max_zone,
                    'sunlight': p.sunlight,
                    'soil_ph_min': p.soil_ph_min, 'soil_ph_max': p.soil_ph_max,
                    'good_neighbors': p.good_neighbors, 'difficulty': p.difficulty,
                    'days_to_harvest': p.days_to_harvest,
                    'fruit_months': p.fruit_months,
                    'bloom_months': p.bloom_months,
                    'growth_months': p.growth_months,
                })
            ctx = {
                'zone': zone_int, 'sunlight_hours': 6,
                'current_month': today.month, 'soil_ph': avg_ph,
                'preferred_types': ['vegetable', 'herb'],
                'current_plant_names': current_plants,
            }
            recs = recommend(plants_data, ctx, top_n=3)
            rec_names = [r['name'] for r in recs]
        except Exception:
            pass

        system_prompt = (
            f"You are a knowledgeable, friendly garden assistant helping a home gardener. "
            f"Today is {today.strftime('%B %d, %Y')} — {season} in the Northern Hemisphere.\n\n"
            f"Garden: {garden_name}\n"
            f"USDA Hardiness Zone: {zone_str}\n"
            f"Current plants: {', '.join(current_plants) if current_plants else 'none yet'}\n"
            f"Top recommendations right now: {', '.join(rec_names) if rec_names else 'see library'}\n\n"
            "Give practical, concise advice tailored to this specific garden and zone. "
            "Use the available tools to look up real data before answering when relevant. "
            "If asked what to plant, prioritise the recommended plants above. "
            "Keep responses under 200 words unless the question genuinely needs more detail."
        )

        # Build full message list: conversation history + new user message
        messages = list(conversation_history) + [{'role': 'user', 'content': user_msg}]

        try:
            from apps.ml_service.app.chat_tools import run_agentic_loop
            reply = run_agentic_loop(system_prompt, messages, garden)
        except RuntimeError as exc:
            return jsonify({'reply': str(exc), 'conversation_history': messages})
        except Exception as exc:
            reply = f'Sorry, the assistant ran into an error: {exc}'

        return jsonify({'reply': reply, 'conversation_history': messages})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
