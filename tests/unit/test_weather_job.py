"""run_daily_weather_fetch: a per-garden DB error must be caught, rolled back,
and must not escape (regression for the nightly 500 on 2026-07-21)."""
from apps.backend.app.routers import weather as weather_mod


def test_garden_fetch_error_is_swallowed_and_rolled_back(db, garden, monkeypatch):
    # SessionLocal() is called inside the job; hand it the test session (whose
    # engine already has the `garden` fixture) and neutralise close().
    monkeypatch.setattr(weather_mod, 'SessionLocal', lambda: db)
    monkeypatch.setattr(db, 'close', lambda: None)

    rollbacks = []
    real_rollback = db.rollback
    monkeypatch.setattr(db, 'rollback', lambda: (rollbacks.append(1), real_rollback())[1])

    def boom(_db, _gid):
        raise RuntimeError('column does not exist')

    monkeypatch.setattr(weather_mod, '_fetch_weather_for_garden', boom)

    # Must not raise even though the only garden's fetch blows up.
    weather_mod.run_daily_weather_fetch()

    assert rollbacks, 'expected db.rollback() after a per-garden failure'
