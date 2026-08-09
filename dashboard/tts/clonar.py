"""Clonación de voz — genera el "Jarvis" de Hugo a partir de un clip de referencia.

El catálogo de voces de Qwen no daba el acento español que Hugo quería, así que se
clona el timbre desde una muestra suya (el Jarvis del doblaje de Iron Man, o el
audio que consiga más limpio). La clonación la hace el modelo **Base** (no el
CustomVoice de las 9 voces): `create_voice_clone_prompt` + `generate_voice_clone`.

Qué necesita el clonado para salir bien:
  - REF_AUDIO: voz LIMPIA y sola (sin música ni efectos), ~10-30 s. Cuanto más
    limpia, mejor clona. WAV o MP3.
  - REF_TEXT: la transcripción EXACTA de lo que se dice en REF_AUDIO (no el texto a
    generar). Mejora bastante la calidad; el modelo condiciona sobre ella.

Uso:
    venv/Scripts/python.exe clonar.py

Edita las tres constantes de abajo (REF_AUDIO, REF_TEXT y las FRASES a decir) y
corre. Deja el resultado en muestras/ como jarvis_clon_*.wav.
"""
import time
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

# Carpeta local (sin symlinks: Windows sin modo desarrollador falla al enlazar los
# ficheros en subcarpetas del Base, p.ej. speech_tokenizer/). Descargado con
# snapshot_download(local_dir=...). El Base es la variante que clona.
MODELO = r"E:/jarvis_tts/models/qwen3-base"
SALIDA = Path(__file__).parent / "muestras"

# --- lo que hay que rellenar con el clip de Hugo -----------------------------
# Ruta al clip de referencia (voz limpia de Jarvis). Ponlo en E:\jarvis_tts\ref\.
REF_AUDIO = r"E:\jarvis_tts\ref\jarvis_ref.wav"
# Modo con transcripción (SOLO_TIMBRE=False): además del timbre, condiciona el
# RITMO y la entonación con el audio + su texto → menos robótico que el x-vector
# solo. REF_TEXT es la transcripción del clip de referencia (sacada con Whisper y
# corregida "Yardis"->"Jarvis"), NO lo que queremos que diga después.
SOLO_TIMBRE = False
REF_TEXT = (
    "Hola, soy Jarvis. Buenos días, son las 7 de la mañana, señor. "
    "Accediendo a la red Oracle. No hay señal de anomalías cardíacas o de "
    "actividad cerebral inusual. Accediendo a satélites. Aunque dan terabytes "
    "de cálculos que se necesitarán antes de probar el vuelo. La nube de Oracle "
    "completó el análisis. Nuestra descarga ya está completa, señor. Estamos en "
    "línea y listos."
)
# Semitonos a bajar el tono para dar gravedad. Hugo pidió el punto medio entre 0 y
# -2, así que -1. Se aplica a todas las salidas.
GRAVE_SEMITONES = -1

FRASES = [
    ("clon_1", "Hola Hugo, ¿qué tal tío? Hoy estás de puta madre, tío, "
               "revienta ese entreno, bien clarito, lo tienes hecho."),
    ("clon_2", "Buenas, has dormido seis horas y media, así que hoy vas con el "
               "depósito medio vacío."),
]


def main():
    SALIDA.mkdir(exist_ok=True)
    ref = Path(REF_AUDIO)
    if not ref.exists():
        raise SystemExit(f"No encuentro el audio de referencia: {ref}\n"
                         f"Déjalo ahí (voz limpia, ~10-30s) y ajusta REF_AUDIO/REF_TEXT.")

    print(f"Cargando {MODELO} …")
    t0 = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        MODELO, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa",
    )
    print(f"  cargado en {time.perf_counter() - t0:.1f}s")

    # El prompt de clonación se construye una vez desde la referencia y se reutiliza.
    modo = "solo timbre (x-vector)" if SOLO_TIMBRE else f"con transcripción: {REF_TEXT!r}"
    print(f"Construyendo el prompt de clonación desde la referencia [{modo}]…")
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(ref),
        ref_text=REF_TEXT if not SOLO_TIMBRE else None,
        x_vector_only_mode=SOLO_TIMBRE,
    )

    import subprocess

    for nombre, frase in FRASES:
        t0 = time.perf_counter()
        wavs, sr = model.generate_voice_clone(
            text=frase, language="Spanish", voice_clone_prompt=prompt,
        )
        dt = time.perf_counter() - t0
        dur = len(wavs[0]) / sr

        # Natural, tal cual sale del modelo (referencia limpia).
        natural = SALIDA / f"jarvis_{nombre}.wav"
        sf.write(natural, wavs[0], sr)

        # Grave con rubberband (ffmpeg): baja el tono GRAVE_SEMITONES preservando los
        # formantes, así queda grave pero natural. librosa metía un "enlatado" metálico.
        if GRAVE_SEMITONES:
            factor = 2 ** (GRAVE_SEMITONES / 12)  # semitonos -> multiplicador de pitch
            grave = SALIDA / f"jarvis_{nombre}_grave.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(natural),
                 "-af", f"rubberband=pitch={factor:.5f}:formant=preserved", str(grave)],
                check=True,
            )
        print(f"  {nombre:8} -> jarvis_{nombre}.wav (+_grave)  "
              f"({dt:.1f}s para {dur:.1f}s, ratio {dt/dur:.2f})")

    print(f"\nListo. Escucha los jarvis_*.wav en: {SALIDA}")


if __name__ == "__main__":
    main()
