"""Flywheel label backfill: a snapshot is only labelled once its "next day" has
elapsed *and* been recorded.

Regression for the always-negative labels found on 2026-08-05 — 66 labelled
rows, 0 positives, every rain_next_day_mm 0.0 — caused by labelling yesterday's
snapshot from today's (nonexistent) data at 4 AM.
"""
from datetime import date, timedelta

import pytest

from apps.backend.app.db.models import (
    GardenBed, MlWateringSnapshot, WateringEvent, WeatherLog,
)
from apps.backend.app.jobs.ml_snapshot import _backfill_labels


@pytest.fixture
def second_bed(db, garden):
    b = GardenBed(name='Raised Bed B', garden_id=garden.id, width_ft=4.0, height_ft=4.0)
    db.add(b)
    db.flush()
    return b


def _snapshot(db, garden, bed, day):
    snap = MlWateringSnapshot(garden_id=garden.id, bed_id=bed.id, snapshot_date=day)
    db.add(snap)
    db.flush()
    return snap


def test_labels_the_day_whose_outcome_is_known(db, garden, bed):
    """D-2's snapshot is labelled from D-1's rows."""
    snap_day = date.today() - timedelta(days=2)
    outcome_day = date.today() - timedelta(days=1)
    snap = _snapshot(db, garden, bed, snap_day)
    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id, event_date=outcome_day,
                         amount='moderate', source='rain'))
    db.add(WeatherLog(garden_id=garden.id, date=outcome_day, rainfall_in=1.0, source='api'))
    db.flush()

    assert _backfill_labels(db, garden.id) == 1
    assert snap.watered_next_day is True
    assert snap.watered_amount == 'moderate'
    assert snap.rain_next_day_mm == 25.4


def test_yesterdays_snapshot_is_left_alone(db, garden, bed):
    """D-1's outcome day is today — still in progress, so it must stay unlabelled
    rather than be recorded as a definitive 'not watered'."""
    snap = _snapshot(db, garden, bed, date.today() - timedelta(days=1))

    assert _backfill_labels(db, garden.id) == 0
    assert snap.watered_next_day is None


def test_records_a_dry_unwatered_day_as_negative(db, garden, bed):
    snap = _snapshot(db, garden, bed, date.today() - timedelta(days=2))
    db.add(WeatherLog(garden_id=garden.id, date=date.today() - timedelta(days=1),
                      rainfall_in=0.0, source='api'))
    db.flush()

    assert _backfill_labels(db, garden.id) == 1
    assert snap.watered_next_day is False
    assert snap.watered_amount is None
    assert snap.rain_next_day_mm == 0.0


def test_recovers_snapshots_missed_by_a_failed_night(db, garden, bed):
    """A night the job didn't run used to leave a permanent null (2026-08-01)."""
    old_day = date.today() - timedelta(days=5)
    snap = _snapshot(db, garden, bed, old_day)
    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id,
                         event_date=old_day + timedelta(days=1),
                         amount='heavy', source='user'))
    db.flush()

    assert _backfill_labels(db, garden.id) == 1
    assert snap.watered_next_day is True
    assert snap.watered_amount == 'heavy'


def test_ignores_snapshots_past_the_retention_edge(db, garden, bed):
    """Source rows are pruned at 7 days; labelling older snapshots from missing
    data would silently write false negatives."""
    snap = _snapshot(db, garden, bed, date.today() - timedelta(days=12))

    assert _backfill_labels(db, garden.id) == 0
    assert snap.watered_next_day is None


def test_matches_events_to_their_own_bed_and_day(db, garden, bed, second_bed):
    """Two beds, one watered — the label must not bleed across beds."""
    snap_day = date.today() - timedelta(days=2)
    watered = _snapshot(db, garden, bed, snap_day)
    dry = _snapshot(db, garden, second_bed, snap_day)
    db.add(WateringEvent(garden_id=garden.id, bed_id=bed.id,
                         event_date=snap_day + timedelta(days=1),
                         amount='light', source='user'))
    db.flush()

    assert _backfill_labels(db, garden.id) == 2
    assert watered.watered_next_day is True
    assert dry.watered_next_day is False


def test_already_labelled_snapshots_are_not_revisited(db, garden, bed):
    snap = _snapshot(db, garden, bed, date.today() - timedelta(days=3))
    snap.watered_next_day = False
    db.flush()

    assert _backfill_labels(db, garden.id) == 0
