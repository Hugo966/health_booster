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
# Plazo duro. El tope de verdad lo marca `ESPERA_MULETILLA_MS` de `voz.ts` (4,5 s): pasado
# eso el navegador ya no la diría, así que llegar más tarde no sirve de nada.
# Estuvo en 1200 ms y era un apretón sin motivo —heredado de cuando esto se pedía en línea
# y sí bloqueaba—; con ese plazo se descartaba 2 de cada 5 respuestas de un modelo que
# escribe mejor. Ahora va en su propio hilo y no le quita tiempo a nadie.
TIMEOUT_S = float(os.environ.get("GROQ_TIMEOUT_MS", "3000")) / 1000
# `reasoning_effort` para los modelos que RAZONAN (los gpt-oss). Vacío = no se manda, que
# es lo que necesitan los que no razonan: mandárselo da error.
#
# Sin esto, un modelo de razonamiento se gasta todo el presupuesto pensando y devuelve
# contenido VACÍO. El 2026-09-12 se descartaron los gpt-oss por eso, dando por hecho que
# no servían; era culpa de pedirles 40 tokens. Con `low` y sitio suficiente,
# `openai/gpt-oss-120b` contesta en ~720 ms y escribe bastante mejor que las alternativas.
ESFUERZO = os.environ.get("GROQ_ESFUERZO", "").strip()
# Holgado a propósito. No encarece ni ralentiza —el modelo para cuando termina— y es lo que
# deja sitio al razonamiento de los gpt-oss. La respuesta se recorta luego de todas formas.
MAX_TOKENS = 300

# Corto a propósito. El límite de Groq es de TOKENS DE ENTRADA por minuto (7000 en el plan
# gratis), no de peticiones: cada palabra de aquí se paga en cada llamada y recorta cuántas
# caben. Medido el 2026-09-12: con ~500 tokens por llamada, 14 seguidas agotan el minuto.
# Los EJEMPLOS son la parte que de verdad hace el trabajo. Están copiados de las
# muletillas pregrabadas de `dashboard/tts/servidor_voz.py`, que las escribió Hugo a mano
# y son literalmente el tono que quiere. Describir un tono con adjetivos ("con retintín")
# no le sirve a un modelo pequeño: se lo inventa. Enseñárselo, sí.
# Si algún día se retoca el personaje, estos ejemplos hay que retocarlos con él.
_SISTEMA = """\
Eres Jarvis, el asistente de Hugo: su colega, con confianza y sarcasmo. Aquí solo haces
UNA cosa: soltar la frase que se dice mientras se piensa la respuesta de verdad. Ganas
tiempo, no contestas.

Así habla Jarvis cuando gana tiempo. **Son ejemplos del TONO, no un menú**: no repitas
ninguno tal cual, porque esas frases exactas ya existen grabadas con mejor voz y copiarlas
no aporta nada. Tu única razón de ser es mencionar lo que él acaba de decir.
  "Déjame que mire eso un segundo, que tus datos y yo tenemos una relación complicada."
  "A ver qué tenemos por aquí… dame un momento, que estoy rebuscando entre tus números."
  "Espera, que lo estoy mirando. No te muevas, que esto tarda menos de lo que parece."
  "Dame un segundo, que estoy cruzando datos como un poseso."
  "Espera que lo compruebo, no vaya a inventarme algo y luego me la líes."
  "Un momento, que no quiero decirte una burrada sin mirarlo."

Reglas:
- UNA frase, menos de quince palabras. Español de España, tuteando.
- Menciona de refilón lo que acaba de decir: es tu única ventaja sobre una frase de bote.
- NO des datos ni números: aún no sabes la respuesta.
- NO preguntes nada: se pondría a contestarte encima de la respuesta real.
- Si habla de dolor, lesión o de estar jodido: sobrio, sin bromas y sin etiqueta.
- Puedes abrir con UNA de estas seis etiquetas, tal cual: [curious] [sarcastic]
  [mischievously] [laughs] [sighs] [excited]. Ninguna otra. Si dudas, ninguna.
- Nunca devuelvas solo la etiqueta: siempre tiene que haber frase.
- Nada de traducciones raras ni de palabras que no existan: si no te sale natural en
  español, di algo simple.
"""


def disponible() -> bool:
    """¿Está configurado? Sin clave o sin modelo, ni se intenta."""
    return bool(API_KEY and MODELO)


def _normalizar(s: str) -> str:
    """Para comparar frases: sin etiquetas, sin puntuación, sin mayúsculas."""
    s = _ETIQUETA.sub("", s).lower()
    return re.sub(r"[^\wáéíóúüñ ]+", "", s, flags=re.UNICODE).strip()


# Los ejemplos del prompt, ya normalizados, para detectar copias literales.
_EJEMPLOS = [
    _normalizar(l.strip().strip('"'))
    for l in _SISTEMA.splitlines()
    if l.startswith('  "')
]


def _es_copia_de_ejemplo(texto: str) -> bool:
    """¿Es esto uno de los ejemplos, tal cual o casi?

    Se mira la inclusión en los dos sentidos, no la igualdad: lo típico no es clavarlo,
    es soltar el ejemplo entero y añadirle cuatro palabras. Eso sigue siendo la frase
    pregrabada con una coletilla, y la pregrabada suena mejor.
    """
    t = _normalizar(texto)
    if len(t) < 15:
        return False
    return any(t in ej or ej in t for ej in _EJEMPLOS if ej)


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

    cuerpo = {
        "model": MODELO,
        "max_tokens": MAX_TOKENS,
        # Alta a propósito: si suena siempre igual, no mejora en nada al bote de
        # frases pregrabadas, que encima tiene mejor voz.
        "temperature": 1.0,
        "messages": [
            {"role": "system", "content": _SISTEMA},
            {"role": "user", "content": mensaje},
        ],
    }
    # Solo si está configurado: a un modelo que no razona, mandárselo le da error.
    if ESFUERZO:
        cuerpo["reasoning_effort"] = ESFUERZO

    t0 = time.monotonic()
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}",
                     "Content-Type": "application/json"},
            json=cuerpo,
            timeout=TIMEOUT_S,
        )
        if r.status_code == 404:
            # EL fallo de esta pieza, y pasó: Groq retiró `groq/compound-mini` y durante
            # semanas las muletillas a medida estuvieron apagadas sin que se notara, porque
            # degradar a las pregrabadas no rompe nada. Por eso este caso es ERROR y no
            # warning, y dice qué hacer: no es un problema de red, es que hay que elegir
            # otro modelo (`scratchpad/elegir_modelo.py` los mide con la clave de Hugo).
            log.error(
                "GROQ_MODELO=%r ya no existe en el proveedor. Las muletillas a medida "
                "están APAGADAS (se usan las pregrabadas). Elige otro modelo en el .env. "
                "Respuesta: %s", MODELO, r.text[:200])
            return None
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

    # Si ha copiado un ejemplo tal cual, mejor NO usarla: esa frase exacta existe
    # pregrabada con el modelo de voz caro, con retintín, y sonaría mejor. Devolver None
    # hace justo eso — que suene la pregrabada. Medido el 2026-10-03: 3 de cada 8 salían
    # copiadas literalmente, y cada una era un cambio a peor.
    if _es_copia_de_ejemplo(texto):
        log.info("muletilla rápida: ha copiado un ejemplo, dejo que suene la pregrabada")
        return None

    log.info("muletilla rápida en %.0f ms: %r", (time.monotonic() - t0) * 1000, texto)
    return texto
