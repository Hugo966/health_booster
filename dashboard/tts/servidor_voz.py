"""Servicio de voz de Jarvis — ElevenLabs con XTTS local de respaldo.

Es el servicio de voz "de producción": el frontend (voz.ts) le pide `POST /voz` y él
decide de dónde sale el audio, en este orden:

  1. **ElevenLabs** (nube, Flash v2.5): ~75 ms de latencia y la mejor voz en castellano.
     Es el camino normal. Solo le sale el TEXTO de la respuesta, ningún dato de salud.
  2. **XTTS local** si ElevenLabs falla (sin clave, sin saldo, sin internet): ~0,3x
     tiempo real en la 3060. Se carga PEREZOSAMENTE, solo la primera vez que hace falta,
     para no ocupar 2,2 GB de VRAM cuando la nube funciona.
  3. Si esto ni arranca, `voz.ts` cae solo a la voz del navegador.

Se descartó Qwen3-TTS (servidor.py) tras medirlo: ~2x tiempo real y un precipicio a
~12x con textos largos al desbordar los 6 GB de VRAM. XTTS lo gana en todo.

Arrancar:
    E:/jarvis_tts/venv_xtts/Scripts/python.exe -m uvicorn servidor_voz:app --port 8123

Config (en el `.env` de la raíz del proyecto, que no va a git):
    ELEVENLABS_API_KEY=sk_...
    ELEVENLABS_VOICE_ID=wtCLyr4fALNxeekzlMyQ
"""
import io
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# La consola de Windows va en cp1252 y cualquier acento/flecha en un print revienta la
# petición entera con UnicodeEncodeError (pasó, y se comía hasta el respaldo).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# El .env vive en la raíz del proyecto (tres niveles arriba: tts -> dashboard -> raíz).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.environ.get("ELEVENLABS_API_KEY", "").strip()
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "wtCLyr4fALNxeekzlMyQ").strip()
# v3 en vez de Flash v2.5: Flash prioriza latencia y sale PLANO — la ironía de Jarvis
# se perdía (Hugo: "la dice muy plana"). v3 es expresivo y además entiende etiquetas
# inline tipo [sarcastic]. Cuesta el doble ($0,10/1k caracteres), que a su volumen son
# ~5 $/mes más. Si algún día prima la velocidad, aquí se vuelve a eleven_flash_v2_5.
MODELO_11 = os.environ.get("ELEVENLABS_MODELO", "eleven_v3")
# stability: en v3 son presets — 0.0 Creative / 0.5 Natural / 1.0 Robust. Creative es el
# que responde a la intención y a las etiquetas; Robust suena estable pero monótono.
ESTABILIDAD = float(os.environ.get("ELEVENLABS_STABILITY", "0.0"))
# 0.7–1.2. Hugo se quejó de que XTTS hablaba lento; aquí 1.0 ya suena natural.
VELOCIDAD = float(os.environ.get("ELEVENLABS_SPEED", "1.0"))
TIMEOUT_S = 20

# Respaldo local (solo portátil con GPU).
XTTS_DIR = os.environ.get("JARVIS_XTTS_DIR", r"E:/jarvis_tts/models/xtts-v2")
REF_AUDIO = os.environ.get("JARVIS_REF_AUDIO", r"E:/jarvis_tts/ref/jarvis_ref.wav")

app = FastAPI(title="Jarvis Voz")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_xtts: dict = {}  # se rellena solo si hay que tirar del respaldo


# Jarvis marca la intención con etiquetas tipo [sarcastic] (ver personalidad.py). Solo
# las entiende v3; cualquier otro motor las leería en alto ("corchete sarcastic"), así
# que se quitan antes de mandarle el texto.
ETIQUETAS = re.compile(r"\[[a-z][a-z ]{1,20}\]\s*")


def _sin_etiquetas(texto: str) -> str:
    return ETIQUETAS.sub("", texto).strip()


def _de_elevenlabs(texto: str) -> bytes:
    """Pide el audio a ElevenLabs. Lanza si no hay clave o la API falla, para que el
    llamante caiga al respaldo."""
    if not API_KEY:
        raise RuntimeError("sin ELEVENLABS_API_KEY")
    es_v3 = MODELO_11.startswith("eleven_v3")
    ajustes = {"stability": ESTABILIDAD, "similarity_boost": 0.75}
    # `speed` solo lo aceptan los modelos v2/Flash; v3 lo rechaza con 422.
    if not es_v3:
        ajustes["speed"] = VELOCIDAD
        texto = _sin_etiquetas(texto)
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={"text": texto, "model_id": MODELO_11, "voice_settings": ajustes},
        timeout=TIMEOUT_S,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    return r.content


def _cargar_xtts():
    """Carga XTTS y los latentes de la voz. Tarda ~13 s, así que solo se hace la primera
    vez que ElevenLabs falla."""
    import torch  # noqa: F401  (lo necesita TTS por debajo)
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import Xtts

    cfg = XttsConfig()
    cfg.load_json(os.path.join(XTTS_DIR, "config.json"))
    modelo = Xtts.init_from_config(cfg)
    modelo.load_checkpoint(cfg, checkpoint_dir=XTTS_DIR, use_deepspeed=False)
    modelo.cuda()
    gpt, spk = modelo.get_conditioning_latents(audio_path=[REF_AUDIO])
    _xtts.update(modelo=modelo, gpt=gpt, spk=spk, sr=cfg.audio.output_sample_rate)


def _de_xtts(texto: str) -> bytes:
    """Respaldo local. Devuelve WAV."""
    import librosa
    import numpy as np
    import soundfile as sf

    if "modelo" not in _xtts:
        print("ElevenLabs no disponible: cargando XTTS local de respaldo...")
        _cargar_xtts()
    salida = _xtts["modelo"].inference(
        _sin_etiquetas(texto), "es", _xtts["gpt"], _xtts["spk"],
        temperature=0.65, speed=1.15, enable_text_splitting=False,
    )
    wav = np.asarray(salida["wav"], dtype=np.float32)
    # XTTS mete a veces pausas de segundos dentro de una frase; se recortan.
    trozos = librosa.effects.split(wav, top_db=30.0)
    if len(trozos):
        hueco = np.zeros(int(_xtts["sr"] * 0.18), dtype=wav.dtype)
        piezas = []
        for i, (a, b) in enumerate(trozos):
            if i:
                piezas.append(hueco)
            piezas.append(wav[a:b])
        wav = np.concatenate(piezas)
    buf = io.BytesIO()
    sf.write(buf, wav, _xtts["sr"], format="WAV")
    return buf.getvalue()


class Peticion(BaseModel):
    texto: str


@app.get("/salud")
def salud():
    return {"listo": True, "elevenlabs": bool(API_KEY), "voz": VOICE_ID,
            "xtts_cargado": "modelo" in _xtts}


@app.post("/voz")
def voz(p: Peticion):
    texto = (p.texto or "").strip()
    if not texto:
        return Response(status_code=204)
    try:
        return Response(content=_de_elevenlabs(texto), media_type="audio/mpeg")
    except Exception as e:
        print(f"[voz] ElevenLabs falló ({e}); tiro del respaldo local.")
        return Response(content=_de_xtts(texto), media_type="audio/wav")
