"""Cliente gspread cacheado — SOLO lectura de la hoja Health_booster_data.

Reutiliza el mismo Service Account y SHEET_ID que los pipelines, leyendo el
`.env` de la raíz del proyecto (el backend vive en dashboard/backend/).
"""
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
TABS = ["derived_diario", "entreno_sesion", "rm1", "peso", "entreno_sets"]

_client = None
_cache = {"ts": 0.0, "data": None}


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

    Cachea en memoria TTL segundos (por defecto 5 min). Las pestañas que no
    existan o fallen devuelven lista vacía en vez de romper.
    """
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < ttl:
        return _cache["data"]

    sh = client().open_by_key(os.environ["SHEET_ID"])
    data = {}
    for tab in TABS:
        try:
            records = sh.worksheet(tab).get_all_records()
            data[tab] = pd.DataFrame(records).to_dict(orient="records")
        except Exception:
            data[tab] = []

    _cache.update(ts=now, data=data)
    return data
