import random

import pytest

from server.bells import SILENT_VOICE
from server.schedule import PREFERRED_RANDOM_GAP_SECONDS
from server.schedule import BellKind
from server.schedule import Schedule
from server.schedule import build_schedule
from server.schedule import fixed_interval_offsets
from server.schedule import random_interval_offsets
from server.session import IntervalMode
from server.session import SessionConfig


def kinds(schedule: Schedule) -> list[BellKind]:
    return [event.kind for event in schedule.events]


def test_plain_session_has_only_opening_and_closing_bells() -> None:
    schedule = build_schedule(SessionConfig(duration_minutes=20.0, prepare_seconds=5.0), random.Random(0))
    assert kinds(schedule) == [BellKind.START, BellKind.END]
    assert schedule.events[0].offset_seconds == 5.0
    assert schedule.events[1].offset_seconds == 1205.0
    assert schedule.total_seconds == 1205.0


def test_silent_voices_drop_their_bells() -> None:
    config = SessionConfig(start_voice=SILENT_VOICE, end_voice=SILENT_VOICE)
    schedule = build_schedule(config, random.Random(0))
    assert schedule.events == ()
    assert schedule.audio_end_seconds == schedule.total_seconds


def test_audio_end_covers_the_tail_of_the_closing_bell() -> None:
    config = SessionConfig(duration_minutes=10.0, prepare_seconds=0.0, end_voice="singing-bowl", end_strikes=3)
    schedule = build_schedule(config, random.Random(0))
    end = schedule.events[-1]
    # Three strikes, then the last one still has to ring out.
    assert schedule.audio_end_seconds > end.offset_seconds + 2 * end.strike_gap_seconds
    assert schedule.audio_end_seconds > schedule.total_seconds


def test_fixed_offsets_are_evenly_spaced_inside_the_session() -> None:
    assert fixed_interval_offsets(1500.0, 300.0) == (300.0, 600.0, 900.0, 1200.0)


def test_fixed_offsets_skip_a_bell_landing_on_the_closing_bell() -> None:
    # A 20 minute sitting with a bell every 5 minutes gets bells at 5, 10 and 15 — not a fourth at 20.
    assert fixed_interval_offsets(1200.0, 300.0) == (300.0, 600.0, 900.0)


def test_fixed_offsets_empty_when_the_interval_exceeds_the_session() -> None:
    assert fixed_interval_offsets(600.0, 900.0) == ()


def test_fixed_bells_are_marked_as_interval_bells() -> None:
    config = SessionConfig(
        duration_minutes=25.0,
        prepare_seconds=0.0,
        interval_mode=IntervalMode.FIXED,
        interval_minutes=5.0,
    )
    schedule = build_schedule(config, random.Random(0))
    assert kinds(schedule) == [BellKind.START] + [BellKind.INTERVAL] * 4 + [BellKind.END]


@pytest.mark.parametrize("seed", range(25))
def test_random_offsets_respect_count_bounds_and_spacing(seed: int) -> None:
    duration = 1800.0
    count = 5
    offsets = random_interval_offsets(duration, count, random.Random(seed))
    assert len(offsets) == count
    assert list(offsets) == sorted(offsets)
    gap = PREFERRED_RANDOM_GAP_SECONDS
    assert offsets[0] >= gap
    assert offsets[-1] <= duration - gap
    for earlier, later in zip(offsets, offsets[1:], strict=False):
        assert later - earlier >= gap


@pytest.mark.parametrize(
    ("duration", "count"),
    [(30.0, 5), (60.0, 1), (120.0, 10), (300.0, 50), (28800.0, 50)],
)
def test_random_offsets_stay_inside_short_and_crowded_sessions(duration: float, count: int) -> None:
    offsets = random_interval_offsets(duration, count, random.Random(1))
    assert len(offsets) == count
    assert all(0 < offset < duration for offset in offsets)
    # The gap shrinks with the session, but bells never land on top of each other.
    for earlier, later in zip(offsets, offsets[1:], strict=False):
        assert later > earlier


def test_random_offsets_differ_between_sittings() -> None:
    first = random_interval_offsets(1800.0, 5, random.Random(1))
    second = random_interval_offsets(1800.0, 5, random.Random(2))
    assert first != second


def test_random_offsets_are_reproducible_for_a_given_seed() -> None:
    assert random_interval_offsets(1800.0, 5, random.Random(7)) == random_interval_offsets(1800.0, 5, random.Random(7))


def test_random_bells_sit_inside_the_session_after_the_lead_in() -> None:
    config = SessionConfig(
        duration_minutes=30.0,
        prepare_seconds=10.0,
        interval_mode=IntervalMode.RANDOM,
        interval_count=5,
    )
    schedule = build_schedule(config, random.Random(3))
    interval_bells = [event for event in schedule.events if event.kind is BellKind.INTERVAL]
    assert len(interval_bells) == 5
    assert all(10.0 < event.offset_seconds < schedule.total_seconds for event in interval_bells)
    assert kinds(schedule) == [BellKind.START] + [BellKind.INTERVAL] * 5 + [BellKind.END]


def test_strike_gap_is_longer_for_voices_that_ring_longer() -> None:
    gong = build_schedule(SessionConfig(end_voice="deep-gong", end_strikes=3), random.Random(0)).events[-1]
    chime = build_schedule(SessionConfig(end_voice="chime", end_strikes=3), random.Random(0)).events[-1]
    assert gong.strike_gap_seconds > chime.strike_gap_seconds


def test_out_of_range_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        SessionConfig(duration_minutes=9999.0)
    with pytest.raises(ValueError):
        SessionConfig(interval_count=0)
    with pytest.raises(ValueError):
        SessionConfig(start_voice="cowbell")
