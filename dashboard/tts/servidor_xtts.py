"""Servicio TTS de Jarvis con XTTS-v2 (coqui-tts) — la voz clonada, servida por HTTP.

Alternativa a servidor.py (Qwen3): XTTS va MUCHO más rápido en esta GPU porque los
"latentes del hablante" (el timbre de Jarvis) se calculan UNA vez al arrancar desde la
referencia y se reutilizan en cada frase. Así desaparece el coste fijo por llamada que
lastraba a Qwen (que reprocesaba los 28 s de referencia cada vez). XTTS además genera
por debajo de tiempo real, así que la tubería por frases de `voz.ts` suena de un tirón.

Mismo interfaz que servidor.py a propósito (POST /voz {texto} -> WAV, GET /salud), y
mismo puerto 8123, para no tocar el frontend: se cambia de motor arrancando este en vez
de aquel.

Arrancar (venv aislado de XTTS, modelo en E:):
    E:/jarvis_tts/venv_xtts/Scripts/python.exe -m uvicorn servidor_xtts:app --port 8123

XTTS-v2 es de licencia no comercial (Coqui Public Model License); uso personal del usuario,
sin distribución, entra sin problema.
"""
import io
import os

import librosa
import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

MODELO_DIR = os.environ.get("JARVIS_XTTS_DIR", r"E:/jarvis_tts/models/xtts-v2")
# La misma referencia limpia de Jarvis que usa Qwen (voz aislada del doblaje de Iron Man).
REF_AUDIO = os.environ.get("JARVIS_REF_AUDIO", r"E:/jarvis_tts/ref/jarvis_ref.wav")
# XTTS habla despacio por defecto (speed=1.0). ~1.15 le da ritmo de conversación sin
# distorsionar. Ajustable en caliente con JARVIS_TTS_SPEED.
SPEED = float(os.environ.get("JARVIS_TTS_SPEED", "1.15"))
# temperature baja = menos "enrollamiento" (XTTS a veces alarga con pausas/ruido).
TEMPERATURE = float(os.environ.get("JARVIS_TTS_TEMP", "0.65"))


def _sin_silencios_largos(wav: np.ndarray, sr: int, top_db: float = 30.0, hueco: float = 0.18) -> np.ndarray:
    """Recorta el silencio de principio y fin y ACORTA los silencios interiores a
    `hueco` segundos. XTTS a veces mete pausas de varios segundos dentro de una misma
    frase (el "inmanejable" que reporta el usuario); esto las elimina sin tocar la voz."""
    intervalos = librosa.effects.split(wav, top_db=top_db)
    if len(intervalos) == 0:
        return wav
    relleno = np.zeros(int(sr * hueco), dtype=wav.dtype)
    piezas: list = []
    for i, (a, b) in enumerate(intervalos):
        if i:
            piezas.append(relleno)
        piezas.append(wav[a:b])
    return np.concatenate(piezas)

app = FastAPI(title="Jarvis TTS (XTTS)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_estado: dict = {}


@app.on_event("startup")
def _cargar():
    print(f"Cargando XTTS-v2 desde {MODELO_DIR} …")
    config = XttsConfig()
    config.load_json(os.path.join(MODELO_DIR, "config.json"))
    modelo = Xtts.init_from_config(config)
    # use_deepspeed=False: DeepSpeed no está en Windows; aun así va sobrado.
    modelo.load_checkpoint(config, checkpoint_dir=MODELO_DIR, use_deepspeed=False)
    modelo.cuda()

    print(f"Calculando latentes de la voz de Jarvis desde {REF_AUDIO} …")
    gpt_cond_latent, speaker_embedding = modelo.get_conditioning_latents(audio_path=[REF_AUDIO])

    _estado["modelo"] = modelo
    _estado["gpt"] = gpt_cond_latent
    _estado["spk"] = speaker_embedding
    _estado["sr"] = config.audio.output_sample_rate  # XTTS-v2: 24000
    print("Voz de Jarvis (XTTS) lista.")


class Peticion(BaseModel):
    texto: str


@app.get("/salud")
def salud():
    return {"listo": "modelo" in _estado}


@app.post("/voz")
def voz(p: Peticion):
    """Genera el audio de `texto` con la voz de Jarvis (XTTS) y lo devuelve como WAV."""
    texto = (p.texto or "").strip()
    if not texto:
        return Response(status_code=204)
    m = _estado["modelo"]
    salida = m.inference(
        texto, "es", _estado["gpt"], _estado["spk"],
        temperature=TEMPERATURE,
        speed=SPEED,
        enable_text_splitting=False,  # el troceo por frases lo hace el cliente (voz.ts)
    )
    wav = np.asarray(salida["wav"], dtype=np.float32)
    wav = _sin_silencios_largos(wav, _estado["sr"])
    buf = io.BytesIO()
    sf.write(buf, wav, _estado["sr"], format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
