import { BellEngine } from "./bells.js";
import { Phase, SessionPlayer } from "./player.js";

const STORAGE_KEY = "meditation-timer.prefs";
const SILENT_VOICE = "none";
const RING_RADIUS = 144;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const IDLE_DIM_MS = 6000;
const HINT_DEBOUNCE_MS = 250;

const engine = new BellEngine();
const player = new SessionPlayer(engine);

const el = (id) => document.getElementById(id);

const setupScreen = el("setup");
const sessionScreen = el("session");
const ringProgress = el("ring-progress");
const ringMarks = el("ring-marks");

/** Config field -> input id. Everything here is sent to the server as a SessionConfig. */
const NUMBER_FIELDS = {
  duration_minutes: "duration",
  prepare_seconds: "prepare",
  start_strikes: "start-strikes",
  interval_minutes: "interval-minutes",
  interval_count: "interval-count",
  interval_strikes: "interval-strikes",
  end_strikes: "end-strikes",
};
const VOICE_FIELDS = {
  start_voice: "start-voice",
  interval_voice: "interval-voice",
  end_voice: "end-voice",
};

let voices = [];
let intervalMode = "none";
let hintTimer = null;
let idleTimer = null;
let frame = null;
let lastCountdown = "";

// ---------------------------------------------------------------- form state

function readNumber(input) {
  const value = Number(input.value);
  const min = Number(input.min);
  const max = Number(input.max);
  if (!Number.isFinite(value)) {
    input.value = min;
    return min;
  }
  const clamped = Math.min(max, Math.max(min, value));
  if (clamped !== value) {
    input.value = clamped;
  }
  return clamped;
}

function readConfig() {
  const config = { interval_mode: intervalMode };
  for (const [field, id] of Object.entries(NUMBER_FIELDS)) {
    config[field] = readNumber(el(id));
  }
  for (const [field, id] of Object.entries(VOICE_FIELDS)) {
    config[field] = el(id).value;
  }
  return config;
}

function applyConfig(config) {
  for (const [field, id] of Object.entries(NUMBER_FIELDS)) {
    if (config[field] !== undefined) {
      el(id).value = config[field];
    }
  }
  for (const [field, id] of Object.entries(VOICE_FIELDS)) {
    if (config[field] !== undefined) {
      el(id).value = config[field];
    }
  }
  setMode(config.interval_mode ?? "none");
}

function setMode(mode) {
  intervalMode = mode;
  for (const button of document.querySelectorAll("#mode-picker .seg")) {
    button.setAttribute("aria-checked", String(button.dataset.mode === mode));
  }
  for (const node of document.querySelectorAll("[data-for-mode]")) {
    node.classList.toggle("hidden", !node.dataset.forMode.split(" ").includes(mode));
  }
  refreshHint();
}

// ---------------------------------------------------------------- preferences

function savePrefs() {
  const prefs = {
    config: readConfig(),
    volume: Number(el("volume").value),
    hideClock: el("hide-clock").checked,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Private browsing or a full quota: the timer still works, it just won't remember.
  }
}

function loadPrefs() {
  let prefs = null;
  try {
    prefs = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
  } catch {
    prefs = null;
  }
  if (!prefs) {
    setMode(intervalMode);
    return;
  }
  if (prefs.config) {
    applyConfig(prefs.config);
  }
  if (typeof prefs.volume === "number") {
    el("volume").value = prefs.volume;
  }
  el("hide-clock").checked = Boolean(prefs.hideClock);
}

