"""Escuchador local de Jarvis — el micro fuera del navegador.

POR QUÉ EXISTE
La escucha vivía en el navegador (Web Speech API, ver `voz.ts`), y Chrome la suspende
en cuanto la pestaña deja de estar visible: el usuario minimizaba y Jarvis se quedaba sordo.
No hay parámetro que lo evite, así que la escucha se saca del navegador a este proceso,
que oye siempre: minimizado, en otra ventana o con el navegador cerrado.

CÓMO FUNCIONA
Micro abierto en bucle → VAD (webrtcvad) recorta lo que es voz de lo que es silencio →
faster-whisper transcribe SOLO esos trozos (no el silencio, que sería tirar GPU) → si
oye "Jarvis" despierta, y a partir de ahí cada frase va al backend → la respuesta se
lee con el mismo servicio de voz del navegador (puerto 8123).

Reaprovecha lo ya montado: NO habla con ElevenLabs ni con el modelo por su cuenta, solo
llama a `/chat/stream` (8099) y a `/voz` (8123). Así el personaje, la memoria, las
muletillas y el enrutado son exactamente los mismos que por pantalla.

Esto NO se arranca solo: no está en `run.sh` ni es un servicio. Es un programa aparte que
solo corre si se lanza a mano con el comando de abajo. En el uso normal —tocar el orbe o
decir "Jarvis" en el navegador— este fichero no interviene para nada.

OJO si algún día se lanza: habría DOS micrófonos escuchando a la vez, el del navegador y
este, y los dos mandarían el mismo comando al backend por separado. Con esto en marcha,
dejar el orbe en reposo.

Arrancar (solo portátil):
    E:/jarvis_tts/venv/Scripts/python.exe escucha.py
    E:/jarvis_tts/venv/Scripts/python.exe escucha.py --listar   # ver micrófonos
    E:/jarvis_tts/venv/Scripts/python.exe escucha.py --micro 15 # elegir uno
"""
import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
import webrtcvad
from faster_whisper import WhisperModel

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BACKEND = os.environ.get("JARVIS_BACKEND", "http://localhost:8099")
TTS = os.environ.get("JARVIS_TTS", "http://localhost:8123")
# La MISMA sesión que usa el navegador (ver `SESION_FIJA` en chat.ts): el hilo vive en
# el backend y tiene que ser una sola conversación. Con sesiones distintas, lo hablado
# por micro no aparecía en el chat ni Jarvis lo recordaba al escribir después.
SESION = os.environ.get("JARVIS_SESION", "hugo")

# 16 kHz mono: lo que piden tanto webrtcvad como Whisper. Marcos de 30 ms (el VAD solo
# admite 10/20/30).
SR = 16000
MS_MARCO = 30
MUESTRAS_MARCO = SR * MS_MARCO // 1000

# Agresividad del VAD (0-3). 2 va bien en una habitación normal: 3 se come las sílabas
# flojas del final de frase.
VAD_AGRESIVIDAD = 2
# Silencio que da una frase por terminada. 700 ms: por debajo corta a mitad de frase
# cuando el usuario respira, por encima se hace lento de responder.
SILENCIO_FIN_MS = 700
# Por debajo de esto es ruido suelto (una tos, un golpe), no una frase.
MIN_VOZ_MS = 400
# Tope por si algo se queda escuchando para siempre.
MAX_FRASE_S = 15

# Modelo de transcripción. `small` es el equilibrio: `base` confunde "Jarvis" con
# cualquier cosa y `medium` no cabe cómodo junto a lo demás en 6 GB.
MODELO_STT = os.environ.get("JARVIS_STT", "small")

# Mismo abanico de grafías que en voz.ts: la J suena "y"/"ll" y el reconocedor confunde
# v/b, además de comerse la "s" final.
WAKE = re.compile(r"\b(?:ll|j|y|h)?ar[vb]i[sz]?\b", re.I)
# Tras hablar él, se ignora este rato para no oírse a sí mismo por los altavoces.
GRACIA_S = 0.8
# Si pasa esto sin que el usuario diga nada, se vuelve a dormir y hay que llamarlo otra vez.
DORMIRSE_S = 45

