"""Modelo RÁPIDO para las muletillas: escribir la coletilla a medida, no elegirla de un bote.

Qué problema resuelve
---------------------
Entre que Hugo termina de hablar y Jarvis suelta su primera frase real pasan varios
segundos (el TTS bueno tiene un suelo de ~3,5 s). Eso se tapa hoy con una muletilla
PREGRABADA ("déjame que lo mire…"): latencia cero y con retintín, porque se generó una vez
con el modelo caro. El precio es que es genérica — no menciona lo que él acaba de decir.

Escribirla a medida se descartó en su día y el motivo está en `chat.enrutar`: había que
sintetizarla en el momento, y en modo rápido el TTS sale plano. Lo que ha cambiado el
2026-09-12 es que la primera muletilla ya no se dice al segundo, sino a los 4,5 s
(`ESPERA_MULETILLA_MS` en `voz.ts`), **así que ahora hay presupuesto de tiempo** para
generar texto y sintetizarlo antes de que haga falta.

Cómo está montado
-----------------
- **Groq**, elegido midiendo y no leyendo: `scratchpad/elegir_modelo.py` cronometra los
  modelos que permite la clave con el caso real. Aquí lo que importa no es que el modelo
  sea listo —es una frase de diez palabras— sino que conteste rápido, y eso lo pone el
  hardware de quien lo sirve.
- **Habla API de OpenAI, que es la que expone Groq**, con `requests` y sin SDK. Efecto
  lateral útil: cambiando `GROQ_URL` sirve cualquier otro proveedor compatible sin tocar
  código, si algún día compensa.
- **El nombre del modelo NO se cablea.** Los catálogos cambian (Groq retiró varios en
  agosto de 2026) y un identificador quemado aquí se pudre en silencio: sin `GROQ_MODELO`
  en el `.env`, esto sencillamente no se activa.
- **Falla en silencio y hacia el lado bueno.** Sin clave, con error o pasado el plazo,
  devuelve `None` y el sistema sigue con las muletillas pregrabadas de siempre. Nunca
  puede dejar a Jarvis callado ni retrasarle: para eso está el plazo duro.
"""
import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

# Las ÚNICAS etiquetas de intención que entiende el TTS. Se filtra en vez de confiar en
# que el modelo obedezca, porque medido el 2026-09-12 se las inventa: soltó
# "[dar un respiro]", "[browsing]" y hasta un "[miejamencioso]", que no es ni una palabra.
# Una etiqueta que el motor no conoce se LEE EN ALTO tal cual, así que esto no es
# cosmético: es la diferencia entre una coletilla y Jarvis diciendo "corchete browsing".
ETIQUETAS_OK = {"curious", "sarcastic", "mischievously", "laughs", "sighs", "excited"}
_ETIQUETA = re.compile(r"\[([^\]]{1,30})\]")

BASE_URL = os.environ.get("GROQ_URL", "https://api.groq.com/openai/v1").rstrip("/")
API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
MODELO = os.environ.get("GROQ_MODELO", "").strip()
# Plazo duro. Si no llega a tiempo NO sirve de nada, porque la muletilla existe justo para
# tapar un silencio: una que llega tarde es el silencio más la muletilla.
TIMEOUT_S = float(os.environ.get("GROQ_TIMEOUT_MS", "1200")) / 1000

# Corto a propósito. El límite de Groq es de TOKENS DE ENTRADA por minuto (7000 en el plan
# gratis), no de peticiones: cada palabra de aquí se paga en cada llamada y recorta cuántas
# caben. Medido el 2026-09-12: con ~500 tokens por llamada, 14 seguidas agotan el minuto.
_SISTEMA = """\
Eres Jarvis. Solo haces una cosa: soltar la frase de relleno que se dice mientras se
piensa la respuesta de verdad. Ganas tiempo, no contestas.

- UNA frase, menos de doce palabras. Español, tuteando, con confianza y retintín.
- Menciona de refilón lo que él acaba de decir: es tu única ventaja sobre una frase de bote.
- NO des datos ni números: aún no sabes la respuesta.
- NO preguntes nada: se pondría a contestarte encima de la respuesta real.
- Si habla de dolor, lesión o de estar jodido: sobrio, sin bromas y sin etiqueta.
- Puedes abrir con UNA de estas seis etiquetas, tal cual: [curious] [sarcastic]
  [mischievously] [laughs] [sighs] [excited]. Ninguna otra. Si dudas, ninguna.
- Nunca devuelvas solo la etiqueta: siempre tiene que haber frase.

Ej.: "¿qué tal he dormido?" -> Déjame mirar tus noches, que prometen poco.
"""


