from litestar import Litestar
from litestar.static_files import create_static_files_router

from server.db import init_db
from server.presets import seed_default_presets
from server.routes import ROUTE_HANDLERS
from server.routes import STATIC_DIR


def on_startup() -> None:
    init_db()
    seed_default_presets()


app = Litestar(
    route_handlers=[
        *ROUTE_HANDLERS,
        create_static_files_router(path="/static", directories=[STATIC_DIR], name="static"),
    ],
    on_startup=[on_startup],
)
