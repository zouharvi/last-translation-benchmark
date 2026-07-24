"""
Last Translation Benchmark - FastAPI backend
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import get_users, init_db
from .public_dashboard_source import close_public_dashboard_source_client
from .routers import router
from .utils import schedule_daily_backup, schedule_daily_notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("uvicorn.access").addFilter(lambda record: False)
    logging.getLogger("gunicorn.access").addFilter(lambda record: False)
    await init_db()
    print("\n=== Magic login links ===")
    host_public = os.getenv("HOST_PUBLIC")
    for user in await get_users():
        print(
            f"  {user['username']:>20}  {host_public}/?user={user['username']}&token={user['magic_token']}"
        )
    print("=========================\n")
    


    backup_task = asyncio.create_task(schedule_daily_backup())
    notif_task = asyncio.create_task(schedule_daily_notifications())
    try:
        yield
    finally:
        backup_task.cancel()
        notif_task.cancel()
        await close_public_dashboard_source_client()
        try:
            await backup_task
            await notif_task
        except asyncio.CancelledError:
            pass




# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Last Translation Benchmark", lifespan=lifespan)


@app.middleware("http")
async def custom_logging(request: Request, call_next):
    body_bytes = await request.body()

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    request._receive = receive
    response = await call_next(request)

    # mask all common file requests and /api/me
    if request.url.path.endswith((".css", ".js", ".svg", ".png", ".json", ".ico")) or request.url.path == "/api/me":
        return response

    print(
        time.strftime("[%Y-%m-%d %H:%M]"),
        response.status_code,
        request.query_params.get("user") or request.cookies.get("ltb_user"),
        request.method,
        request.url.path,
        flush=True,
    )

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://last-translation-benchmark.vilda.net"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ---------------------------------------------------------------------------
# Transparent HTML serving (no redirect, URL stays the same)
# ---------------------------------------------------------------------------

_STATIC_DIR = os.path.dirname(os.path.abspath(__file__)) + "/static"


@app.get("/admin")
async def serve_admin():
    return FileResponse(_STATIC_DIR + "/admin.html")


@app.get("/contribute")
async def serve_contribute():
    return FileResponse(_STATIC_DIR + "/contribute.html")


@app.get("/review")
async def serve_review():
    return FileResponse(_STATIC_DIR + "/review.html")


@app.get("/profile")
async def serve_profile():
    return FileResponse(_STATIC_DIR + "/profile.html")


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(_STATIC_DIR + "/dashboard.html")


# redirect favicon.ico to assets/favicon.svg to avoid 404 errors in logs
@app.get("/favicon.ico")
async def serve_favicon():
    return FileResponse(_STATIC_DIR + "/assets/favicon.svg")


# ---------------------------------------------------------------------------
# Static frontend — must be mounted last
# ---------------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(
        directory=os.path.dirname(os.path.abspath(__file__)) + "/static", html=True
    ),
    name="static",
)
