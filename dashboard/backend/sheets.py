"""Cliente gspread cacheado — SOLO lectura de la hoja Health_booster_data.

Reutiliza el mismo Service Account y SHEET_ID que los pipelines, leyendo el
`.env` de la raíz del proyecto (el backend vive en dashboard/backend/).
"""
import logging
import os
import time
from pathlib import Path

import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# El .env vive en la raíz del proyecto: dashboard/backend/sheets.py -> ../../.env
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
# `wellness_am` y `wellness_pm` son las pestañas ORIGEN de los formularios (las llenan
# los Google Forms y ahora también la app). Se leen para el editor y el semáforo de
# huecos: `derived_diario` no sirve para eso porque solo lo regenera el pipeline y no
# tiene fila para los días vacíos, que son justo los que hay que detectar.
TABS = ["derived_diario", "entreno_sesion", "rm1", "peso", "entreno_sets",
        "wellness_am", "wellness_pm"]

log = logging.getLogger(__name__)

# Tras un fallo de lectura se sirve lo último bueno durante este rato antes de volver a
# intentarlo. Reintentar en CADA petición, con la cuota de Google agotada, solo echaría
# más leña al fuego que provocó el fallo.
ESPERA_TRAS_FALLO_S = 30

_client = None
# `ts` es la hora de la última lectura COMPLETAMENTE buena; una lectura con fallos no la
# renueva, para que se reintente en cuanto pase `reintento_ts`.
_cache = {"ts": 0.0, "data": None, "reintento_ts": 0.0}


def client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SA_JSON"], scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def fetch_all(ttl: int = 300):
    """Devuelve un dict {tab: [registros]} con las pestañas que consume el panel.

    Cachea en memoria TTL segundos (por defecto 5 min).

    Si una pestaña no se puede leer se conserva lo último que se leyó bien de ella. NO se
    cachea el vacío: hacerlo convertía un fallo pasajero (cuota de Google, un corte de
    red) en "no tienes datos" durante 5 minutos, con el semáforo pintando en rojo días
    que estaban rellenos y el editor en blanco. Pasó el 2026-09-04 justo después de
    guardar un formulario, y parecía una pérdida de datos que nunca existió.
    """
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"] < ttl or now < _cache["reintento_ts"]):
        return _cache["data"]

    previo = _cache["data"] or {}
    try:
        sh = client().open_by_key(os.environ["SHEET_ID"])
    except Exception as e:
        # Abrir la hoja falla en bloque cuando se agota la cuota, y aquí no vale con
        # propagar: dejaría la petición en 500 y al panel sin nada. Si ya teníamos datos
        # se sirven, y se reintenta luego.
        log.warning("sheets: no se pudo abrir la hoja (%s: %s)", type(e).__name__, e)
        if previo:
            _cache.update(reintento_ts=now + ESPERA_TRAS_FALLO_S)
            return previo
        raise

    data = {}
    fallos = []
    for tab in TABS:
        try:
            records = sh.worksheet(tab).get_all_records()
            data[tab] = pd.DataFrame(records).to_dict(orient="records")
        except Exception as e:
            # Sin este log el motivo se perdía y desde el servidor el fallo era invisible.
            log.warning("sheets: no se pudo leer la pestaña %r (%s: %s). Me quedo con las "
                        "%d filas que ya tenía.", tab, type(e).__name__, e,
                        len(previo.get(tab, [])))
            fallos.append(tab)
            data[tab] = previo.get(tab, [])

    if fallos:
        _cache.update(data=data, reintento_ts=now + ESPERA_TRAS_FALLO_S)
    else:
        _cache.update(ts=now, data=data, reintento_ts=0.0)
    return data


def invalidar(tab: str | None = None) -> None:
    """Refresca la caché tras escribir. Con `tab`, solo esa pestaña.

    Se llama tras escribir un formulario: si no, el semáforo y el editor seguirían
    viendo el estado anterior hasta 300s, y parecería que el guardado no ha hecho nada.

    Lo de refrescar UNA pestaña no es una optimización cosmética: releer las 7 en cada
    guardado (con `entreno_sets` a la cabeza, 1500+ filas) es lo que nos ponía contra la
    cuota de la API. Al guardar un formulario solo cambia su propia pestaña.
    """
    if tab is None or _cache["data"] is None:
        _cache["ts"] = 0.0
        return
    try:
        sh = client().open_by_key(os.environ["SHEET_ID"])
        records = sh.worksheet(tab).get_all_records()
        _cache["data"][tab] = pd.DataFrame(records).to_dict(orient="records")
    except Exception as e:
        # Si el refresco puntual falla, que la próxima lectura completa lo intente.
        log.warning("sheets: no se pudo refrescar %r tras escribir (%s: %s)",
                    tab, type(e).__name__, e)
        _cache["ts"] = 0.0
