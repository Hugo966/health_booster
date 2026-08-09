"""Audición de voces de Qwen3-TTS en español — antes de cablear nada.

El objetivo es que Hugo elija el timbre "Jarvis" DE OÍDO y confirmar de paso que
el modelo instala, cabe en la VRAM del portátil (6 GB) y que el español suena
bien. Genera la misma frase con cada voz candidata y deja los .wav en muestras/.

Se corre una sola vez, a mano:
    venv/Scripts/python.exe prueba.py

No usa flash-attn (falla de compilar en Windows); con `attn_implementation="sdpa"`
va perfecto y sin dependencias extra.
"""
import time
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODELO = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
SALIDA = Path(__file__).parent / "muestras"

# Frase con números y coloquialismo, para oír cómo lee cifras y el tono chulesco
# de Jarvis (que es como va a hablar de verdad).
FRASE = (
    "Hola Hugo, ¿qué tal tío? Hoy estás de puta madre, tío, "
    "revienta ese entreno, bien clarito, lo tienes hecho."
)

# Voces masculinas del catálogo (las candidatas a Jarvis: grave y con presencia).
# Se prueban varias porque el timbre se juzga mejor comparando. Ono_Fu/Uncle_Fu y
# Dylan/Eric/Ryan/Aiden son las de registro más grave según la doc.
VOCES = ["Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden"]


def main():
    SALIDA.mkdir(exist_ok=True)
    print(f"VRAM libre antes de cargar: "
          f"{torch.cuda.mem_get_info()[0] / 1e9:.2f} GB" if torch.cuda.is_available()
          else "CUDA no disponible")

    print(f"Cargando {MODELO} …")
    t0 = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        MODELO,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    print(f"  cargado en {time.perf_counter() - t0:.1f}s")
    if torch.cuda.is_available():
        print(f"  VRAM en uso tras cargar: "
              f"{torch.cuda.memory_allocated() / 1e9:.2f} GB")

    for voz in VOCES:
        try:
            t0 = time.perf_counter()
            wavs, sr = model.generate_custom_voice(
                text=FRASE, language="Spanish", speaker=voz,
            )
            dt = time.perf_counter() - t0
            destino = SALIDA / f"jarvis_{voz}.wav"
            sf.write(destino, wavs[0], sr)
            dur = len(wavs[0]) / sr
            # El ratio dt/dur dice si es viable en tiempo real: <1 genera más rápido
            # de lo que dura, que es lo que necesita un asistente de voz.
            print(f"  {voz:10} -> {destino.name}  ({dt:.1f}s para {dur:.1f}s de audio, "
                  f"ratio {dt / dur:.2f})")
        except Exception as e:
            print(f"  {voz:10} -> FALLO: {type(e).__name__}: {e}")

    print(f"\nListo. Escucha los .wav en: {SALIDA}")


if __name__ == "__main__":
    main()
