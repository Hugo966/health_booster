"""FastAPI — /data sirve la hoja en JSON, /formulario escribe en ella y /chat habla con Jarvis."""
import json
import os
import queue
import threading
import time
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import chat as chat_mod
import formularios
import huecos
import memoria
import meteo
import plan_pestanas
import proveedor
import rapido
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
        try:
            # El tiempo, por lo mismo y por una razón más: desde la VM, Open-Meteo falla
            # a ratos (medido el 2026-11-16: dos peticiones de cinco colgadas hasta
            # agotar el plazo, y quince seguidas perfectas media hora después). Pedido
            # desde aquí, ese tropiezo lo paga un hilo de fondo y el turno sigue leyendo
            # la caché; pedido desde el parte, le mete el plazo entero de espera a un
            # mensaje y, en frío, deja a Jarvis sin saber si llueve. Su TTL (20 min) es
            # mayor que esta vuelta, así que la mayoría de las veces esto no pide nada.
            meteo.ahora()
        except Exception:
            pass
        time.sleep(240)

app = FastAPI(title="Health Booster — Dashboard API")
# Antes esto era allow_origins=["*"], que valía cuando la API solo leía. Ahora hay
# endpoints que escriben en la hoja, así que una web cualquiera abierta en el navegador
# del usuario podría hacerles POST. Se limita a orígenes locales y de LAN privada: sigue
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
    # `sugerencias` NO son valores guardados: es dónde arranca la rueda (el último peso,
    # la última cafeína). Van aparte justo para que la UI no pueda confundirlas con un
    # valor puesto y mandarlas sin que el usuario las toque.
    # `precargados` es lo contrario: no está guardado pero sale escrito Y se manda sin
    # que el usuario lo toque (el dolor que ya apuntó en el keep ese día).
    guardado = formularios.leer(tipo, fecha)
    return {"tipo": tipo, "fecha": fecha, "valores": guardado,
            "sugerencias": formularios.sugerencias(tipo, fecha),
            "precargados": formularios.precarga(tipo, fecha, guardado)}


@app.post("/formulario/{tipo}")
def formulario_guardar(tipo: str, datos: dict = Body(...)):
    fecha = str(datos.get("fecha", "")).strip()
    # `borrar` viaja aparte de los valores: un campo vacío sigue significando "no lo he
    # contestado", que es lo que permite corregir un solo número sin reenviar el día.
    borrar = datos.get("borrar") or []
    valores = {k: v for k, v in datos.items() if k not in ("fecha", "borrar")}
    try:
        res = formularios.guardar(tipo, fecha, valores, borrar)
    except ValueError as e:
        # 422 con el mensaje en español: se lo va a leer Jarvis para volver a preguntar.
        raise HTTPException(422, str(e))
    res["valores"] = formularios.leer(tipo, fecha)
    return res


@app.get("/ubicacion")
def ubicacion_leer():
    """Dónde está el usuario, para el tiempo. `null` si todavía no lo ha dicho:
    es lo que hace que la app se lo pregunte la primera vez que la abre."""
    return {"ubicacion": meteo.ubicacion(), "tiempo": meteo.ahora()}


@app.post("/ubicacion")
def ubicacion_guardar(datos: dict = Body(...)):
    # Vale dirección, ciudad o código postal: se resuelve lo que escriba y se guarda solo
    # la ciudad y el país, nunca la calle.
    texto = str(datos.get("lugar", "") or datos.get("ciudad", "")).strip()
    if not texto:
        raise HTTPException(422, "Dime una dirección, una ciudad o un código postal.")
    lugar = meteo.buscar_lugar(texto)
    if not lugar:
        raise HTTPException(422, f"No encuentro '{texto}'. Prueba con la ciudad a secas "
                                 "o con el código postal.")
    try:
        meteo.guardar_ubicacion(lugar)
    except Exception as e:
        # Lo típico es un 429 de cuota de Google, que se pasa solo. Decirlo en castellano
        # importa: esto lo lee Hugo en la pantalla, no en un log.
        raise HTTPException(503, f"No he podido guardarlo ahora mismo ({type(e).__name__}). "
                                 "Suele ser la cuota de Google: inténtalo en un minuto.")
    return {"ubicacion": lugar, "tiempo": meteo.ahora()}


