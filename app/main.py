"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import applications, auth, health, pages

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="İlanUyum", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(pages.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
