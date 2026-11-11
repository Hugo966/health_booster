"""El tiempo donde esté el usuario, para que Jarvis no hable del día a ciegas.

Open-Meteo: gratis y **sin clave**, así que quien clone esto no tiene que registrarse en
ningún sitio. A cambio no hay acuerdo de servicio: si falla o tarda, esto devuelve `None`
y el parte de estado sale sin la línea del tiempo. Nunca puede tumbar el parte — Jarvis
sin saber si llueve sigue sirviendo; Jarvis mudo, no.

Lo único que sale hacia fuera son unas coordenadas. Ni nombre, ni correo, ni nada de sus
datos de salud.
"""
import logging
import time

import requests

import ajustes

log = logging.getLogger(__name__)

URL = "https://api.open-meteo.com/v1/forecast"
# Nominatim (OpenStreetMap) y no el geocodificador de Open-Meteo porque ese solo entiende
# NOMBRES de sitio: este traga dirección, ciudad y código postal con la misma consulta,
# que es como la gente escribe dónde vive. Su política pide identificar al cliente y no
# pasar de una petición por segundo; lo primero se cumple con el nombre de la app (no con
# datos de nadie), y lo segundo sobra: esto se usa UNA vez.
URL_LUGARES = "https://nominatim.openstreetmap.org/search"
CABECERAS = {"User-Agent": "jarvis-health-dashboard/1.0"}
# El tiempo no cambia en dos minutos y el parte se monta en CADA mensaje: sin caché, cada
# "hola" se iría medio segundo a pedirlo. 20 min es más fino que el dato real.
TTL_S = 20 * 60
TIMEOUT_S = 6

# Códigos WMO. Solo los que se dan de verdad en una ciudad; el resto cae en "raro".
_CIELO = {
    0: "despejado", 1: "casi despejado", 2: "nubes y claros", 3: "nublado",
    45: "niebla", 48: "niebla helada",
    51: "llovizna floja", 53: "llovizna", 55: "llovizna fuerte",
    61: "lluvia floja", 63: "lluvia", 65: "lluvia fuerte",
    66: "lluvia helada", 67: "lluvia helada fuerte",
    71: "nieve floja", 73: "nieve", 75: "nieve fuerte", 77: "aguanieve",
    80: "chubascos", 81: "chubascos fuertes", 82: "chubascos muy fuertes",
    85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta con granizo fuerte",
}

_cache = {"ts": 0.0, "datos": None, "clave": None}


def buscar_lugar(texto: str) -> dict | None:
    """Dirección, ciudad o código postal -> {nombre, lat, lon}. `None` si no sale nada.

    Da igual cómo lo escriba: "Madrid", "28001" y "Calle de Alcalá 1, Madrid" valen las
    tres.

    Devuelve DOS nombres. `nombre` es la etiqueta corta (ciudad y país) y es la que se
    enseña: el parte de estado diría su calle en cada mensaje si fuera la larga.
    `direccion` es la dirección completa tal como la resuelve el buscador, que es la que
    sirve para lo que no es el tiempo (decirle cuánto tarda en llegar a algún sitio, por
    ejemplo). Las dos se guardan; cada consumidor coge la que necesita.
    """
    try:
        r = requests.get(URL_LUGARES, timeout=TIMEOUT_S, headers=CABECERAS,
                         params={"q": texto, "format": "jsonv2", "limit": 1,
                                 "addressdetails": 1})
        res = r.json() or []
    except Exception as e:
        log.warning("no pude buscar el sitio: %s", e)
        return None
    if not res:
        return None
    sitio = res[0]
    d = sitio.get("address", {})
    # De lo más concreto a lo menos: un código postal rural puede no tener "city".
    ciudad = next((d[k] for k in ("city", "town", "village", "municipality", "county",
                                  "state") if d.get(k)), None)
    pais = (d.get("country_code") or "").upper()
    etiqueta = ", ".join(x for x in (ciudad, pais) if x) or texto.strip()
    return {"nombre": etiqueta,
            "direccion": sitio.get("display_name") or texto.strip(),
            "lat": float(sitio["lat"]), "lon": float(sitio["lon"])}


