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
URL_CIUDADES = "https://geocoding-api.open-meteo.com/v1/search"
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


def buscar_ciudad(nombre: str) -> dict | None:
    """Nombre de ciudad -> {nombre, lat, lon}. `None` si no se encuentra."""
    try:
        r = requests.get(URL_CIUDADES, timeout=TIMEOUT_S,
                         params={"name": nombre, "count": 1, "language": "es"})
        res = (r.json() or {}).get("results") or []
    except Exception as e:
        log.warning("geocoding falló: %s", e)
        return None
    if not res:
        return None
    c = res[0]
    # El país ayuda a distinguir las muchas ciudades que comparten nombre.
    etiqueta = ", ".join(x for x in (c.get("name"), c.get("country_code")) if x)
    return {"nombre": etiqueta, "lat": c["latitude"], "lon": c["longitude"]}


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
                             "lat": float(lat), "lon": float(lon)}
    except Exception as e:
        log.warning("no pude leer la ubicación (%s: %s)", type(e).__name__, e)
    return _ultima_ubicacion


def guardar_ubicacion(lugar: dict) -> None:
    ajustes.escribir({"meteo_lugar": str(lugar["nombre"]),
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
