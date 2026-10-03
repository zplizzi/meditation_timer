import enum
from typing import Any

import attr

from server.bells import SILENT_VOICE
from server.bells import is_valid_voice


class IntervalMode(enum.StrEnum):
    NONE = "none"
    FIXED = "fixed"
    RANDOM = "random"


def _validate_voice(instance: Any, attribute: attr.Attribute, value: str) -> None:  # type: ignore[type-arg]
    if not is_valid_voice(value):
        raise ValueError(f"'{attribute.name}' is not a known bell voice: {value!r}")


def _voice_field(default: str) -> Any:
    return attr.ib(default=default, validator=[attr.validators.instance_of(str), _validate_voice])


def _bounded(default: float, low: float, high: float) -> Any:
    return attr.ib(default=default, validator=[attr.validators.ge(low), attr.validators.le(high)])


@attr.s(auto_attribs=True, frozen=True)
class SessionConfig:
    """Everything the user chooses for one sitting. Durations are minutes; the lead-in is seconds."""

    duration_minutes: float = _bounded(20.0, 0.5, 480.0)
    prepare_seconds: float = _bounded(5.0, 0.0, 300.0)

    start_voice: str = _voice_field("singing-bowl")
    start_strikes: int = _bounded(1, 1, 5)

    interval_mode: IntervalMode = IntervalMode.NONE
    interval_minutes: float = _bounded(5.0, 0.25, 240.0)
    interval_count: int = _bounded(5, 1, 50)
    interval_voice: str = _voice_field("temple-bell")
    interval_strikes: int = _bounded(1, 1, 5)

    end_voice: str = _voice_field("singing-bowl")
    end_strikes: int = _bounded(3, 1, 5)

    @property
    def duration_seconds(self) -> float:
        return self.duration_minutes * 60.0

    @property
    def interval_seconds(self) -> float:
        return self.interval_minutes * 60.0

    def has_start_bell(self) -> bool:
        return self.start_voice != SILENT_VOICE

    def has_end_bell(self) -> bool:
        return self.end_voice != SILENT_VOICE

    def has_interval_bells(self) -> bool:
        return self.interval_mode is not IntervalMode.NONE and self.interval_voice != SILENT_VOICE
