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
import hashlib
import io
import os
import random
import re
import sys
import threading
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
# se perdía (el usuario: "la dice muy plana"). v3 es expresivo y además entiende etiquetas
# inline tipo [sarcastic]. Cuesta el doble ($0,10/1k caracteres), que a su volumen son
# ~5 $/mes más. Si algún día prima la velocidad, aquí se vuelve a eleven_flash_v2_5.
MODELO_11 = os.environ.get("ELEVENLABS_MODELO", "eleven_v3")
# Para las muletillas: plano pero instantáneo (~0,8 s frente a los ~3,5 s de v3).
MODELO_RAPIDO = os.environ.get("ELEVENLABS_MODELO_RAPIDO", "eleven_flash_v2_5")
# stability: en v3 son presets — 0.0 Creative / 0.5 Natural / 1.0 Robust. Creative es el
# que responde a la intención y a las etiquetas; Robust suena estable pero monótono.
ESTABILIDAD = float(os.environ.get("ELEVENLABS_STABILITY", "0.0"))
# 0.7–1.2. El usuario se quejó de que XTTS hablaba lento; aquí 1.0 ya suena natural.
VELOCIDAD = float(os.environ.get("ELEVENLABS_SPEED", "1.0"))
TIMEOUT_S = 20

# Respaldo local (solo portátil con GPU).
XTTS_DIR = os.environ.get("JARVIS_XTTS_DIR", r"E:/jarvis_tts/models/xtts-v2")
REF_AUDIO = os.environ.get("JARVIS_REF_AUDIO", r"E:/jarvis_tts/ref/jarvis_ref.wav")

app = FastAPI(title="Jarvis Voz")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    # Sin exponerla, el navegador no puede leer qué muletilla sonó y repetiría la misma
    # al encadenar la segunda.
    expose_headers=["X-Muletilla"],
)

_xtts: dict = {}  # se rellena solo si hay que tirar del respaldo


# Jarvis marca la intención con etiquetas tipo [sarcastic] (ver personalidad.py). Solo
# las entiende v3; cualquier otro motor las leería en alto ("corchete sarcastic"), así
# que se quitan antes de mandarle el texto.
ETIQUETAS = re.compile(r"\[[a-z][a-z ]{1,20}\]\s*")


def _sin_etiquetas(texto: str) -> str:
    return ETIQUETAS.sub("", texto).strip()


def _de_elevenlabs(texto: str, rapido: bool = False) -> bytes:
    """Pide el audio a ElevenLabs. Lanza si no hay clave o la API falla, para que el
    llamante caiga al respaldo."""
    if not API_KEY:
        raise RuntimeError("sin ELEVENLABS_API_KEY")
    # `rapido`: Flash en vez de v3. v3 tiene un suelo de ~3,5 s por petición, que para la
    # respuesta buena compensa (es donde vive la ironía) pero para una coletilla de
    # relleno la haría inútil: cuando sonara, ya estaría lista la respuesta de verdad.
    modelo = MODELO_RAPIDO if rapido else MODELO_11
    es_v3 = modelo.startswith("eleven_v3")
    ajustes = {"stability": ESTABILIDAD, "similarity_boost": 0.75}
    # `speed` solo lo aceptan los modelos v2/Flash; v3 lo rechaza con 422.
    if not es_v3:
        ajustes["speed"] = VELOCIDAD
        texto = _sin_etiquetas(texto)
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={"text": texto, "model_id": modelo, "voice_settings": ajustes},
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


