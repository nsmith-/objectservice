import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from .db import dbengine
from .routers import items


@asynccontextmanager
async def lifespan(app: FastAPI):
    await auth.default_auth.load_server_metadata()
    auth.patch_for_testenv(auth.default_auth)
    yield
    await dbengine.dispose()


app = FastAPI(
    title="objectservice",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])
app.include_router(items.router)
app.include_router(auth.router)


@app.get("/")
def read_root(request: Request):
    data = {
        "Hello": "World",
        "url": request.base_url,
    }
    data["user"] = request.session.get("user")
    return data