def disponible() -> bool:
    """¿Está configurado? Sin clave o sin modelo, ni se intenta."""
    return bool(API_KEY and MODELO)


def muletilla(mensaje: str) -> str | None:
    """Escribe la coletilla para lo que Hugo acaba de decir. `None` si no se puede.

    `None` no es un error que haya que tratar: significa "tira de las pregrabadas", que es
    el comportamiento de siempre y suena bien. Por eso aquí no se propaga nada.
    """
    if not disponible():
        return None
    mensaje = (mensaje or "").strip()
    if not mensaje:
        return None

    t0 = time.monotonic()
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": MODELO,
                # Corto de verdad: es una frase. Además acota el gasto y el tiempo.
                "max_tokens": 40,
                # Alta a propósito: si suena siempre igual, no mejora en nada al bote de
                # frases pregrabadas, que encima tiene mejor voz.
                "temperature": 1.0,
                "messages": [
                    {"role": "system", "content": _SISTEMA},
                    {"role": "user", "content": mensaje},
                ],
            },
            timeout=TIMEOUT_S,
        )
        if r.status_code != 200:
            log.warning("muletilla rápida: HTTP %s — %s", r.status_code, r.text[:200])
            return None
        texto = (r.json()["choices"][0]["message"]["content"] or "").strip()
    except requests.Timeout:
        log.info("muletilla rápida: no llegó en %.0f ms, tiro de las pregrabadas",
                 TIMEOUT_S * 1000)
        return None
    except Exception as e:
        log.warning("muletilla rápida falló (%s: %s); tiro de las pregrabadas",
                    type(e).__name__, e)
        return None

    # Fuera el razonamiento. Muchos modelos pequeños de hoy piensan en voz alta y lo
    # sueltan DENTRO del contenido: medido el 2026-09-12, `qwen/qwen3.6-27b` devolvía
    # "<think>\nHere's a thinking process..." en inglés. Va antes que nada, porque si no
    # lo primero que se leería en alto sería su monólogo interior.
    if "<think>" in texto:
        fin = texto.find("</think>")
        texto = texto[fin + len("</think>"):] if fin != -1 else ""

    # Los modelos pequeños se emocionan: comillas, varias frases, o un párrafo. Se recorta
    # en vez de descartarse, porque una frase de más no estropea nada y quedarse sin
    # muletilla sí deja el silencio que esto viene a tapar.
    texto = texto.strip().strip('"').strip("'").split("\n")[0].strip()

    # Solo sobreviven las etiquetas que el TTS conoce; las inventadas se borran.
    # Se NORMALIZAN además de filtrarse: devolvió "[ sighs ]" con espacios dentro
    # (2026-09-12), que pasa el filtro pero el motor de voz no reconoce y acabaría
    # leyéndose. Sale siempre en la forma canónica "[sighs]".
    def _limpiar(m):
        nombre = m.group(1).strip().lower()
        return f"[{nombre}]" if nombre in ETIQUETAS_OK else ""

    texto = _ETIQUETA.sub(_limpiar, texto).strip()
    texto = re.sub(r"\s{2,}", " ", texto)

    # A veces devuelve SOLO la etiqueta ("[sarcastic]") y ni una palabra — visto el
    # 2026-09-12. Eso no es una muletilla: o no suena nada, o el TTS lee "sarcastic".
    # Mejor ninguna y que entre una pregrabada.
    if not _ETIQUETA.sub("", texto).strip():
        log.info("muletilla rápida: solo etiqueta y sin texto, la descarto")
        return None
    if len(texto) > 120:
        corte = texto[:120]
        punto = max(corte.rfind("."), corte.rfind("!"), corte.rfind("?"))
        texto = corte[: punto + 1] if punto > 30 else corte.rsplit(" ", 1)[0] + "…"
    if not texto:
        return None

    log.info("muletilla rápida en %.0f ms: %r", (time.monotonic() - t0) * 1000, texto)
    return texto
