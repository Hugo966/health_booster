"""FastAPI — /data sirve la hoja en JSON, /formulario escribe en ella y /chat habla con Jarvis."""
import json
import os
import queue
import threading
import time

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import chat as chat_mod
import formularios
import huecos
import memoria
import proveedor
import sheets
from sheets import fetch_all


def _mantener_datos_calientes():
    """Refresca la caché de la hoja por debajo de su TTL (300s), en bucle. El chat
    lee la hoja en cada mensaje (briefing): sin esto, cuando la caché caduca el
    siguiente mensaje espera ~6s a Google. Así nunca se enfría."""
    while True:
        try:
            # ttl=0 fuerza la relectura. Con el TTL por defecto (300s) esta llamada daba
            # acierto de caché a los 240s y no refrescaba nada: el refresco real caía cada
            # ~480s y la caché podía llegar con 8 minutos de retraso.
            fetch_all(ttl=0)
        except Exception:
            pass
        time.sleep(240)

app = FastAPI(title="Health Booster — Dashboard API")
# Antes esto era allow_origins=["*"], que valía cuando la API solo leía. Ahora hay
# endpoints que escriben en la hoja, así que una web cualquiera abierta en el navegador
# de Hugo podría hacerles POST. Se limita a orígenes locales y de LAN privada: sigue
# valiendo para el dashboard, para abrirlo desde el móvil por wifi y para el escuchador.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\]|"
                       r"192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
                       r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$",
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


# --- formularios: rellenar y corregir desde la app ---------------------------
# Hasta ahora los datos solo entraban por Google Forms. El cuerpo es plano
# ({"fecha": ..., campos...}) y todos los campos son opcionales salvo la fecha, porque la
# voz manda trozos sueltos. Los rangos NO se declaran aquí: viven en formularios.ESQUEMA,
# que es la única fuente, y de ahí los saca también la UI.

@app.get("/formularios/esquema")
def formularios_esquema():
    return formularios.esquema_publico()


@app.get("/formularios/estado")
def formularios_estado(dias: int = 14):
    return huecos.estado(dias=dias)


@app.get("/formulario/{tipo}")
def formulario_leer(tipo: str, fecha: str):
    if tipo not in formularios.ESQUEMA:
        raise HTTPException(404, f"No existe el formulario '{tipo}'.")
    return {"tipo": tipo, "fecha": fecha, "valores": formularios.leer(tipo, fecha)}


@app.post("/formulario/{tipo}")
def formulario_guardar(tipo: str, datos: dict = Body(...)):
    fecha = str(datos.get("fecha", "")).strip()
    valores = {k: v for k, v in datos.items() if k != "fecha"}
    try:
        res = formularios.guardar(tipo, fecha, valores)
    except ValueError as e:
        # 422 con el mensaje en español: se lo va a leer Jarvis para volver a preguntar.
        raise HTTPException(422, str(e))
    res["valores"] = formularios.leer(tipo, fecha)
    return res


class Mensaje(BaseModel):
    sesion: str = "default"
    mensaje: str
    # Permite comparar proveedores sin reiniciar el backend ni tocar el .env.
    proveedor: str | None = None


@app.post("/chat")
def chat(m: Mensaje):
    """Devuelve {texto, acciones}: lo que dice Jarvis y lo que el navegador debe hacer."""
    return chat_mod.responder(m.sesion, m.mensaje, m.proveedor)


@app.get("/hilo")
def hilo(sesion: str = "hugo", n: int = 40):
    """El hilo tal y como lo tiene el backend. La UI lo consulta para enterarse de lo
    hablado por el micro (dashboard/escucha), que llega aquí sin pasar por el navegador.
    El `id` es autoincremental, así que a la UI le basta comparar el último para saber
    si se ha perdido algo."""
    memoria.init()
    return {"mensajes": memoria.hilo_con_id(sesion, n)}


@app.post("/chat/stream")
def chat_stream(m: Mensaje):
    """Lo mismo que /chat pero por SSE, soltando el texto según el modelo lo escribe.

    Existe por la latencia: esperar la respuesta entera son ~6 s (los marca su longitud,
    no el prompt, que va cacheado). Emitiendo sobre la marcha, el navegador manda la
    PRIMERA frase al TTS y Jarvis empieza a hablar en ~2 s mientras redacta el resto.

    Eventos: `{tipo:"texto", texto}` por cada trozo y un `{tipo:"fin", texto, acciones,
    uso, error}` al terminar. Las acciones van al final a propósito: hasta que el modelo
    no acaba no se sabe si además de hablar quiere abrir un panel.

    El turno corre en un hilo aparte y se comunica por cola porque `chat.responder` es
    síncrono (SDK de Anthropic en modo bloqueante) y no queremos reescribirlo a async.
    """
    # Primero el enrutado (Haiku, ~0,7 s). Va ANTES y solo, no en paralelo: lanzado a la
    # vez que Sonnet se pisaban y tardaba 2,9 s. Además así un "hola" ni llega a Sonnet.
    ruta = chat_mod.enrutar(m.mensaje)

    if ruta["respuesta"]:
        corto = chat_mod.responder_rapido(m.sesion, m.mensaje, ruta["respuesta"])

        def solo_texto():
            yield f"data: {json.dumps({'tipo': 'texto', 'texto': corto['texto']}, ensure_ascii=False)}\n\n"
            fin = {"tipo": "fin", "texto": corto["texto"], "acciones": [], "uso": {},
                   "error": None}
            yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            solo_texto(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    cola: queue.Queue = queue.Queue()
    caja: dict = {}

    def trabajo():
        try:
            caja["r"] = chat_mod.responder(
                m.sesion, m.mensaje, m.proveedor,
                al_texto=lambda t: cola.put(("texto", t)),
            )
        except Exception as e:  # el error viaja en el evento final, no rompe el flujo
            caja["error"] = str(e)
        finally:
            cola.put(None)

    threading.Thread(target=trabajo, daemon=True).start()

    def eventos():
        # La coletilla ya la trae el enrutado: sale la primera, sin esperar a Sonnet.
        if ruta["muletilla"]:
            yield f"data: {json.dumps({'tipo': 'muletilla', 'texto': ruta['muletilla']}, ensure_ascii=False)}\n\n"
        while True:
            item = cola.get()
            if item is None:
                break
            tipo, dato = item
            yield f"data: {json.dumps({'tipo': tipo, 'texto': dato}, ensure_ascii=False)}\n\n"
        r = caja.get("r") or {}
        fin = {
            "tipo": "fin",
            "texto": r.get("texto", ""),
            "acciones": r.get("acciones", []),
            "uso": r.get("uso", {}),
            "error": caja.get("error"),
        }
        yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        # Sin esto, un proxy intermedio podría bufferizar y anular la ganancia.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