# La última ubicación que se leyó bien. Si la hoja no contesta —la cuota de Google se
# agota más de lo que parece— se sirve esta: sin ella, un 429 pasajero le volvería a
# preguntar al usuario en qué ciudad vive, que es de las cosas que más cara de tonto te
# dejan en una app.
_ultima_ubicacion = None


def ubicacion() -> dict | None:
    """Lo que contestó el usuario la primera vez que abrió la app.

    No propaga NUNCA un fallo de la hoja: esto lo llaman el parte de estado y la portada
    del dashboard, y quedarse sin saber el tiempo no puede tumbar ninguno de los dos.
    """
    global _ultima_ubicacion
    try:
        lat, lon = ajustes.leer("meteo_lat"), ajustes.leer("meteo_lon")
        if not lat or not lon:
            return None
        _ultima_ubicacion = {"nombre": ajustes.leer("meteo_lugar", ""),
                             "direccion": ajustes.leer("meteo_direccion", ""),
                             "lat": float(lat), "lon": float(lon)}
    except Exception as e:
        log.warning("no pude leer la ubicación (%s: %s)", type(e).__name__, e)
    return _ultima_ubicacion


def guardar_ubicacion(lugar: dict) -> None:
    ajustes.escribir({"meteo_lugar": str(lugar["nombre"]),
                      "meteo_direccion": str(lugar.get("direccion") or lugar["nombre"]),
                      "meteo_lat": str(lugar["lat"]),
                      "meteo_lon": str(lugar["lon"])})
    global _ultima_ubicacion
    _ultima_ubicacion = dict(lugar)
    _cache.update(ts=0.0, datos=None, clave=None)   # la caché era de otro sitio


def ahora() -> dict | None:
    """El tiempo de ahora y el resto del día. `None` si no hay ubicación o si falla."""
    sitio = ubicacion()
    if not sitio:
        return None
    clave = (sitio["lat"], sitio["lon"])
    if _cache["datos"] and _cache["clave"] == clave and time.time() - _cache["ts"] < TTL_S:
        return _cache["datos"]
    try:
        d = requests.get(URL, timeout=TIMEOUT_S, params={
            "latitude": sitio["lat"], "longitude": sitio["lon"],
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 1,
        }).json()
        act, dia = d["current"], d["daily"]
        datos = {
            "lugar": sitio["nombre"],
            "temp": round(act["temperature_2m"]),
            "sensacion": round(act["apparent_temperature"]),
            "cielo": _CIELO.get(act["weather_code"], "raro"),
            "maxima": round(dia["temperature_2m_max"][0]),
            "minima": round(dia["temperature_2m_min"][0]),
            "lluvia": dia["precipitation_probability_max"][0],
        }
    except Exception as e:
        # Se devuelve lo último bueno si lo hay: un tiempo de hace una hora es mucho más
        # útil que ninguno, y esto no decide nada, solo se cuenta.
        log.warning("no pude leer el tiempo: %s", e)
        return _cache["datos"]
    _cache.update(ts=time.time(), datos=datos, clave=clave)
    return datos


def frase() -> str | None:
    """Una línea para el parte de estado. `None` si no hay nada que contar."""
    d = ahora()
    if not d:
        return None
    texto = (f"- Tiempo en {d['lugar']}: {d['cielo']}, {d['temp']}°"
             + (f" (sensación {d['sensacion']}°)" if abs(d['sensacion'] - d['temp']) >= 2 else "")
             + f" · hoy {d['minima']}° a {d['maxima']}°")
    # La probabilidad solo se dice cuando significa algo: un 10% es ruido.
    if d["lluvia"] is not None and d["lluvia"] >= 30:
        texto += f" · {d['lluvia']}% de lluvia"
    return texto
