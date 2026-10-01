import enum
import random

import attr

from server.bells import VOICES_BY_ID
from server.session import IntervalMode
from server.session import SessionConfig

# Random bells are kept at least this far apart, and this far from each end of the session, so that a random
# scatter never bunches two bells together. Short sessions scale the gap down rather than giving up on it.
PREFERRED_RANDOM_GAP_SECONDS = 60.0
RANDOM_GAP_FRACTION = 0.5

# An interval bell this close to the end would collide with the closing bell, so it is dropped.
END_CLEARANCE_SECONDS = 1.0

# Repeated strikes are spaced relative to how long the voice rings, so a gong gets more room than a chime.
STRIKE_GAP_FRACTION = 0.45
MIN_STRIKE_GAP_SECONDS = 1.2
MAX_STRIKE_GAP_SECONDS = 4.0


class BellKind(enum.StrEnum):
    START = "start"
    INTERVAL = "interval"
    END = "end"


@attr.s(auto_attribs=True, frozen=True)
class BellEvent:
    """One bell, at `offset_seconds` after the timer starts (the lead-in is already included)."""

    offset_seconds: float
    voice: str
    strikes: int
    strike_gap_seconds: float
    kind: BellKind

    @property
    def last_strike_offset(self) -> float:
        return self.offset_seconds + (self.strikes - 1) * self.strike_gap_seconds


@attr.s(auto_attribs=True, frozen=True)
class Schedule:
    """A whole sitting, laid out on one timeline so the browser only has to play it back.

    `total_seconds` is where the timer hits zero; `audio_end_seconds` is when the last bell has finished ringing,
    which is later whenever the closing bell has a long tail.
    """

    prepare_seconds: float
    duration_seconds: float
    total_seconds: float
    audio_end_seconds: float
    events: tuple[BellEvent, ...]


def _strike_gap(voice_id: str) -> float:
    longest_decay = max(partial.decay for partial in VOICES_BY_ID[voice_id].partials)
    return min(MAX_STRIKE_GAP_SECONDS, max(MIN_STRIKE_GAP_SECONDS, longest_decay * STRIKE_GAP_FRACTION))


def _voice_tail(voice_id: str) -> float:
    return max(partial.decay for partial in VOICES_BY_ID[voice_id].partials)


def fixed_interval_offsets(duration_seconds: float, interval_seconds: float) -> tuple[float, ...]:
    """Offsets of evenly spaced bells strictly inside the session, excluding one that would land on the end."""
    offsets = []
    offset = interval_seconds
    while offset < duration_seconds - END_CLEARANCE_SECONDS:
        offsets.append(offset)
        offset += interval_seconds
    return tuple(offsets)


def random_interval_offsets(duration_seconds: float, count: int, rng: random.Random) -> tuple[float, ...]:
    """`count` offsets scattered through the session, uniformly at random subject to a minimum gap.

    Drawing `count` points in the interval shrunk by the gaps and then pushing each one out by the gaps it sits
    behind gives a uniform sample over exactly the arrangements that respect the spacing — no rejection loop.
    """
    gap = min(PREFERRED_RANDOM_GAP_SECONDS, duration_seconds / (count + 1) * RANDOM_GAP_FRACTION)
    usable = duration_seconds - gap * (count + 1)
    assert usable > 0, f"gap {gap} leaves no room in {duration_seconds}s for {count} bells"
    draws = sorted(rng.random() * usable for _ in range(count))
    return tuple(draw + gap * (index + 1) for index, draw in enumerate(draws))


def _interval_offsets(config: SessionConfig, rng: random.Random) -> tuple[float, ...]:
    if config.interval_mode is IntervalMode.FIXED:
        return fixed_interval_offsets(config.duration_seconds, config.interval_seconds)
    if config.interval_mode is IntervalMode.RANDOM:
        return random_interval_offsets(config.duration_seconds, config.interval_count, rng)
    raise AssertionError(f"no interval offsets for mode {config.interval_mode}")


def build_schedule(config: SessionConfig, rng: random.Random) -> Schedule:
    events: list[BellEvent] = []

    def add(offset: float, voice: str, strikes: int, kind: BellKind) -> None:
        events.append(
            BellEvent(
                offset_seconds=offset,
                voice=voice,
                strikes=strikes,
                strike_gap_seconds=_strike_gap(voice),
                kind=kind,
            )
        )

    if config.has_start_bell():
        add(config.prepare_seconds, config.start_voice, config.start_strikes, BellKind.START)

    if config.has_interval_bells():
        for offset in _interval_offsets(config, rng):
            add(config.prepare_seconds + offset, config.interval_voice, config.interval_strikes, BellKind.INTERVAL)

    total_seconds = config.prepare_seconds + config.duration_seconds
    if config.has_end_bell():
        add(total_seconds, config.end_voice, config.end_strikes, BellKind.END)

    events.sort(key=lambda event: event.offset_seconds)
    audio_end = max(
        (event.last_strike_offset + _voice_tail(event.voice) for event in events),
        default=total_seconds,
    )
    return Schedule(
        prepare_seconds=config.prepare_seconds,
        duration_seconds=config.duration_seconds,
        total_seconds=total_seconds,
        audio_end_seconds=max(total_seconds, audio_end),
        events=tuple(events),
    )
