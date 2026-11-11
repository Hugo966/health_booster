#!/usr/bin/env python3
"""Comprobaciones de la cafeína del día anterior.  `./venv/bin/python test_cafeina.py`

La cafeína ya solo se apunta el día que se toma (formulario PM). La columna que el panel
de Correlaciones cruza con el sueño —`cafeina_ayer_mg`— se calcula desplazando esa un
día. Si el desplazamiento se hace por FILAS en vez de por fecha, un hueco en los datos le
cuelga el café de un día a la noche de otro y la correlación sale falsa sin dar error.
"""
import pandas as pd
import status_pipeline as sp


def df(filas):
    """filas: (fecha, cafeina_hoy_mg) o (fecha, cafeina_hoy_mg, cafeina_ayer_mg_del_AM)."""
    cols = ["fecha", "cafeina_hoy_mg"] + (["cafeina_ayer_mg"] if len(filas[0]) == 3 else [])
    return pd.DataFrame(filas, columns=cols)


def ayer(filas):
    return list(sp.cafeina_de_ayer(df(filas)))


def vacio(v):
    return v is None or pd.isna(v)


# --- días seguidos: cada noche carga con el café del día anterior -------------
d = ayer([("2026-11-01", 100), ("2026-11-02", 200), ("2026-11-03", 300)])
assert vacio(d[0])                      # del 31/10 no hay nada
assert d[1] == 100 and d[2] == 200

# --- un hueco NO se rellena con el día equivocado -----------------------------
# Lo que mata a `shift(1)`: aquí el café del día 1 no tiene nada que ver con la noche
# del día 4, y colgárselo sería inventarse el dato.
d = ayer([("2026-11-01", 100), ("2026-11-04", 300)])
assert vacio(d[1]), f"el hueco de dos días se rellenó con {d[1]}"

# --- el día SIN cafeína apuntada no contagia al siguiente ---------------------
d = ayer([("2026-11-01", 100), ("2026-11-02", None), ("2026-11-03", 300)])
assert d[1] == 100 and vacio(d[2])

# --- el histórico del AM manda donde no hay PM del día anterior ---------------
# Hasta el 2026-11-11 la cafeína se preguntaba también en el AM ("la de ayer"). Esas
# filas viejas tienen que seguir alimentando la correlación.
d = ayer([("2026-06-01", None, 250), ("2026-06-02", None, 400)])
assert d[0] == 250 and d[1] == 400

# ...pero el PM gana cuando están los dos: es el día en que se la tomó.
d = ayer([("2026-06-01", 100, None), ("2026-06-02", None, 999)])
assert d[1] == 100, f"debería ganar el PM del día anterior, salió {d[1]}"

# --- sin columna del PM (datos antiguos) no revienta --------------------------
sinpm = pd.DataFrame([("2026-06-01", 250)], columns=["fecha", "cafeina_ayer_mg"])
assert list(sp.cafeina_de_ayer(sinpm)) == [250]

print("OK")
