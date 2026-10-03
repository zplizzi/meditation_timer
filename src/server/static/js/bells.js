// Additive synthesis of the bell voices the server describes in bells.py. Each strike builds a small graph of
// sine oscillators (one per partial, doubled and detuned to get the slow beating real bowls have) plus a short
// burst of band-passed noise for the mallet, all under a per-strike lowpass.

const NEAR_SILENCE = 0.0001;
const STRIKE_TAIL = 0.05;

export class BellEngine {
  /** `context` is only passed by tests, which render the voices through an OfflineAudioContext. */
  constructor(context = null) {
    this.providedContext = context;
    this.ctx = null;
    this.master = null;
    this.fader = null;
    this.noiseBuffer = null;
    this.voices = new Map();
    this.volume = 0.7;
  }

  setVoices(voices) {
    this.voices.clear();
    for (const voice of voices) {
      this.voices.set(voice.id, voice);
    }
  }

  /** Build the audio graph without starting it. */
  prepare() {
    if (!this.ctx) {
      this.#build();
    }
    return this.ctx;
  }

  // Browsers only allow an audio context to start from a user gesture, so this is called from click handlers.
  async unlock() {
    this.prepare();
    if (this.ctx.state !== "running") {
      await this.ctx.resume();
    }
    return this.ctx;
  }

  get now() {
    return this.ctx ? this.ctx.currentTime : 0;
  }

  setVolume(volume) {
    this.volume = volume;
    if (this.master) {
      this.master.gain.setTargetAtTime(this.#masterGain(), this.now, 0.02);
    }
  }

  // Loudness tracks the slider roughly perceptually rather than linearly.
  #masterGain() {
    return this.volume * this.volume;
  }

  #build() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = this.providedContext ?? new AudioCtx();

    // Overlapping bells can sum past full scale. This sits high and hard enough to act as a safety limiter
    // only — a single bell never reaches it, so strikes keep their attack.
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -2;
    limiter.knee.value = 2;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.002;
    limiter.release.value = 0.2;

    // `master` carries the user's volume; `fader` is separate so pausing can duck the output without
    // disturbing (or being disturbed by) the volume slider.
    const fader = ctx.createGain();
    fader.gain.value = 1;
    fader.connect(limiter).connect(ctx.destination);

    const master = ctx.createGain();
    master.gain.value = this.#masterGain();
    master.connect(fader);

    const frames = Math.floor(ctx.sampleRate * 2);
    const noiseBuffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = noiseBuffer.getChannelData(0);
    for (let i = 0; i < frames; i++) {
      data[i] = Math.random() * 2 - 1;
    }

    this.ctx = ctx;
    this.master = master;
    this.fader = fader;
    this.noiseBuffer = noiseBuffer;
  }

  /** Schedule one strike of `voiceId` at audio-clock time `when`. Returns the source nodes, so a pause can
   * cancel strikes that have not sounded yet. */
  strike(voiceId, when) {
    const voice = this.voices.get(voiceId);
    if (!voice || !this.ctx) {
      return [];
    }
    const ctx = this.ctx;
    const sources = [];

    const lowpass = ctx.createBiquadFilter();
    lowpass.type = "lowpass";
    lowpass.frequency.value = voice.lowpass;
    lowpass.Q.value = 0.5;

    const bus = ctx.createGain();
    // Normalising by the summed partial gains keeps voices with many modes from being louder than sparse ones.
    const total = voice.partials.reduce((sum, partial) => sum + partial.gain, 0);
    bus.gain.value = voice.gain / total;
    bus.connect(lowpass).connect(this.master);

    const detunes = voice.beat_hz > 0 ? [-voice.beat_hz / 2, voice.beat_hz / 2] : [0];
    for (const partial of voice.partials) {
      const peak = partial.gain / detunes.length;
      const end = when + voice.attack + partial.decay;
      for (const detune of detunes) {
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = voice.fundamental * partial.ratio + detune;

        const envelope = ctx.createGain();
        envelope.gain.setValueAtTime(0, when);
        envelope.gain.linearRampToValueAtTime(peak, when + voice.attack);
        envelope.gain.exponentialRampToValueAtTime(NEAR_SILENCE, end);

        osc.connect(envelope).connect(bus);
        osc.start(when);
        osc.stop(end + STRIKE_TAIL);
        sources.push(osc);
      }
    }

    if (voice.strike_gain > 0) {
      const noise = ctx.createBufferSource();
      noise.buffer = this.noiseBuffer;

      const band = ctx.createBiquadFilter();
      band.type = "bandpass";
      band.frequency.value = voice.strike_frequency;
      band.Q.value = 1.2;

      const envelope = ctx.createGain();
      envelope.gain.setValueAtTime(voice.strike_gain, when);
      envelope.gain.exponentialRampToValueAtTime(NEAR_SILENCE, when + voice.strike_decay);

      noise.connect(band).connect(envelope).connect(bus);
      noise.start(when, Math.random());
      noise.stop(when + voice.strike_decay + STRIKE_TAIL);
      sources.push(noise);
    }

    return sources;
  }

  /** Schedule a bell event: `strikes` strikes of one voice, spaced by `strike_gap_seconds`. */
  ring(event, when) {
    const sources = [];
    for (let index = 0; index < event.strikes; index++) {
      sources.push(...this.strike(event.voice, when + index * event.strike_gap_seconds));
    }
    return sources;
  }

  fadeOut(seconds) {
    this.#rampFader(0, seconds);
  }

  fadeIn(seconds) {
    this.#rampFader(1, seconds);
  }

  #rampFader(target, seconds) {
    if (!this.fader) {
      return;
    }
    const now = this.now;
    this.fader.gain.cancelScheduledValues(now);
    this.fader.gain.setValueAtTime(this.fader.gain.value, now);
    if (seconds > 0) {
      this.fader.gain.linearRampToValueAtTime(target, now + seconds);
    } else {
      this.fader.gain.setValueAtTime(target, now);
    }
  }

  /** A looping silent source, to keep the context from being suspended mid-sitting. */
  startSilence() {
    if (!this.ctx) {
      return null;
    }
    const buffer = this.ctx.createBuffer(1, this.ctx.sampleRate, this.ctx.sampleRate);
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(this.master);
    source.start();
    return source;
  }

  tailOf(voiceId) {
    const voice = this.voices.get(voiceId);
    return voice ? Math.max(...voice.partials.map((partial) => partial.decay)) : 0;
  }
}
