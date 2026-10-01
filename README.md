# meditation timer

A personal meditation timer that runs as an OpenHost app. Set a duration, pick bells, sit.
Bells can be placed at a fixed interval ("one every 5 minutes") or scattered at random
through the sitting ("5 bells, somewhere in the next half hour").

It is login-gated by the OpenHost router — `openhost.toml` declares no `public_paths`, so
only the zone owner can reach it.

## what it does

- **Timer** with an optional lead-in, so you can put the phone down and settle before the
  opening bell.
- **Interval bells** in three modes: none, one every *n* minutes, or *n* bells placed at
  random. Random bells are re-scattered every time you begin, kept at least a minute apart
  (less in a short sitting), and deliberately not drawn on the ring — knowing when they are
  coming rather defeats the point.
- **Six bell voices**, synthesized in the browser: singing bowl, temple bell, deep gong,
  crystal bowl, chime, and a dry wood block for interval marks that stay out of the way.
  Opening, interval and closing bells are chosen separately, each with 1–5 strikes (three
  closing strikes is the traditional default).
- **Presets** saved server-side, so the settings follow you between phone and laptop. Three
  are seeded on first run; saving over a name overwrites it.
- **Hide the countdown** if watching the clock is the problem.

## how the bells are made

There are no audio files. `src/server/bells.py` describes each voice as an additive-synthesis
recipe — a fundamental, a set of inharmonic partials with their own gains and decay times, a
noise transient for the mallet, and a detune that gives the slow beating a real bowl has —
and `static/js/bells.js` renders it with the Web Audio API. Bells are inharmonic (their
partials are not integer multiples of the fundamental), which is what makes them sound like
struck metal; the ratios in each voice approximate the instrument it imitates, including the
hum/prime/minor-third structure of a cast bell.

To add or retune a voice, edit `BELL_VOICES` in `bells.py`. Nothing else needs to change: the
page fetches the catalog from `/api/bells` and the synthesis is generic.

## how the timing works

The server owns the scheduling rules. `POST /api/schedule` turns a `SessionConfig` into a flat
timeline of bell events, and the browser does nothing but play it back — so the interesting
logic (where random bells land, which interval bells fit) is typed Python with tests, not
JavaScript.

Every bell for the whole sitting is scheduled on the Web Audio clock **up front**, rather than
fired from a JS timer. That means the bells stay sample-accurate and keep sounding if the tab
is backgrounded or the screen goes to sleep — which is the normal way to use this. A looping
silent source keeps the audio graph busy to discourage browsers from suspending the context.
That is not a guarantee on every mobile browser: iOS in particular may still stop audio when
the device is locked, so if you sit with the screen off, check it works on your phone first.

## api

| | |
|---|---|
| `GET /api/bells` | the bell voice catalog |
| `POST /api/schedule` | a `SessionConfig` in, a timeline of bells out |
| `GET /api/presets` | saved presets |
| `PUT /api/presets` | save a preset (upsert by name) |
| `DELETE /api/presets/{id}` | delete a preset |

## development

```bash
just setup      # install deps, pre-commit hooks, and the playwright chromium browser
just run        # run locally on http://localhost:8080
just test-fast  # scheduling + API tests, in process (no podman needed)
just test       # the whole suite, including containerized browser tests
just check      # lint, format, typecheck
```

Python work uses [uv](https://docs.astral.sh/uv/). Use `uv add <pkg>` to add a dependency and
`uv add --group dev <pkg>` for a dev-only one.

`tests/test_schedule.py` and `tests/test_api.py` cover the scheduling rules and the API in
process. `tests/test_app.py` drives the real page in a browser, including a test that renders
every bell voice through an `OfflineAudioContext` and measures peak level and decay — a broken
envelope would otherwise fail silently, since nothing else can hear the output.

`just test` uses the OpenHost test harness, which builds the Dockerfile and runs the app under
**podman** fronted by the real OpenHost router. `stack.url` requires owner auth (use
`stack.owner_session` for requests, or `stack.playwright_login(page)` for browser tests);
`stack.app_url` hits the container directly.

Presets live in the SQLite database OpenHost provisions from `sqlite = ["main"]` in
`openhost.toml`, at `$OPENHOST_SQLITE_MAIN`. `just run` points that at `.local/sqlite/main.db`.

## deploying

```bash
oh app reload meditation-timer --update --wait --instance <name>
oh app logs meditation-timer --instance <name>
```
