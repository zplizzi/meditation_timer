import re

import httpx
from openhost_test_harness import OpenhostStack
from playwright.sync_api import Page
from playwright.sync_api import expect


def test_health_endpoint(stack: OpenhostStack) -> None:
    response = httpx.get(f"{stack.app_url}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_setup_page_loads_bells_and_presets(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    expect(page.get_by_role("heading", name="Meditation Timer")).to_be_visible()

    # Voices come from the server's catalog.
    expect(page.locator("#start-voice option")).to_have_count(7)
    expect(page.locator("#start-voice")).to_have_value("singing-bowl")

    # The seeded presets are clickable.
    expect(page.get_by_role("button", name="Bell every 5 min", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="5 random bells", exact=True)).to_be_visible()


def test_choosing_a_preset_fills_in_the_form(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.get_by_role("button", name="Bell every 5 min", exact=True).click()
    expect(page.locator("#duration")).to_have_value("25")
    expect(page.locator("#interval-minutes")).to_have_value("5")
    expect(page.locator("#mode-picker .seg[data-mode='fixed']")).to_have_attribute("aria-checked", "true")
    # The hint comes back from the server, which is what decides how many bells fit.
    expect(page.locator("#interval-hint")).to_contain_text("4 bells")


def test_interval_bells_are_marked_on_the_ring_for_fixed_sessions(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.get_by_role("button", name="Bell every 5 min", exact=True).click()
    page.get_by_role("button", name="Begin").click()
    expect(page.locator("#session")).to_be_visible()
    expect(page.locator("#ring-marks line")).to_have_count(4)


def test_random_bells_are_left_off_the_ring(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.get_by_role("button", name="5 random bells", exact=True).click()
    page.get_by_role("button", name="Begin").click()
    expect(page.locator("#session")).to_be_visible()
    expect(page.locator("#ring-marks line")).to_have_count(0)
    expect(page.locator("#session-detail")).to_contain_text("still to come")


def test_running_pausing_and_ending_a_session(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.locator("#duration").fill("2")
    page.locator("#prepare").fill("0")
    page.get_by_role("button", name="Begin").click()

    expect(page.locator("#session")).to_be_visible()
    expect(page.locator("#setup")).to_be_hidden()
    # The clock is counting down off the audio clock.
    expect(page.locator("#countdown")).to_have_text(re.compile(r"^(2:00|1:5\d)$"))
    first = page.locator("#countdown").inner_text()
    expect(page.locator("#countdown")).not_to_have_text(first, timeout=5_000)

    page.get_by_role("button", name="Pause").click()
    expect(page.locator("#phase-label")).to_have_text("paused")
    frozen = page.locator("#countdown").inner_text()
    page.wait_for_timeout(1_500)
    expect(page.locator("#countdown")).to_have_text(frozen)

    page.get_by_role("button", name="Resume").click()
    expect(page.locator("#phase-label")).not_to_have_text("paused")

    page.get_by_role("button", name="End").click()
    expect(page.locator("#setup")).to_be_visible()
    expect(page.locator("#session")).to_be_hidden()


def test_lead_in_counts_down_before_the_sitting_starts(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.locator("#duration").fill("10")
    page.locator("#prepare").fill("30")
    page.get_by_role("button", name="Begin").click()
    expect(page.locator("#phase-label")).to_have_text("settling in")
    expect(page.locator("#countdown")).to_have_text(re.compile(r"^0:(30|2\d)$"))


def test_saving_and_deleting_a_preset_from_the_page(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.locator("#duration").fill("42")
    page.locator("#preset-name").fill("Browser test sit")
    page.get_by_role("button", name="Save", exact=True).click()

    saved = page.get_by_role("button", name="Browser test sit", exact=True)
    expect(saved).to_be_visible()

    page.reload()
    expect(page.get_by_role("button", name="Browser test sit", exact=True)).to_be_visible()

    page.get_by_role("button", name="Delete preset Browser test sit").click()
    expect(page.get_by_role("button", name="Browser test sit", exact=True)).to_have_count(0)


def test_settings_are_remembered_across_reloads(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    page.locator("#duration").fill("37")
    page.locator("#duration").blur()
    page.locator("#mode-picker .seg[data-mode='random']").click()
    page.reload()
    expect(page.locator("#duration")).to_have_value("37")
    expect(page.locator("#mode-picker .seg[data-mode='random']")).to_have_attribute("aria-checked", "true")


# Renders every bell through an OfflineAudioContext in the page and measures the result. This is the only way to
# check the synthesis actually makes a sound — a broken envelope or a bad partial would otherwise fail silently.
RENDER_VOICES = """
async () => {
  const { BellEngine } = await import("/static/js/bells.js");
  const voices = await (await fetch("/api/bells")).json();
  const measured = {};
  for (const voice of voices) {
    const rate = 44100;
    const ctx = new OfflineAudioContext(1, rate * 8, rate);
    const engine = new BellEngine(ctx);
    engine.setVoices(voices);
    engine.setVolume(0.7);
    engine.prepare();
    engine.strike(voice.id, 0.05);
    const data = (await ctx.startRendering()).getChannelData(0);
    let peak = 0;
    for (let i = 0; i < data.length; i++) {
      peak = Math.max(peak, Math.abs(data[i]));
    }
    let tail = 0;
    for (let i = data.length - 1; i >= 0; i--) {
      if (Math.abs(data[i]) > peak * 0.001) {
        tail = i / rate;
        break;
      }
    }
    measured[voice.id] = { peak, tail };
  }
  return measured;
}
"""


def test_every_bell_voice_renders_audible_unclipped_audio(stack: OpenhostStack, page: Page) -> None:
    stack.playwright_login(page)
    page.goto(stack.url)
    measured = page.evaluate(RENDER_VOICES)

    assert set(measured) == {"singing-bowl", "temple-bell", "deep-gong", "crystal-bowl", "chime", "wood-block"}
    for voice_id, result in measured.items():
        assert 0.1 < result["peak"] < 1.0, f"{voice_id} is silent or clipping: {result}"

    # The voices are level-matched to each other, so no bell is startling after the one before it.
    bells = [result["peak"] for voice_id, result in measured.items() if voice_id != "wood-block"]
    assert max(bells) / min(bells) < 1.5

    # Bowls and gongs ring on; the wood block is a click.
    assert measured["singing-bowl"]["tail"] > 5.0
    assert measured["deep-gong"]["tail"] > 5.0
    assert measured["chime"]["tail"] < 5.0
    assert measured["wood-block"]["tail"] < 0.5
