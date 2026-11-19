#!/usr/bin/env python3
"""Comprobaciones del guardado de formularios.  `./venv/bin/python test_formularios.py`

Se prueba contra una pestaña FALSA, no contra la hoja del usuario: probar esto con la hoja de
verdad ya le escribió una vez una fila inventada en sus datos de salud (HANDOFF §0).

Lo que se vigila aquí es la diferencia entre "no he contestado" y "quítalo", que por el
cable son la misma cadena vacía. Si se confunden, abrir el formulario y darle a Guardar
borraría todo lo que no hubiera rellenado ese día.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "dashboard" / "backend"))
import formularios as f


class HojaFalsa:
    """Lo justo de una worksheet de gspread para que `guardar` crea que escribe."""

    def __init__(self, cabeceras, filas):
        self.cabeceras = cabeceras
        self.filas = filas          # [[valores...]], sin la cabecera
        self.escrito = {}           # celda -> valor
        self.anadidas = []

    def row_values(self, n):
        return self.cabeceras if n == 1 else self.filas[n - 2]

    def col_values(self, n):
        return [self.cabeceras[n - 1]] + [fila[n - 1] for fila in self.filas]

    def batch_update(self, cambios, value_input_option=None):
        for c in cambios:
            self.escrito[c["range"]] = c["values"][0][0]

    def append_row(self, valores, **kw):
        self.filas.append(valores)
        return {"updates": {"updatedRange": f"x!A{len(self.filas) + 1}"}}


def montar(valores_del_dia):
    """Una PM con una fila del 2026-11-10 ya rellena."""
    cab = ["fecha", "energia", "sensacion_global", "rpd_sesion", "notas_pm"]
    hoja = HojaFalsa(cab, [["2026-11-10"] + [valores_del_dia.get(c, "") for c in cab[1:]]])
    f._hoja = lambda tipo: hoja
    f.leer = lambda tipo, fecha: {}
    f.sheets.invalidar = lambda tab=None: None
    return hoja


# --- un campo vacío NO borra lo que ya había ---------------------------------
# Es lo que permite corregir un solo número sin reenviar el día entero.
hoja = montar({"energia": 8, "rpd_sesion": 7})
f.guardar("pm", "2026-11-10", {"energia": 6, "sensacion_global": ""})
assert hoja.escrito == {"B2": 6}, hoja.escrito

# --- `borrar` sí vacía, y solo lo nombrado -----------------------------------
# El caso del usuario: metió el RPE de un día que no entrenó. Un 0 no vale, porque un 0 es
# un entreno que existió y salió fatal.
hoja = montar({"energia": 8, "rpd_sesion": 7})
f.guardar("pm", "2026-11-10", {}, borrar=["rpd_sesion"])
assert hoja.escrito == {"D2": ""}, hoja.escrito

# --- borrar y corregir en el mismo guardado ----------------------------------
hoja = montar({"energia": 8, "rpd_sesion": 7})
f.guardar("pm", "2026-11-10", {"energia": 5}, borrar=["rpd_sesion"])
assert hoja.escrito == {"B2": 5, "D2": ""}, hoja.escrito

# --- un campo no puede venir en los dos sitios -------------------------------
# Gana el borrado: si pidió quitarlo, quitarlo es lo que quiere. Pero entonces NO se puede
# devolver que se guardó su valor: eso le hizo a Jarvis jurar que el RPE del 10/11 estaba
# puesto mientras la celda quedaba vacía y el panel lo reclamaba (2026-11-11).
hoja = montar({"rpd_sesion": 7})
res = f.guardar("pm", "2026-11-10", {"rpd_sesion": 9}, borrar=["rpd_sesion"])
assert hoja.escrito == {"D2": ""}, hoja.escrito
assert "rpd_sesion" not in res["guardado"], res["guardado"]
assert any("rpd_sesion" in a for a in res["avisos"]), res["avisos"]

# --- borrar un campo que no existe es un error, no un silencio ---------------
hoja = montar({})
try:
    f.guardar("pm", "2026-11-10", {}, borrar=["rpe_de_la_vida"])
    raise SystemExit("tenía que haber fallado")
except ValueError as e:
    assert "rpe_de_la_vida" in str(e)
assert hoja.escrito == {}

# --- sin valores y sin borrados, no se escribe nada --------------------------
hoja = montar({})
try:
    f.guardar("pm", "2026-11-10", {})
    raise SystemExit("tenía que haber fallado")
except ValueError:
    pass
assert hoja.escrito == {}

# --- un día que no existe no se crea para borrarlo ---------------------------
# Crear una fila vacía sería inventarse justo el día que se quiere quitar de en medio.
hoja = montar({})
f.guardar("pm", "2026-11-09", {}, borrar=["rpd_sesion"])
assert hoja.escrito == {} and len(hoja.filas) == 1, (hoja.escrito, hoja.filas)

# --- lo que ve JARVIS de un campo borrado ------------------------------------
# Vive aquí y no en un fichero aparte porque es la otra mitad del borrado: no basta con
# vaciar la celda si la herramienta que lee el día sigue cantando el valor viejo.
# `derived_diario` solo lo regenera el pipeline (cada hora), así que justo después de
# borrar algo el derivado está caducado. El 2026-11-11 eso hizo que `dia` contestara
# rpd_sesion 7 del día 10 con la celda ya vacía: Jarvis le discutía al panel un dato que
# el propio usuario acababa de quitar.
import chat  # noqa: E402

chat.fetch_all = lambda *a, **kw: {
    # el derivado, con el valor de antes del borrado
    "derived_diario": [{"fecha": "2026-11-10", "rpd_sesion": 7, "readiness": 71,
                        "energia": 8}],
    "wellness_am": [],
    # el origen, ya vaciado por el borrado de arriba
    "wellness_pm": [{"fecha": "2026-11-10", "energia": 8, "sensacion_global": 7,
                     "rpd_sesion": ""}],
    "peso": [],
    "entreno_sets": [],
}
d = chat._tool_dia("2026-11-10")["datos"]
assert "rpd_sesion" not in d, d          # vaciado: el derivado NO puede resucitarlo
assert d["energia"] == 8, d              # y lo que sí está sigue estando

# Sin fila de PM ese día no se afirma nada: el derivado es lo único que hay y se respeta.
chat.fetch_all = lambda *a, **kw: {
    "derived_diario": [{"fecha": "2026-11-10", "rpd_sesion": 7}],
    "wellness_am": [{"fecha": "2026-11-10", "sueno_calidad": 6}],
    "wellness_pm": [], "peso": [], "entreno_sets": [],
}
assert chat._tool_dia("2026-11-10")["datos"]["rpd_sesion"] == 7

print("OK")

# --- La precarga del dolor: lo del keep sale ya escrito en el form PM -------------------
f.sheets.fetch_all = lambda *a, **kw: {"entreno_sesion": [
    {"fecha": "2026-11-18", "dolor_sesion_keep": "Molestia en el codo en press"},
    {"fecha": "2026-11-17", "dolor_sesion_keep": ""},
]}
assert f.precarga("pm", "2026-11-18", {}) == {
    "dolor_sesion_nota": "Molestia en el codo en press"}
# El form manda sobre el keep: si ya escribió algo ahí, no se pisa.
assert f.precarga("pm", "2026-11-18", {"dolor_sesion_nota": "ya lo puse yo"}) == {}
assert f.precarga("pm", "2026-11-17", {}) == {}   # entrenó, pero sin dolores
assert f.precarga("pm", "2026-11-16", {}) == {}   # no entrenó: no hay fila
assert f.precarga("am", "2026-11-18", {}) == {}   # el AM no tiene ese campo

print("OK precarga")
