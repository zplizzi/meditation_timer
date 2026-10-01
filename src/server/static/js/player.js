// Plays back a schedule from the server. Every bell is scheduled on the audio clock up front rather than fired
// from a JS timer, so the bells stay accurate (and keep sounding) even if the tab is backgrounded or the screen
// goes to sleep part way through a sitting.

const SCHEDULE_LEAD = 0.02;
const PAUSE_FADE = 0.12;

export const Phase = {
  IDLE: "idle",
  PREPARING: "preparing",
  SITTING: "sitting",
  RINGING_OUT: "ringing-out",
  DONE: "done",
};

export class SessionPlayer {
  constructor(engine) {
    this.engine = engine;
    this.schedule = null;
    this.paused = false;
    this.sources = [];
    this.keepAlive = null;
    // Elapsed seconds banked before the current run (ie everything before the last pause).
    this.banked = 0;
    this.runStartedAt = null;
  }

  get running() {
    return this.schedule !== null;
  }

  get elapsed() {
    if (!this.schedule) {
      return 0;
    }
    if (this.paused || this.runStartedAt === null) {
      return this.banked;
    }
    return this.banked + (this.engine.now - this.runStartedAt);
  }

  get phase() {
    if (!this.schedule) {
      return Phase.IDLE;
    }
    const elapsed = this.elapsed;
    if (elapsed < this.schedule.prepare_seconds) {
      return Phase.PREPARING;
    }
    if (elapsed < this.schedule.total_seconds) {
      return Phase.SITTING;
    }
    if (elapsed < this.schedule.audio_end_seconds) {
      return Phase.RINGING_OUT;
    }
    return Phase.DONE;
  }

  /** Seconds left in the current phase: the lead-in while settling, otherwise the sitting itself. */
  get remaining() {
    if (!this.schedule) {
      return 0;
    }
    const elapsed = this.elapsed;
    if (elapsed < this.schedule.prepare_seconds) {
      return this.schedule.prepare_seconds - elapsed;
    }
    return Math.max(0, this.schedule.total_seconds - elapsed);
  }

  /** How far through the sitting proper, 0 to 1, ignoring the lead-in. */
  get progress() {
    if (!this.schedule || this.schedule.duration_seconds <= 0) {
      return 0;
    }
    const sat = this.elapsed - this.schedule.prepare_seconds;
    return Math.min(1, Math.max(0, sat / this.schedule.duration_seconds));
  }

  start(schedule) {
    this.schedule = schedule;
    this.banked = 0;
    this.paused = false;
    this.engine.fadeIn(0);
    this.#scheduleRemaining();
    this.#startKeepAlive();
  }

  pause() {
    if (!this.schedule || this.paused) {
      return;
    }
    this.banked = this.elapsed;
    this.paused = true;
    this.runStartedAt = null;
    this.engine.fadeOut(PAUSE_FADE);
    this.#cancelSources(PAUSE_FADE + 0.03);
  }

  resume() {
    if (!this.schedule || !this.paused) {
      return;
    }
    this.paused = false;
    this.engine.fadeIn(0.05);
    this.#scheduleRemaining();
  }

  stop() {
    this.engine.fadeOut(PAUSE_FADE);
    this.#cancelSources(PAUSE_FADE + 0.03);
    this.#stopKeepAlive();
    this.schedule = null;
    this.paused = false;
    this.banked = 0;
    this.runStartedAt = null;
  }

  /** Bells that have not sounded yet, for the "next bell" readout. */
  upcomingEvents() {
    if (!this.schedule) {
      return [];
    }
    const elapsed = this.elapsed;
    return this.schedule.events.filter((event) => event.offset_seconds > elapsed);
  }

  #scheduleRemaining() {
    const elapsed = this.banked;
    this.runStartedAt = this.engine.now;
    this.sources = [];
    for (const event of this.schedule.events) {
      if (event.offset_seconds < elapsed) {
        continue;
      }
      const at = Math.max(this.runStartedAt + (event.offset_seconds - elapsed), this.engine.now + SCHEDULE_LEAD);
      this.sources.push(...this.engine.ring(event, at));
    }
  }

  #cancelSources(delay) {
    const stopAt = this.engine.now + delay;
    for (const source of this.sources) {
      try {
        source.stop(stopAt);
      } catch {
        // Already stopped; nothing to cancel.
      }
    }
    this.sources = [];
  }

  // A looping silent source keeps the audio graph busy, which discourages mobile browsers from suspending the
  // context while the screen is off. It is not a guarantee — see the README.
  #startKeepAlive() {
    this.#stopKeepAlive();
    this.keepAlive = this.engine.startSilence();
  }

  #stopKeepAlive() {
    if (this.keepAlive) {
      try {
        this.keepAlive.stop();
      } catch {
        // Already stopped.
      }
      this.keepAlive = null;
    }
  }
}
