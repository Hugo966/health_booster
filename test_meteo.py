"""Prueba de la ventana de previsión: que lo que mira son las horas que VIENEN.

Sin red: `_ventana` es pura y se le da el horario a mano. Lo que se protege es que a las
ocho de la tarde no cuente la madrugada de hoy —que ya pasó— y que a las once de la
noche siga mirando hacia delante aunque eso sea mañana.
"""
import sys

sys.path.insert(0, "dashboard/backend")
import meteo


def _horario(desde_h: int, n: int, temps, lluvias=None, dia="2026-11-16"):
    """n horas seguidas desde `desde_h`, cruzando a mañana si hace falta."""
    tiempos, d2 = [], "2026-11-17"
    for i in range(n):
        h = desde_h + i
        tiempos.append(f"{dia if h < 24 else d2}T{h % 24:02d}:00")
    return {"time": tiempos, "temperature_2m": temps,
            "precipitation_probability": lluvias or [0] * n}


def main():
    # Son las 20:10. La madrugada (6°) ya pasó: no puede salir en la ventana.
    h = _horario(0, 30, [6] * 20 + [19, 17, 15, 13, 12, 11, 10, 9, 8, 7])
    v = meteo._ventana(h, "2026-11-16T20:10")
    assert v == {"min": 10, "max": 17, "lluvia": 0, "hasta": "02:00"}, v

    # A las 23:00 la ventana cruza la medianoche: por eso se piden DOS días.
    v = meteo._ventana(h, "2026-11-16T23:00")
    assert v["hasta"] == "05:00" and v["max"] == 12, v

    # La lluvia es la peor de la ventana, no la media: 0,0,70,0 -> 70.
    h = _horario(10, 4, [15, 16, 16, 15], [0, 0, 70, 0])
    v = meteo._ventana(h, "2026-11-16T09:30", horas=4)
    assert v["lluvia"] == 70, v

    # Sin datos no se inventa nada (y el parte sale sin el tramo, no roto).
    assert meteo._ventana({}, "2026-11-16T20:00") is None
    assert meteo._ventana(_horario(0, 3, [5, 5, 5]), "2026-11-16T23:00") is None

    # Huecos sueltos del servicio: se saltan, no tumban la ventana.
    h = _horario(10, 4, [15, None, 16, 15], [None, None, None, None])
    v = meteo._ventana(h, "2026-11-16T09:30", horas=4)
    assert v == {"min": 15, "max": 16, "lluvia": None, "hasta": "13:00"}, v

    print("ok — 6 casos")


if __name__ == "__main__":
    main()
