"""FastAPI — endpoint único /data que sirve la hoja en JSON (solo lectura)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sheets import fetch_all

app = FastAPI(title="Health Booster — Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/data")
def data():
    return fetch_all()
