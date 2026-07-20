"""FastAPI — /data sirve la hoja en JSON (solo lectura) y /chat habla con Jarvis."""
import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chat as chat_mod
import memoria
import proveedor
from sheets import fetch_all


def _mantener_datos_calientes():
    """Refresca la caché de la hoja por debajo de su TTL (300s), en bucle. El chat
    lee la hoja en cada mensaje (briefing): sin esto, cuando la caché caduca el
    siguiente mensaje espera ~6s a Google. Así nunca se enfría."""
    while True:
        try:
            fetch_all()
        except Exception:
            pass
        time.sleep(240)

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
    # Mantener caliente la caché de la hoja (afecta a cualquier proveedor).
    threading.Thread(target=_mantener_datos_calientes, daemon=True).start()
    # Precalentar el modelo local si es el proveedor activo, para que el primer
    # mensaje no espere a la carga en VRAM.
    if os.getenv("JARVIS_PROVEEDOR", "ollama").lower() == "ollama":
        threading.Thread(target=proveedor.precalentar, daemon=True).start()


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
