from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routes import router
from app.scheduler import init_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await init_scheduler()
    yield


app = FastAPI(title="UptimeGuard", version="1.0.0", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
