from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar.testing import TestClient

from server import db
from server.app import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """An in-process client against a throwaway database — no container needed, so this suite stays fast."""
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "sqlite" / "main.db"))
    with TestClient(app=app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_index_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Meditation Timer" in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    for path in ("/static/styles.css", "/static/js/app.js", "/static/js/bells.js", "/static/js/player.js"):
        assert client.get(path).status_code == 200, path


def test_bell_catalog_describes_every_voice(client: TestClient) -> None:
    voices = client.get("/api/bells").json()
    assert {voice["id"] for voice in voices} == {
        "singing-bowl",
        "temple-bell",
        "deep-gong",
        "crystal-bowl",
        "chime",
        "wood-block",
    }
    for voice in voices:
        assert voice["partials"], voice["id"]
        assert voice["name"] and voice["description"]


def test_schedule_for_fixed_intervals(client: TestClient) -> None:
    response = client.post(
        "/api/schedule",
        json={
            "duration_minutes": 25,
            "prepare_seconds": 0,
            "interval_mode": "fixed",
            "interval_minutes": 5,
        },
    )
    assert response.status_code == 200
    schedule = response.json()
    assert schedule["total_seconds"] == 1500
    offsets = [event["offset_seconds"] for event in schedule["events"] if event["kind"] == "interval"]
    assert offsets == [300, 600, 900, 1200]


def test_schedule_for_random_intervals(client: TestClient) -> None:
    body = {
        "duration_minutes": 30,
        "prepare_seconds": 5,
        "interval_mode": "random",
        "interval_count": 5,
    }
    first = client.post("/api/schedule", json=body).json()
    second = client.post("/api/schedule", json=body).json()
    picks = [event["offset_seconds"] for event in first["events"] if event["kind"] == "interval"]
    assert len(picks) == 5
    assert picks == sorted(picks)
    # Random bells land strictly inside the sitting, after the lead-in and before the closing bell.
    assert all(5 < offset < first["total_seconds"] for offset in picks)
    # Each request re-scatters the bells.
    assert first["events"] != second["events"]


def test_schedule_rejects_an_unknown_voice(client: TestClient) -> None:
    response = client.post("/api/schedule", json={"start_voice": "cowbell"})
    assert response.status_code == 400


def test_schedule_rejects_an_overlong_session(client: TestClient) -> None:
    response = client.post("/api/schedule", json={"duration_minutes": 100000})
    assert response.status_code == 400


def test_presets_are_seeded_on_first_run(client: TestClient) -> None:
    presets = client.get("/api/presets").json()
    assert [preset["name"] for preset in presets] == [
        "Just sit (20 min)",
        "Bell every 5 min",
        "5 random bells",
    ]
    random_preset = presets[2]
    assert random_preset["config"]["interval_mode"] == "random"
    assert random_preset["config"]["interval_count"] == 5


def test_saving_and_deleting_a_preset(client: TestClient) -> None:
    created = client.put(
        "/api/presets",
        json={"name": "Long sit", "config": {"duration_minutes": 45, "interval_mode": "fixed"}},
    )
    assert created.status_code == 200
    preset = created.json()
    assert preset["config"]["duration_minutes"] == 45

    names = [item["name"] for item in client.get("/api/presets").json()]
    assert "Long sit" in names

    assert client.delete(f"/api/presets/{preset['id']}").status_code == 204
    assert "Long sit" not in [item["name"] for item in client.get("/api/presets").json()]


def test_saving_the_same_name_overwrites_rather_than_duplicating(client: TestClient) -> None:
    first = client.put("/api/presets", json={"name": "Evening", "config": {"duration_minutes": 10}}).json()
    second = client.put("/api/presets", json={"name": "Evening", "config": {"duration_minutes": 15}}).json()
    assert first["id"] == second["id"]
    assert second["config"]["duration_minutes"] == 15
    matching = [item for item in client.get("/api/presets").json() if item["name"] == "Evening"]
    assert len(matching) == 1


def test_blank_preset_names_are_rejected(client: TestClient) -> None:
    assert client.put("/api/presets", json={"name": "   ", "config": {}}).status_code == 400


def test_deleting_a_missing_preset_is_a_404(client: TestClient) -> None:
    assert client.delete("/api/presets/9999").status_code == 404
