from typing import Any

import attr
import msgspec
from loguru import logger

from server.db import connect
from server.session import IntervalMode
from server.session import SessionConfig


@attr.s(auto_attribs=True, frozen=True)
class Preset:
    id: int
    name: str
    config: SessionConfig


MAX_PRESET_NAME_LENGTH = 80


def _validate_name(instance: Any, attribute: "attr.Attribute[str]", value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{attribute.name}' must not be blank")
    if len(value) > MAX_PRESET_NAME_LENGTH:
        raise ValueError(f"'{attribute.name}' must be at most {MAX_PRESET_NAME_LENGTH} characters")


@attr.s(auto_attribs=True, frozen=True)
class PresetInput:
    name: str = attr.ib(validator=_validate_name)
    config: SessionConfig = attr.ib(factory=SessionConfig)


# Shown the first time the app runs, so there is something to click.
DEFAULT_PRESETS: tuple[PresetInput, ...] = (
    PresetInput(name="Just sit (20 min)", config=SessionConfig(duration_minutes=20.0)),
    PresetInput(
        name="Bell every 5 min",
        config=SessionConfig(duration_minutes=25.0, interval_mode=IntervalMode.FIXED, interval_minutes=5.0),
    ),
    PresetInput(
        name="5 random bells",
        config=SessionConfig(duration_minutes=30.0, interval_mode=IntervalMode.RANDOM, interval_count=5),
    ),
)


def _row_to_preset(row: Any) -> Preset:
    return Preset(
        id=row["id"],
        name=row["name"],
        config=msgspec.json.decode(row["config_json"], type=SessionConfig),
    )


def list_presets() -> tuple[Preset, ...]:
    with connect() as connection:
        rows = connection.execute("SELECT id, name, config_json FROM presets ORDER BY id").fetchall()
    return tuple(_row_to_preset(row) for row in rows)


def save_preset(preset: PresetInput) -> Preset:
    """Insert the preset, or overwrite the config of the existing preset with the same name."""
    config_json = msgspec.json.encode(preset.config).decode()
    with connect() as connection:
        row = connection.execute(
            "INSERT INTO presets (name, config_json) VALUES (?, ?)"
            " ON CONFLICT(name) DO UPDATE SET config_json = excluded.config_json"
            " RETURNING id, name, config_json",
            (preset.name.strip(), config_json),
        ).fetchone()
    return _row_to_preset(row)


def delete_preset(preset_id: int) -> bool:
    with connect() as connection:
        cursor = connection.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    return cursor.rowcount > 0


def seed_default_presets() -> None:
    with connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM presets").fetchone()["count"]
    if count > 0:
        return
    for preset in DEFAULT_PRESETS:
        save_preset(preset)
    logger.info("seeded {} default presets", len(DEFAULT_PRESETS))