@app.get("/plan/pendientes")
def plan_pendientes():
    """Qué pestañas del plan están sin colocar, y dónde arrancan las ruedas."""
    return {"pendientes": plan_pestanas.pendientes(),
            "sugerencia": plan_pestanas.sugerencia(),
            "campos": [vars(c) for c in plan_pestanas.CAMPOS]}


@app.post("/plan/enrutar")
def plan_enrutar(datos: dict = Body(...)):
    """Dice a qué semana es una pestaña del plan que el pipeline no supo colocar.

    Se contesta con el código de un tirón (`P2B4S3`) en vez de con tres campos: es un
    dato que el usuario escribe una vez cada varios meses, y teclearlo entero es menos lío que
    tres ruedas. Lo mismo se puede hacer hablando con Jarvis (`enrutar_pestana`).
    """
    try:
        return {"ok": plan_pestanas.resolver_codigo(str(datos.get("pestana", "")),
                                                    str(datos.get("codigo", "")))}
    except ValueError as e:
        raise HTTPException(422, str(e))


class Mensaje(BaseModel):
    sesion: str = "default"
    mensaje: str
    # Permite comparar proveedores sin reiniciar el backend ni tocar el .env.
    proveedor: str | None = None


class Sesion(BaseModel):
    sesion: str = "default"


# Turno en vuelo por sesión, para poder cortarlo. Que el navegador cierre el socket NO
# basta: el turno corre en un hilo aparte que seguiría hasta el final, ejecutando por el
# camino las herramientas que escriben en la hoja del usuario. Y el generador SSE suele estar
# bloqueado en `cola.get()`, no en un `yield`, así que tampoco se puede confiar en que le
# llegue el `GeneratorExit` a tiempo. Por eso el frontend lo pide explícitamente.
_turnos: dict[str, threading.Event] = {}
_turnos_lock = threading.Lock()


def _abrir_turno(sesion: str) -> threading.Event:
    """Registra el turno y cancela el anterior de esa sesión, si lo hubiera.

    Lo segundo es la red de seguridad del backend: aunque el navegador no avise (pestaña
    cerrada de golpe, red caída), mandar un mensaje nuevo corta el viejo."""
    corte = threading.Event()
    with _turnos_lock:
        previo = _turnos.get(sesion)
        if previo is not None:
            previo.set()
        _turnos[sesion] = corte
    return corte


def _cerrar_turno(sesion: str, corte: threading.Event) -> None:
    with _turnos_lock:
        # Solo si sigue siendo el nuestro: otro turno pudo haber tomado el relevo.
        if _turnos.get(sesion) is corte:
            _turnos.pop(sesion, None)


