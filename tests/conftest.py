from collections.abc import Iterator
from typing import Any

import pytest
from openhost_test_harness import OpenhostStack


@pytest.fixture(scope="session")
def stack() -> Iterator[OpenhostStack]:
    """Build the app's Dockerfile, run it under podman per openhost.toml, and front it with the real OpenHost
    router.

    - stack.url                    — through the router; requires owner auth
    - stack.owner_session          — a requests.Session authenticated as the zone owner
    - stack.playwright_login(page) — log a playwright page in as the owner for browser tests
    - stack.app_url                — direct to the container (control your own headers; eg the health probe)
    """
    with OpenhostStack() as s:
        yield s


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """The timer only makes sound after a user gesture, and headless Chromium has no audio device; these flags let
    the AudioContext start and keep the test run silent."""
    args = list(browser_type_launch_args.get("args", []))
    args += ["--autoplay-policy=no-user-gesture-required", "--mute-audio"]
    return {**browser_type_launch_args, "args": args}