# --- muletillas ---------------------------------------------------------------
# v3 tiene un suelo de ~3,5 s por petición, así que entre que el usuario termina de hablar y
# Jarvis suelta la primera frase real pasan ~9 s de silencio incómodo. Se tapa con una
# muletilla ("déjame ver…") que suena AL INSTANTE mientras se genera la respuesta de
# verdad. No hace falta generarlas en vivo: son fijas, así que se generan una vez y se
# guardan en disco (coste único de céntimos, latencia cero a partir de ahí).
# Duran ~3-4 s a propósito: es lo que hay que cubrir hasta la primera frase real.
MULETILLAS_DIR = Path(os.environ.get("JARVIS_MULETILLAS", r"E:/jarvis_tts/muletillas"))
# Largas a propósito (~4-5 s de audio): tienen que cubrir hasta que la primera frase
# real esté generada. Con muletillas de 2 s quedaba un silencio de 7 s detrás.
#
# DOS POOLS, porque la muletilla tiene que pegar con lo que el usuario acaba de decir: soltar
# "déjame que lo mire" después de un "hola" queda absurdo. `consulta` es para cuando
# pregunta por sus datos (ahí sí hay algo que mirar) y `neutra` sirve para cualquier
# otra cosa. A los saludos NO se les pone muletilla: eso lo decide el frontend.
# Se generan con v3 y CON etiquetas ([sarcastic]…) a propósito: una muletilla plana
# detrás de una respuesta con retintín desentona muchísimo (el usuario). Como el coste se paga
# una sola vez, aquí sí sale a cuenta el modelo caro. Y hay ~20 por pool para que tarde
# mucho en repetirse: es lo que compensa que no mencionen lo que acabas de decir.
MULETILLAS: dict[str, list[str]] = {
    "consulta": [
        "[curious] Déjame que mire eso un segundo, que tus datos y yo tenemos una relación complicada.",
        "A ver qué tenemos por aquí… dame un momento, que estoy rebuscando entre tus números.",
        "Espera, que lo estoy mirando. No te muevas, que esto tarda menos de lo que parece.",
        "[curious] Buena pregunta. Déjame revisarlo bien antes de soltarte cualquier tontería.",
        "Un segundo, que saco los datos y te digo algo con sentido.",
        "Vale, déjame ver qué dicen tus números, que para algo me los aprendo.",
        "[sarcastic] Ay, madre. Déjame mirar esto antes de darte un disgusto.",
        "Dame un segundo, que estoy cruzando datos como un poseso.",
        "Espera que lo compruebo, no vaya a inventarme algo y luego me la líes.",
        "[mischievously] Uy, esto promete. Déjame mirarlo con calma.",
        "A ver, que consulto tus registros antes de opinar.",
        "Un momento, que no quiero decirte una burrada sin mirarlo.",
        "[curious] Vamos a ver qué me cuentan tus datos de esto.",
        "Déjame un segundo, que estoy sacando los números.",
        "Espera, que me asomo a tus registros y te digo.",
        "Dame un segundo. Prefiero mirarlo que soltarte lo primero que se me ocurra.",
        "[sarcastic] Menuda pregunta. Déjame revisar antes de contestarte.",
        "Voy a mirarlo bien, dame un momento.",
        "A ver… estoy repasando lo que tengo apuntado.",
        "Un segundito, que compruebo una cosa.",
    ],
    "neutra": [
        "Mmm, déjame pensarlo un segundo, que no quiero soltarte lo primero que se me ocurra.",
        "A ver, dame un momento y le doy una vuelta a eso.",
        "Espera un segundo, que estoy ordenando las ideas.",
        "[curious] Vaya, eso merece que me lo piense un poco.",
        "Mmm… déjame procesar eso un momento.",
        "Joder, dame un segundo para pensarlo bien.",
        "[curious] Interesante. Espera que le dé una vuelta.",
        "Uy, eso da para pensarlo. Un segundo.",
        "A ver cómo te digo esto… dame un momento.",
        "Mmm, buena esa. Déjame pensar.",
        "Espera, que quiero contestarte bien a eso.",
        "[mischievously] Vaya, vaya. Déjame darle una vuelta.",
        "Dame un segundo, que le estoy dando vueltas.",
        "Mmm… vale, déjame ordenar esto.",
        "Un momento, que me lo pienso.",
        "A ver, dame un segundo para procesarlo.",
        "[curious] Eso no me lo esperaba. Espera un poco.",
        "Déjame pensarlo, que no quiero meter la pata.",
        "Mmm, espera un segundo que lo proceso.",
        "Vale, dame un momento para eso.",
    ],
    # Para encadenar cuando la primera se queda corta. Cortas y de CONTINUACIÓN: repetir
    # otro "déjame que mire eso" sonaba redundante (el usuario). Empiezan con un "mmm" o un
    # "a ver" para que enganchen con lo anterior en vez de arrancar de cero.
    "segunda": [
        "Mmm… a ver.",
        "Un segundo más, que ya casi lo tengo.",
        "Mmm, casi está.",
        "A ver… ya voy.",
        "Espera, que ya te digo.",
        "Mmm… un momento.",
        "Ya casi.",
        "Un poco más…",
        "Mmm, sí… espera.",
        "Casi lo tengo.",
        "A ver… ya.",
        "Espera, ya.",
    ],
}
TODAS_MULETILLAS = [f for lista in MULETILLAS.values() for f in lista]


