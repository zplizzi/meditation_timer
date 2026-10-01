import attr


@attr.s(auto_attribs=True, frozen=True)
class Partial:
    """One mode of a struck resonator: a sine at `ratio` x the fundamental, decaying over `decay` seconds."""

    ratio: float
    gain: float
    decay: float


@attr.s(auto_attribs=True, frozen=True)
class BellVoice:
    """An additive-synthesis recipe for a bell. The browser renders this with the Web Audio API.

    Real bells are inharmonic — their partials are not integer multiples of the fundamental — which is what makes
    them sound like metal rather than an organ. Each voice below uses measured-ish mode ratios for the instrument
    it imitates, plus a short filtered-noise `strike` transient for the sound of the mallet itself.
    """

    id: str
    name: str
    description: str
    fundamental: float
    partials: tuple[Partial, ...]
    attack: float
    strike_gain: float
    strike_decay: float
    strike_frequency: float
    beat_hz: float
    lowpass: float
    gain: float


SILENT_VOICE = "none"

BELL_VOICES: tuple[BellVoice, ...] = (
    BellVoice(
        id="singing-bowl",
        name="Singing bowl",
        description="Deep Tibetan bowl with a long, slowly beating tail.",
        fundamental=196.0,
        partials=(
            Partial(ratio=1.0, gain=1.0, decay=15.0),
            Partial(ratio=2.46, gain=0.55, decay=10.0),
            Partial(ratio=4.52, gain=0.26, decay=6.5),
            Partial(ratio=7.14, gain=0.11, decay=4.0),
            Partial(ratio=10.3, gain=0.05, decay=2.2),
        ),
        attack=0.012,
        strike_gain=0.16,
        strike_decay=0.07,
        strike_frequency=2400.0,
        beat_hz=0.45,
        lowpass=5000.0,
        gain=0.9,
    ),
    BellVoice(
        id="temple-bell",
        name="Temple bell",
        description="Cast bell with the classic hum, prime and minor-third tierce.",
        fundamental=330.0,
        partials=(
            Partial(ratio=0.5, gain=0.7, decay=11.0),
            Partial(ratio=1.0, gain=1.0, decay=7.5),
            Partial(ratio=1.19, gain=0.5, decay=5.5),
            Partial(ratio=1.5, gain=0.34, decay=4.0),
            Partial(ratio=2.0, gain=0.3, decay=3.0),
            Partial(ratio=2.5, gain=0.16, decay=1.8),
            Partial(ratio=3.01, gain=0.12, decay=1.3),
            Partial(ratio=4.14, gain=0.07, decay=0.8),
        ),
        attack=0.005,
        strike_gain=0.3,
        strike_decay=0.05,
        strike_frequency=3600.0,
        beat_hz=0.8,
        lowpass=7000.0,
        gain=1.15,
    ),
    BellVoice(
        id="deep-gong",
        name="Deep gong",
        description="Low gong that blooms in and hangs for a long time.",
        fundamental=82.0,
        partials=(
            Partial(ratio=1.0, gain=1.0, decay=18.0),
            Partial(ratio=1.42, gain=0.62, decay=14.0),
            Partial(ratio=1.98, gain=0.5, decay=11.0),
            Partial(ratio=2.51, gain=0.36, decay=8.0),
            Partial(ratio=3.11, gain=0.26, decay=6.0),
            Partial(ratio=4.07, gain=0.17, decay=4.5),
            Partial(ratio=5.23, gain=0.1, decay=3.0),
            Partial(ratio=6.91, gain=0.06, decay=2.0),
        ),
        attack=0.045,
        strike_gain=0.12,
        strike_decay=0.12,
        strike_frequency=1200.0,
        beat_hz=0.3,
        lowpass=2600.0,
        gain=1.0,
    ),
    BellVoice(
        id="crystal-bowl",
        name="Crystal bowl",
        description="Pure, high and shimmering — very little attack.",
        fundamental=528.0,
        partials=(
            Partial(ratio=1.0, gain=1.0, decay=13.0),
            Partial(ratio=2.39, gain=0.3, decay=8.0),
            Partial(ratio=4.31, gain=0.12, decay=4.5),
            Partial(ratio=6.8, gain=0.05, decay=2.5),
        ),
        attack=0.025,
        strike_gain=0.06,
        strike_decay=0.05,
        strike_frequency=4200.0,
        beat_hz=1.3,
        lowpass=8000.0,
        gain=0.9,
    ),
    BellVoice(
        id="chime",
        name="Chime",
        description="Small bright chime, gone in a few seconds.",
        fundamental=880.0,
        partials=(
            Partial(ratio=1.0, gain=1.0, decay=4.5),
            Partial(ratio=2.76, gain=0.4, decay=2.6),
            Partial(ratio=5.4, gain=0.16, decay=1.5),
            Partial(ratio=8.93, gain=0.06, decay=0.8),
        ),
        attack=0.003,
        strike_gain=0.28,
        strike_decay=0.03,
        strike_frequency=5200.0,
        beat_hz=0.6,
        lowpass=11000.0,
        gain=1.0,
    ),
    BellVoice(
        id="wood-block",
        name="Wood block",
        description="Dry click, for interval markers that stay out of the way.",
        fundamental=1100.0,
        partials=(
            Partial(ratio=1.0, gain=1.0, decay=0.14),
            Partial(ratio=1.58, gain=0.5, decay=0.09),
            Partial(ratio=2.33, gain=0.22, decay=0.055),
        ),
        attack=0.001,
        strike_gain=0.5,
        strike_decay=0.02,
        strike_frequency=2000.0,
        beat_hz=0.0,
        lowpass=7000.0,
        gain=1.1,
    ),
)

VOICES_BY_ID: dict[str, BellVoice] = {voice.id: voice for voice in BELL_VOICES}


def is_valid_voice(voice_id: str) -> bool:
    return voice_id == SILENT_VOICE or voice_id in VOICES_BY_ID
