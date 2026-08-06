"""Rain heavy enough to soak a bed counts as a watering — same as the gardener
doing it by hand (WateringEvent + last_watered)."""
from datetime import date, timedelta

import pytest

from apps.backend.app.db.models import BedPlant, WateringEvent, WeatherLog
from apps.backend.app.services.helpers import apply_rain_as_watering
from apps.ml_service.app.watering_engine import rain_watering_amount


@pytest.mark.parametrize('rainfall_in, expected', [
    (None,  None),        # no data
    (0.0,   None),
    (0.05,  None),        # trace — fully intercepted
    (0.20,  None),        # 5.1mm raw -> 3.1mm effective, below the 5mm floor
    (0.30,  'light'),     # 7.6mm raw -> 5.6mm effective
    (0.45,  'moderate'),  # 11.4mm    -> 9.4mm
    (0.75,  'heavy'),     # 19.1mm    -> 17.1mm
    (2.03,  'heavy'),     # the real 2026-08-02 rain
])
def test_rain_watering_amount_bands(rainfall_in, expected):
    assert rain_watering_amount(rainfall_in) == expected


def _log_rain(db, garden, day, inches):
    db.add(WeatherLog(garden_id=garden.id, date=day, rainfall_in=inches, source='api'))
    db.flush()


def test_soaking_rain_credits_bed_and_resets_last_watered(db, garden, bed, plant_in_bed):
    rain_day = date.today() - timedelta(days=2)
    _log_rain(db, garden, rain_day, 0.75)

    created = apply_rain_as_watering(db, garden)
    db.flush()

    assert created == 1
    ev = db.query(WateringEvent).one()
    assert (ev.bed_id, ev.event_date, ev.amount, ev.source) == (bed.id, rain_day, 'heavy', 'rain')

    bp = db.query(BedPlant).filter_by(bed_id=bed.id).one()
    assert bp.last_watered == rain_day
    assert bp.plant.last_watered == rain_day


def test_light_rain_is_not_a_watering(db, garden, bed, plant_in_bed):
    _log_rain(db, garden, date.today() - timedelta(days=1), 0.15)

    assert apply_rain_as_watering(db, garden) == 0
    assert db.query(WateringEvent).count() == 0
    assert db.query(BedPlant).filter_by(bed_id=bed.id).one().last_watered is None


def test_is_idempotent_across_reruns(db, garden, bed, plant_in_bed):
    _log_rain(db, garden, date.today() - timedelta(days=2), 0.75)

    assert apply_rain_as_watering(db, garden) == 1
    db.flush()
    assert apply_rain_as_watering(db, garden) == 0, 'second run must not duplicate the event'
    assert db.query(WateringEvent).count() == 1


def test_does_not_roll_back_a_more_recent_watering(db, garden, bed, plant_in_bed):
    """An older rain day must not overwrite a watering the gardener logged since."""
    watered_on = date.today() - timedelta(days=1)
    bp = db.query(BedPlant).filter_by(bed_id=bed.id).one()
    bp.last_watered = watered_on
    _log_rain(db, garden, date.today() - timedelta(days=4), 0.75)
    db.flush()

    apply_rain_as_watering(db, garden)
    db.flush()

    assert bp.last_watered == watered_on


def test_gardener_logged_event_wins_for_the_same_day(db, garden, bed, plant_in_bed):
    day = date.today() - timedelta(days=2)
    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id, event_date=day,
                         amount='light', source='user'))
    _log_rain(db, garden, day, 0.75)
    db.flush()

    assert apply_rain_as_watering(db, garden) == 0
    assert db.query(WateringEvent).one().source == 'user'


def test_empty_bed_is_not_credited(db, garden, bed):
    """No plants in the bed — nothing to water, so no training signal either."""
    _log_rain(db, garden, date.today() - timedelta(days=2), 0.75)

    assert apply_rain_as_watering(db, garden) == 0
    assert db.query(WateringEvent).count() == 0


def test_log_rain_endpoint_credits_the_bed(client, db, garden, bed, plant_in_bed):
    day = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post(f'/api/gardens/{garden.id}/log-rain',
                       json={'rainfall_in': 1.0, 'entry_date': day})

    assert resp.status_code == 200
    ev = db.query(WateringEvent).one()
    assert (ev.source, ev.amount, ev.event_date.isoformat()) == ('rain', 'heavy', day)
