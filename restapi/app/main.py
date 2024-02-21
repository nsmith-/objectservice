from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import auth
from .db import dbengine
from .routers import items


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.account_provider.setup()
    yield
    await dbengine.dispose()


app = FastAPI(
    title="objectservice",
    root_path="/api",
    lifespan=lifespan,
)
app.include_router(items.router)
app.include_router(auth.router)


@app.get("/")
def read_root():
    data = {
        "Hello": "World",
    }
    return data