FIN_FRASE = re.compile(r"^[\s\S]*[.!?…](?=\s|$)")


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Escuchador:
    def __init__(self, micro=None):
        self.vad = webrtcvad.Vad(VAD_AGRESIVIDAD)
        self.cola = queue.Queue()
        self.micro = micro
        self.despierto_hasta = 0.0
        self.mudo_hasta = 0.0
        _log(f"Cargando Whisper '{MODELO_STT}' …")
        # int8 en GPU: rápido y deja VRAM libre para el resto.
        try:
            self.stt = WhisperModel(MODELO_STT, device="cuda", compute_type="int8_float16")
        except Exception as e:
            _log(f"Sin GPU para Whisper ({e}); tirando de CPU.")
            self.stt = WhisperModel(MODELO_STT, device="cpu", compute_type="int8")
        _log("Whisper listo.")

    # --- captura ---------------------------------------------------------
    def _entrada(self, datos, marcos, tiempo, estado):
        if estado:
            pass  # xruns puntuales: no merecen ruido en el log
        self.cola.put(bytes(datos))

    def frases(self):
        """Generador: suelta un array de audio por cada frase que oye."""
        with sd.RawInputStream(samplerate=SR, blocksize=MUESTRAS_MARCO, device=self.micro,
                               dtype="int16", channels=1, callback=self._entrada):
            _log("Micro abierto. Di «Jarvis» cuando quieras.")
            buf, hablando, silencio_ms, voz_ms = [], False, 0, 0
            while True:
                marco = self.cola.get()
                # Mientras Jarvis habla (o justo después) se tira lo que entre: si no, se
                # transcribe a sí mismo y se contesta solo.
                if time.time() < self.mudo_hasta:
                    buf, hablando, silencio_ms, voz_ms = [], False, 0, 0
                    continue
                es_voz = self.vad.is_speech(marco, SR)
                if es_voz:
                    buf.append(marco)
                    voz_ms += MS_MARCO
                    silencio_ms = 0
                    hablando = True
                elif hablando:
                    buf.append(marco)  # el rabito de silencio ayuda a Whisper
                    silencio_ms += MS_MARCO
                    if silencio_ms >= SILENCIO_FIN_MS or voz_ms > MAX_FRASE_S * 1000:
                        if voz_ms >= MIN_VOZ_MS:
                            crudo = b"".join(buf)
                            audio = np.frombuffer(crudo, dtype=np.int16).astype(np.float32) / 32768.0
                            yield audio
                        buf, hablando, silencio_ms, voz_ms = [], False, 0, 0

    # --- transcripción ---------------------------------------------------
    def transcribir(self, audio):
        segs, _ = self.stt.transcribe(audio, language="es", vad_filter=False,
                                      beam_size=1, condition_on_previous_text=False)
        return " ".join(s.text for s in segs).strip()

    # --- salida ----------------------------------------------------------
    def decir(self, texto):
        """Genera el audio con el servicio de voz y lo reproduce por los altavoces."""
        try:
            r = requests.post(f"{TTS}/voz", json={"texto": texto}, timeout=60)
            if r.status_code != 200 or not r.content:
                return
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(r.content)
                ruta = f.name
            try:
                # El servicio devuelve MP3 y soundfile no lo lee: se pasa por ffmpeg,
                # que ya hace falta en el resto del proyecto.
                wav = subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", ruta, "-f", "wav", "-ar", str(SR),
                     "-ac", "1", "pipe:1"],
                    capture_output=True, check=True).stdout
                datos, sr = sf.read(__import__("io").BytesIO(wav), dtype="float32")
                sd.play(datos, sr)
                sd.wait()
            finally:
                Path(ruta).unlink(missing_ok=True)
        except Exception as e:
            _log(f"  (no he podido hablar: {e})")
        finally:
            self.mudo_hasta = time.time() + GRACIA_S

    def muletilla(self, tipo):
        try:
            r = requests.get(f"{TTS}/muletilla", params={"tipo": tipo}, timeout=30)
            if r.status_code == 200 and r.content:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(r.content)
                    ruta = f.name
                try:
                    wav = subprocess.run(
                        ["ffmpeg", "-v", "error", "-i", ruta, "-f", "wav", "-ar", str(SR),
                         "-ac", "1", "pipe:1"],
                        capture_output=True, check=True).stdout
                    datos, sr = sf.read(__import__("io").BytesIO(wav), dtype="float32")
                    sd.play(datos, sr)
                    sd.wait()
                finally:
                    Path(ruta).unlink(missing_ok=True)
        except Exception:
            pass
        finally:
            self.mudo_hasta = time.time() + GRACIA_S

    # --- conversación ----------------------------------------------------
    def preguntar(self, texto):
        """Manda el comando al backend y va leyendo la respuesta frase a frase, igual
        que hace el navegador: así se empieza a oír antes de que termine de escribir."""
        pendiente, dicho_algo = "", False
        try:
            with requests.post(f"{BACKEND}/chat/stream",
                               json={"sesion": SESION, "mensaje": texto},
                               stream=True, timeout=120) as r:
                for linea in r.iter_lines(decode_unicode=True):
                    if not linea or not linea.startswith("data: "):
                        continue
                    ev = json.loads(linea[6:])
                    if ev.get("tipo") == "muletilla" and ev.get("texto"):
                        if not dicho_algo:
                            self.muletilla(ev["texto"])
                    elif ev.get("tipo") == "texto":
                        pendiente += ev["texto"]
                        m = FIN_FRASE.match(pendiente)
                        if m and len(m.group(0).strip()) >= 18:
                            self.decir(m.group(0))
                            dicho_algo = True
                            pendiente = pendiente[len(m.group(0)):]
                    elif ev.get("tipo") == "fin" and ev.get("error"):
                        _log(f"  error del backend: {ev['error']}")
        except Exception as e:
            _log(f"  no he podido preguntar: {e}")
        if pendiente.strip():
            self.decir(pendiente)

    def bucle(self):
        for audio in self.frases():
            texto = self.transcribir(audio)
            if not texto:
                continue
            despierto = time.time() < self.despierto_hasta
            m = None
            for m in WAKE.finditer(texto):
                pass  # nos quedamos con la ÚLTIMA aparición
            if m:
                resto = texto[m.end():].lstrip(" ,.:;!?¡¿-").strip()
                if not resto:
                    _log(f"«{texto}» → despierto, te escucho")
                    self.despierto_hasta = time.time() + DORMIRSE_S
                    continue
                comando = resto
            elif despierto:
                comando = texto.strip()
            else:
                continue  # dormido y sin nombrarlo: no es para él
            _log(f"→ {comando}")
            self.despierto_hasta = time.time() + DORMIRSE_S
            self.preguntar(comando)
            # Tras contestar sigue escuchando un rato, como el modo "activo" del orbe.
            self.despierto_hasta = time.time() + DORMIRSE_S


def main():
    ap = argparse.ArgumentParser(description="Escuchador local de Jarvis")
    ap.add_argument("--listar", action="store_true", help="lista los micrófonos y sale")
    ap.add_argument("--micro", type=int, default=None, help="índice del micrófono a usar")
    args = ap.parse_args()

    if args.listar:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"  [{i}] {d['name']}  (canales: {d['max_input_channels']})")
        return

    esc = Escuchador(micro=args.micro)
    try:
        esc.bucle()
    except KeyboardInterrupt:
        _log("Hasta luego.")


if __name__ == "__main__":
    main()