def _ruta_muletilla(frase: str) -> Path:
    """Nombre por hash del texto: al cambiar una frase se genera sola con otro nombre y
    la vieja queda huérfana (unos KB), sin tener que borrar nada a mano."""
    return MULETILLAS_DIR / f"m_{hashlib.sha1(frase.encode('utf-8')).hexdigest()[:8]}.mp3"


def _muletillas_hechas(tipo: str | None = None) -> list[Path]:
    frases = MULETILLAS.get(tipo, []) if tipo else TODAS_MULETILLAS
    return [p for p in map(_ruta_muletilla, frases) if p.exists() and p.stat().st_size > 1000]


def _preparar_muletillas():
    """Genera las que falten y las deja en disco. Corre en segundo plano al arrancar
    para no retrasar el servicio; si no hay clave, simplemente no habrá muletillas."""
    try:
        MULETILLAS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[muletillas] no puedo crear {MULETILLAS_DIR}: {e}")
        return
    for frase in TODAS_MULETILLAS:
        destino = _ruta_muletilla(frase)
        if destino.exists() and destino.stat().st_size > 1000:
            continue
        try:
            destino.write_bytes(_de_elevenlabs(frase))
            print(f"[muletillas] generada {destino.name}: {frase!r}")
        except Exception as e:
            print(f"[muletillas] falló {destino.name}: {e}")
            return  # sin clave o sin saldo: no insistir con las demás


class Peticion(BaseModel):
    texto: str
    # Muletillas: prioriza velocidad sobre expresividad (Flash en vez de v3).
    rapido: bool = False


@app.on_event("startup")
def _arranque():
    threading.Thread(target=_preparar_muletillas, daemon=True).start()


@app.get("/salud")
def salud():
    return {"listo": True, "elevenlabs": bool(API_KEY), "voz": VOICE_ID,
            "xtts_cargado": "modelo" in _xtts, "muletillas": len(_muletillas_hechas())}


@app.get("/muletilla")
def muletilla(tipo: str = "neutra", evitar: str = ""):
    """Una muletilla al azar del pool pedido, ya generada. Suena mientras se cocina la
    respuesta real. `evitar` es el nombre de la que acaba de sonar, para no repetirla
    cuando hay que encadenar una segunda."""
    hechas = _muletillas_hechas(tipo) or _muletillas_hechas()
    if not hechas:
        return Response(status_code=204)  # aún no están: el frontend sigue sin ellas
    opciones = [p for p in hechas if p.name != evitar] or hechas
    elegida = random.choice(opciones)
    return Response(content=elegida.read_bytes(), media_type="audio/mpeg",
                    headers={"X-Muletilla": elegida.name})


@app.post("/voz")
def voz(p: Peticion):
    texto = (p.texto or "").strip()
    if not texto:
        return Response(status_code=204)
    try:
        return Response(content=_de_elevenlabs(texto, p.rapido), media_type="audio/mpeg")
    except Exception as e:
        print(f"[voz] ElevenLabs falló ({e}); tiro del respaldo local.")
        return Response(content=_de_xtts(texto), media_type="audio/wav")