@app.post("/chat/cancelar")
def chat_cancelar(s: Sesion):
    """El usuario ha cortado a Jarvis. Lo llama el navegador al abortar la petición."""
    with _turnos_lock:
        corte = _turnos.get(s.sesion)
    if corte is None:
        return {"cancelado": False}
    corte.set()
    return {"cancelado": True}


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

    # El atajo de `enrutar` solo vale para ABRIR conversación. Haiku recibe el mensaje
    # suelto, sin una línea del hilo, así que en mitad de una charla contesta con mucho
    # aplomo cosas que no tienen que ver — o directamente falsas: el 2026-10-05, rellenando
    # formularios, soltó "no tengo memoria de mensajes anteriores" (mentira: el hilo estaba
    # ahí) y "no necesitas repetir como un loro". Era la mayor parte de lo que hacía
    # insufrible hablar con él.
    # Con la conversación caliente se tira el atajo y se va por Sonnet, que sí ve el hilo.
    # La muletilla se queda: esa no depende del contexto y tapa el silencio igual.
    if ruta["respuesta"] and memoria.conversacion_caliente(m.sesion):
        ruta = {"respuesta": "", "muletilla": ruta["muletilla"] or "neutra"}

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
    corte = _abrir_turno(m.sesion)

    def al_texto(t):
        # El punto de corte fino: se comprueba en cada token. Lanzar aquí sale del `with`
        # del stream de Anthropic, así que además de abortar el turno se deja de generar.
        if corte.is_set():
            raise chat_mod.Cancelado()
        cola.put(("texto", t))

    def trabajo():
        try:
            caja["r"] = chat_mod.responder(
                m.sesion, m.mensaje, m.proveedor,
                al_texto=al_texto, cancelado=corte.is_set,
            )
        except chat_mod.Cancelado:
            # El usuario le ha cortado: no es un fallo y no hay nada que contarle. La respuesta
            # a medias NO se guarda (lo decide `chat.responder`).
            caja["cancelado"] = True
        except Exception as e:  # el error viaja en el evento final, no rompe el flujo
            caja["error"] = str(e)
        finally:
            _cerrar_turno(m.sesion, corte)
            cola.put(None)

    threading.Thread(target=trabajo, daemon=True).start()

    # La coletilla a medida va POR LA MISMA COLA que el texto, desde su propio hilo.
    # Escribirla cuesta ~400 ms de mediana, con picos medidos de 1,1 s. Pedirla en línea
    # antes de emitir retrasaba ese rato el primer evento del stream —o sea, el texto en
    # pantalla— por una frase que encima puede acabar sin usarse: si la respuesta real
    # llega antes de los 4,5 s, el navegador la descarta. Y esperar dentro del generador
    # no arregla nada, porque es secuencial y bloquearía el texto igual.
    # Por la cola sale en cuanto está, sin frenar a nadie, y si llega tarde el navegador
    # ya no la dirá — que es exactamente lo que debe pasar.
    if ruta["muletilla"]:
        if rapido.disponible():
            def coletilla():
                # Si el modelo falla o no llega, sale el nombre del pool pregrabado: el
                # comportamiento de siempre. Nunca se queda sin coletilla por esto.
                texto = rapido.muletilla(m.mensaje)
                cola.put(("muletilla_texto", texto) if texto
                         else ("muletilla", ruta["muletilla"]))

            threading.Thread(target=coletilla, daemon=True).start()
        else:
            cola.put(("muletilla", ruta["muletilla"]))

    def eventos():
        try:
            while True:
                item = cola.get()
                if item is None:
                    break
                tipo, dato = item
                yield f"data: {json.dumps({'tipo': tipo, 'texto': dato}, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            # El navegador se fue sin avisar (pestaña cerrada, red caída). Red secundaria:
            # el camino normal es `POST /chat/cancelar`, que llega antes y no depende de
            # que este generador esté parado en un `yield` justo cuando toca.
            corte.set()
            raise
        r = caja.get("r") or {}
        fin = {
            "tipo": "fin",
            "texto": r.get("texto", ""),
            "acciones": r.get("acciones", []),
            "uso": r.get("uso", {}),
            "error": caja.get("error"),
            # Lo mira quien siga escuchando: si el corte lo provocó un mensaje NUEVO de la
            # misma sesión, este cliente sigue ahí y no debe quedarse colgado esperando.
            "cancelado": bool(caja.get("cancelado")),
        }
        yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        # Sin esto, un proxy intermedio podría bufferizar y anular la ganancia.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- servir el frontend ya compilado -----------------------------------------
# En la VM no hay nginx ni Vite: el backend sirve también el `dist/`, así que todo sale
# por un único puerto y en el MISMO origen. Eso quita de en medio el CORS y hace que
# `tailscale serve` solo tenga que exponer un puerto.
# Va al final a propósito: las rutas de la API se registran antes y tienen prioridad
# sobre este montaje en "/". En desarrollo no existe `dist/` y no se monta nada, así que
# Vite sigue funcionando igual.
_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
