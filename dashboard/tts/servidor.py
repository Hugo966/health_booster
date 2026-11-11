"""Servicio TTS de Jarvis — la voz clonada, servida por HTTP.

Vive APARTE del backend principal (dashboard/backend) a propósito: arrastra torch +
Qwen3-TTS (~4 GB en VRAM) y solo corre en el portátil con GPU. El backend principal
sigue ligero y portable; el otro equipo no levanta esto y el frontend cae a la
voz del navegador (ver `voz.ts`).

Carga el modelo Base (el que clona) UNA vez al arrancar (~10 s) y arma el prompt de
clonación desde la referencia (Jarvis de Iron Man, voz aislada). Luego cada `POST /voz`
genera el audio, le baja el tono -1 semitono con rubberband (grave sin "enlatado") y
lo devuelve como WAV.

Arrancar (desde el venv de E:, con el modelo en E:):
    HF_HOME=E:/jarvis_tts/hf_cache \
    E:/jarvis_tts/venv/Scripts/python.exe -m uvicorn servidor:app --port 8123

Se elige puerto 8123 para no chocar con el backend (8099), el frontend (5173) ni Ollama.
"""
import io
import os
import subprocess
import tempfile
from pathlib import Path

import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qwen_tts import Qwen3TTSModel

# Todo lo pesado en E: (C: sin espacio). El Base es la variante que clona. Se puede
# alternar 1.7B <-> 0.6B con JARVIS_TTS_MODELO sin tocar código: el 0.6B (2,5 GB) cabe
# holgado en los 6 GB de VRAM y no derrama a RAM con textos largos → mucho más rápido,
# a cambio de algo menos de calidad. Por defecto el 1.7B (mejor voz).
MODELO = os.environ.get("JARVIS_TTS_MODELO", r"E:/jarvis_tts/models/qwen3-base")
REF_AUDIO = r"E:/jarvis_tts/ref/jarvis_ref.wav"
# Transcripción de la referencia (mejora la fluidez; sacada con faster-whisper y
# corregida). Sin esto el clon sale robótico (modo x-vector solo).
REF_TEXT = (
    "Hola, soy Jarvis. Buenos días, son las 7 de la mañana, señor. "
    "Accediendo a la red Oracle. No hay señal de anomalías cardíacas o de "
    "actividad cerebral inusual. Accediendo a satélites. Aunque dan terabytes "
    "de cálculos que se necesitarán antes de probar el vuelo. La nube de Oracle "
    "completó el análisis. Nuestra descarga ya está completa, señor. Estamos en "
    "línea y listos."
)
GRAVE_SEMITONES = -1  # gravedad aprobada por el usuario

app = FastAPI(title="Jarvis TTS")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Estado global: el modelo y el prompt de clonación, cargados una vez.
_estado: dict = {}


@app.on_event("startup")
def _cargar():
    print(f"Cargando modelo de voz {MODELO} …")
    modelo = Qwen3TTSModel.from_pretrained(
        MODELO, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa",
    )
    prompt = modelo.create_voice_clone_prompt(
        ref_audio=REF_AUDIO, ref_text=REF_TEXT, x_vector_only_mode=False,
    )
    _estado["modelo"] = modelo
    _estado["prompt"] = prompt
    print("Voz de Jarvis lista.")


def _grave(wav, sr: int) -> bytes:
    """Escribe el wav, le baja el tono con rubberband (formant=preserved, sin
    enlatado) y devuelve los bytes.

    IMPORTANTE: ffmpeg escribe la salida a un fichero temporal, NO a una tubería.
    Con `pipe:1` no puede volver atrás a rellenar el tamaño de la cabecera RIFF y
    la deja en 0xFFFFFFFF; el navegador entonces no reproduce (o tarda >1 min
    buffeando). Con fichero seekable la cabecera sale correcta."""
    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    entrada = buf.getvalue()
    if not GRAVE_SEMITONES:
        return entrada
    factor = 2 ** (GRAVE_SEMITONES / 12)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        salida = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0",
             "-af", f"rubberband=pitch={factor:.5f}:formant=preserved", salida],
            input=entrada, check=True,
        )
        return Path(salida).read_bytes()
    finally:
        Path(salida).unlink(missing_ok=True)


class Peticion(BaseModel):
    texto: str


@app.get("/salud")
def salud():
    return {"listo": "modelo" in _estado}


@app.post("/voz")
def voz(p: Peticion):
    """Genera el audio de `texto` con la voz de Jarvis y lo devuelve como WAV."""
    texto = (p.texto or "").strip()
    if not texto:
        return Response(status_code=204)
    modelo = _estado["modelo"]
    wavs, sr = modelo.generate_voice_clone(
        text=texto, language="Spanish", voice_clone_prompt=_estado["prompt"],
    )
    audio = _grave(wavs[0], sr)
    return Response(content=audio, media_type="audio/wav")
