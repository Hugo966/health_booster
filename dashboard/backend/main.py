"""FastAPI — /data sirve la hoja en JSON (solo lectura) y /chat habla con Jarvis."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chat as chat_mod
import memoria
from sheets import fetch_all

app = FastAPI(title="Health Booster — Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _arranque():
    # Crear las tablas aquí evita que el primer mensaje pague ese coste.
    memoria.init()


@app.get("/data")
def data():
    return fetch_all()


class Mensaje(BaseModel):
    sesion: str = "default"
    mensaje: str
    # Permite comparar proveedores sin reiniciar el backend ni tocar el .env.
    proveedor: str | None = None


@app.post("/chat")
def chat(m: Mensaje):
    """Devuelve {texto, acciones}: lo que dice Jarvis y lo que el navegador debe hacer."""
    return chat_mod.responder(m.sesion, m.mensaje, m.proveedor)