// ---------------------------------------------------------------- server calls

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.extra?.[0]?.message ?? body.detail ?? detail;
    } catch {
      // Not a JSON error body; the status line will have to do.
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

const fetchSchedule = (config) =>
  request("/api/schedule", { method: "POST", body: JSON.stringify(config) });

function showError(message) {
  el("error").textContent = message ?? "";
}

// ---------------------------------------------------------------- hints

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function formatMinutes(minutes) {
  return Number.isInteger(minutes) ? `${minutes} min` : `${minutes.toFixed(2).replace(/0+$/, "")} min`;
}

function refreshHint() {
  clearTimeout(hintTimer);
  hintTimer = setTimeout(async () => {
    const config = readConfig();
    try {
      // The server owns the scheduling rules, so ask it rather than re-deriving the bell count here.
      const schedule = await fetchSchedule(config);
      showError(null);
      el("interval-hint").textContent = describeSchedule(config, schedule);
    } catch (error) {
      showError(error.message);
    }
  }, HINT_DEBOUNCE_MS);
}

function describeSchedule(config, schedule) {
  const count = schedule.events.filter((event) => event.kind === "interval").length;
  if (intervalMode === "none") {
    return "Only the opening and closing bells.";
  }
  if (intervalMode === "fixed") {
    if (count === 0) {
      return `No room for an interval bell in a ${formatMinutes(config.duration_minutes)} sitting.`;
    }
    return `${plural(count, "bell")} during the sitting, marked on the ring.`;
  }
  return `${plural(count, "bell")} placed afresh at random each time you begin, spaced so they never bunch together. They are not marked on the ring.`;
}

function describeVoice(selectId) {
  const voice = voices.find((candidate) => candidate.id === el(selectId).value);
  el("voice-hint").textContent = voice ? voice.description : "";
}

// ---------------------------------------------------------------- presets

async function loadPresets() {
  const presets = await request("/api/presets");
  const list = el("preset-list");
  list.replaceChildren();
  for (const preset of presets) {
    const chip = document.createElement("div");
    chip.className = "chip";

    const load = document.createElement("button");
    load.type = "button";
    load.className = "chip-load";
    load.textContent = preset.name;
    load.addEventListener("click", () => {
      applyConfig(preset.config);
      el("preset-name").value = preset.name;
      savePrefs();
      describeVoice("start-voice");
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chip-delete";
    remove.textContent = "×";
    remove.title = `Delete "${preset.name}"`;
    remove.setAttribute("aria-label", `Delete preset ${preset.name}`);
    remove.addEventListener("click", async () => {
      await request(`/api/presets/${preset.id}`, { method: "DELETE" });
      await loadPresets();
    });

    chip.append(load, remove);
    list.append(chip);
  }
}

// ---------------------------------------------------------------- session view

function formatClock(seconds) {
  const total = Math.max(0, Math.ceil(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (value) => String(value).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`;
}

function drawMarks(schedule, mode) {
  ringMarks.replaceChildren();
  // Random bells are deliberately left off the ring: seeing them coming is the thing you are avoiding.
  if (mode !== "fixed" || schedule.duration_seconds <= 0) {
    return;
  }
  for (const event of schedule.events) {
    if (event.kind !== "interval") {
      continue;
    }
    const fraction = (event.offset_seconds - schedule.prepare_seconds) / schedule.duration_seconds;
    const angle = fraction * 2 * Math.PI;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "ring-mark");
    line.setAttribute("x1", 160 + 137 * Math.cos(angle));
    line.setAttribute("y1", 160 + 137 * Math.sin(angle));
    line.setAttribute("x2", 160 + 151 * Math.cos(angle));
    line.setAttribute("y2", 160 + 151 * Math.sin(angle));
    ringMarks.append(line);
  }
}

function detailText(config) {
  if (player.paused) {
    return "";
  }
  if (intervalMode === "fixed") {
    return `a bell every ${formatMinutes(config.interval_minutes)}`;
  }
  if (intervalMode === "random") {
    const left = player.upcomingEvents().filter((event) => event.kind === "interval").length;
    return left === 0 ? "" : `${plural(left, "bell")} still to come`;
  }
  return "";
}

const PHASE_LABELS = {
  [Phase.PREPARING]: "settling in",
  [Phase.SITTING]: "",
  [Phase.RINGING_OUT]: "ringing out",
  [Phase.DONE]: "complete",
};

function render(config) {
  const phase = player.phase;
  el("phase-label").textContent = player.paused ? "paused" : PHASE_LABELS[phase] ?? "";

  const clock = formatClock(player.remaining);
  if (clock !== lastCountdown) {
    el("countdown").textContent = clock;
    lastCountdown = clock;
  }

  ringProgress.setAttribute("stroke-dashoffset", RING_CIRCUMFERENCE * (1 - player.progress));
  el("session-detail").textContent = detailText(config);

  if (phase === Phase.DONE) {
    el("pause").classList.add("hidden");
    el("finish").textContent = "Done";
    sessionScreen.classList.remove("dimmed");
    return false;
  }
  return true;
}

function startRenderLoop(config) {
  const step = () => {
    frame = render(config) ? requestAnimationFrame(step) : null;
  };
  cancelAnimationFrame(frame);
  step();
}

function stopRenderLoop() {
  if (frame !== null) {
    cancelAnimationFrame(frame);
    frame = null;
  }
}

function markActivity() {
  sessionScreen.classList.remove("dimmed");
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (player.running && !player.paused && player.phase !== Phase.DONE) {
      sessionScreen.classList.add("dimmed");
    }
  }, IDLE_DIM_MS);
}

async function begin() {
  showError(null);
  const config = readConfig();
  savePrefs();
  let schedule;
  try {
    await engine.unlock();
    schedule = await fetchSchedule(config);
  } catch (error) {
    showError(error.message);
    return;
  }

  ringProgress.setAttribute("stroke-dasharray", RING_CIRCUMFERENCE);
  ringProgress.setAttribute("stroke-dashoffset", RING_CIRCUMFERENCE);
  drawMarks(schedule, intervalMode);

  sessionScreen.classList.toggle("hide-clock", el("hide-clock").checked);
  sessionScreen.classList.remove("dimmed");
  el("pause").classList.remove("hidden");
  el("pause").textContent = "Pause";
  el("finish").textContent = "End";
  setupScreen.classList.add("hidden");
  sessionScreen.classList.remove("hidden");

  lastCountdown = "";
  player.start(schedule);
  startRenderLoop(config);
  markActivity();
}

function endSession() {
  player.stop();
  stopRenderLoop();
  clearTimeout(idleTimer);
  sessionScreen.classList.add("hidden");
  setupScreen.classList.remove("hidden");
}

// ---------------------------------------------------------------- wiring

function wireUp() {
  for (const button of document.querySelectorAll("#mode-picker .seg")) {
    button.addEventListener("click", () => {
      setMode(button.dataset.mode);
      savePrefs();
    });
  }

  for (const input of document.querySelectorAll("#setup input[type='number']")) {
    input.addEventListener("change", () => {
      savePrefs();
      refreshHint();
    });
  }

  for (const select of document.querySelectorAll("#setup select[data-voice]")) {
    select.addEventListener("change", () => {
      describeVoice(select.id);
      savePrefs();
      refreshHint();
    });
  }

  for (const button of document.querySelectorAll(".try")) {
    button.addEventListener("click", async () => {
      const select = el(button.dataset.try);
      if (select.value === SILENT_VOICE) {
        return;
      }
      await engine.unlock();
      engine.fadeIn(0);
      engine.strike(select.value, engine.now + 0.02);
    });
  }

  el("volume").addEventListener("input", () => {
    engine.setVolume(Number(el("volume").value));
    savePrefs();
  });

  el("hide-clock").addEventListener("change", () => {
    sessionScreen.classList.toggle("hide-clock", el("hide-clock").checked);
    savePrefs();
  });

  el("preset-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = el("preset-name").value.trim();
    if (!name) {
      return;
    }
    try {
      await request("/api/presets", {
        method: "PUT",
        body: JSON.stringify({ name, config: readConfig() }),
      });
      await loadPresets();
      showError(null);
    } catch (error) {
      showError(error.message);
    }
  });

  el("begin").addEventListener("click", begin);

  el("pause").addEventListener("click", () => {
    if (player.paused) {
      player.resume();
      el("pause").textContent = "Pause";
    } else {
      player.pause();
      el("pause").textContent = "Resume";
    }
    markActivity();
  });

  el("finish").addEventListener("click", endSession);

  for (const event of ["pointermove", "pointerdown", "touchstart", "keydown"]) {
    sessionScreen.addEventListener(event, markActivity, { passive: true });
  }

  // Coming back to a backgrounded tab: the context may have been suspended, and rAF has stopped.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") {
      return;
    }
    if (engine.ctx && engine.ctx.state === "suspended" && player.running && !player.paused) {
      engine.ctx.resume();
    }
    if (player.running && frame === null && player.phase !== Phase.DONE) {
      startRenderLoop(readConfig());
    }
  });
}

function populateVoices() {
  for (const id of Object.values(VOICE_FIELDS)) {
    const select = el(id);
    const silent = document.createElement("option");
    silent.value = SILENT_VOICE;
    silent.textContent = "— silent —";
    select.append(silent);
    for (const voice of voices) {
      const option = document.createElement("option");
      option.value = voice.id;
      option.textContent = voice.name;
      select.append(option);
    }
  }
  el("start-voice").value = "singing-bowl";
  el("interval-voice").value = "temple-bell";
  el("end-voice").value = "singing-bowl";
}

async function main() {
  wireUp();
  try {
    voices = await request("/api/bells");
  } catch (error) {
    showError(`Could not load the bell sounds: ${error.message}`);
    return;
  }
  populateVoices();
  loadPrefs();
  engine.setVoices(voices);
  engine.setVolume(Number(el("volume").value));
  describeVoice("start-voice");
  try {
    await loadPresets();
  } catch (error) {
    showError(`Could not load presets: ${error.message}`);
  }
}

main();
