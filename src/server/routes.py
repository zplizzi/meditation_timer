import random
from pathlib import Path

import attr
from litestar import MediaType
from litestar import delete
from litestar import get
from litestar import post
from litestar import put
from litestar.exceptions import NotFoundException
from litestar.params import FromPath

from server import presets as presets_store
from server.bells import BELL_VOICES
from server.bells import BellVoice
from server.presets import Preset
from server.presets import PresetInput
from server.schedule import Schedule
from server.schedule import build_schedule
from server.session import SessionConfig

STATIC_DIR = Path(__file__).parent / "static"
INDEX_PATH = STATIC_DIR / "index.html"


@attr.s(auto_attribs=True, frozen=True)
class HealthStatus:
    status: str


@get("/health", sync_to_thread=False)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


@get("/", media_type=MediaType.HTML, sync_to_thread=False)
def index() -> str:
    return INDEX_PATH.read_text()


@get("/api/bells", sync_to_thread=False)
def bell_voices() -> tuple[BellVoice, ...]:
    return BELL_VOICES


@post("/api/schedule", status_code=200, sync_to_thread=False)
def create_schedule(data: SessionConfig) -> Schedule:
    return build_schedule(data, random.Random())


@get("/api/presets", sync_to_thread=True)
def get_presets() -> tuple[Preset, ...]:
    return presets_store.list_presets()


@put("/api/presets", status_code=200, sync_to_thread=True)
def put_preset(data: PresetInput) -> Preset:
    return presets_store.save_preset(data)


@delete("/api/presets/{preset_id:int}", sync_to_thread=True)
def remove_preset(preset_id: FromPath[int]) -> None:
    if not presets_store.delete_preset(preset_id):
        raise NotFoundException(detail=f"no preset with id {preset_id}")


ROUTE_HANDLERS = [health, index, bell_voices, create_schedule, get_presets, put_preset, remove_preset]
