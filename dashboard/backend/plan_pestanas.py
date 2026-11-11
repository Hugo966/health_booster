"""Las pestañas del plan que el pipeline no supo enrutar, y la respuesta de Hugo.

El entrenador bautiza la pestaña como le sale. Cuando el nombre acaba en el número de la
semana, `entreno_pipeline.rutas_automaticas` la resuelve sola. Cuando NO acaba en número
("Peaking final") no hay nada que deducir: la semana decide a qué sesión van los nombres
de los ejercicios, y equivocarse ahí le pone a las series el nombre de otro día.

Así que el pipeline apunta la pestaña aquí a medias —el nombre, sin números— y Jarvis se
lo pregunta a Hugo. Lo que conteste lo lee el pipeline a la hora siguiente: ni código, ni
despliegue, ni esperar a una sesión de Claude.
"""
import os
import sys
from pathlib import Path

import formularios
import sheets

# El parser del plan vive en la raíz, no aquí: se mete en `sys.path` de forma explícita y
# no confiando en que otro módulo lo haya hecho antes (ya pasó con `briefing.py`, y el
# fallo se tragaba un `except` ancho).
_RAIZ = str(Path(__file__).resolve().parents[2])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import entreno_pipeline  # noqa: E402

PESTANA = "plan_pestanas"

# Las tres ruedas con las que se contesta desde el panel. Los rangos se declaran AQUÍ y
# no en el frontend, por lo mismo que los de los formularios: duplicarlos es justo como
# se acaba ofreciendo un tope que no es, y sin que nadie se entere.
CAMPOS = [
    formularios.Campo("plani", "P", "entero", 1, 9, paso=1),
    formularios.Campo("bloque", "B", "entero", 1, 12, paso=1),
    formularios.Campo("semana", "S", "entero", 1, 20, paso=1),
]


def sugerencia() -> dict:
    """Dónde arrancan las ruedas: la semana SIGUIENTE a la que acaba de entrenar.

    Sale de `entreno_sesion` —o sea, de los números que escribe Hugo en su keep—, no del
    nombre de la pestaña, que es precisamente lo que no se ha podido leer. Una pestaña
    nueva suele ser la semana que viene del bloque en curso, así que casi siempre es
    entrar, mirar que cuadra y darle a Guardar.
    """
    filas = [f for f in sheets.fetch_all().get("entreno_sesion", [])
             if str(f.get("fecha", "")).strip()]
    if not filas:
        return {"plani": 1, "bloque": 1, "semana": 1}
    ultima = max(filas, key=lambda f: str(f["fecha"])[:10])

    def _n(v, defecto):
        try:
            return int(v)
        except (TypeError, ValueError):
            return defecto

    return {"plani": _n(ultima.get("plani"), 1),
            "bloque": _n(ultima.get("bloque"), 1),
            "semana": _n(ultima.get("semana"), 0) + 1}


def pendientes() -> list[str]:
    """Las pestañas apuntadas que todavía no tienen respuesta."""
    filas = sheets.fetch_all().get(PESTANA, [])
    return [str(f["pestana"]).strip() for f in filas
            if str(f.get("pestana", "")).strip()
            and not str(f.get("semana", "")).strip()]


def resolver(pestana: str, plani: int, bloque: int, semana: int) -> str:
    """Guarda lo que ha contestado Hugo. Devuelve la frase de confirmación.

    Solo completa filas que el pipeline haya apuntado: si Jarvis se inventara el nombre
    de una pestaña, la fila nueva no casaría con ninguna de Drive y el plan de esa semana
    seguiría sin aparecer, pero sin que nadie lo notara.
    """
    objetivo = str(pestana).strip().lower()
    hoja = formularios.cliente().open_by_key(os.environ["SHEET_ID"])
    ws = hoja.worksheet(PESTANA)
    columna = ws.col_values(1)
    fila = next((i for i, v in enumerate(columna[1:], start=2)
                 if str(v).strip().lower() == objetivo), None)
    if fila is None:
        apuntadas = ", ".join(pendientes()) or "ninguna"
        raise ValueError(f"'{pestana}' no está apuntada como pendiente. Las que hay: {apuntadas}.")

    cabeceras = ws.row_values(1)
    valores = {"plani": int(plani), "bloque": int(bloque), "semana": int(semana)}
    ws.batch_update([{"range": _a1(fila, cabeceras.index(c) + 1), "values": [[v]]}
                     for c, v in valores.items() if c in cabeceras],
                    value_input_option="USER_ENTERED")
    sheets.invalidar(PESTANA)
    return (f"'{pestana}' queda como plan {plani}, bloque {bloque}, semana {semana}. "
            "El pipeline la coge en la próxima pasada.")


def resolver_codigo(pestana: str, codigo: str) -> str:
    """Igual que `resolver`, pero con el código que Hugo escribe de un tirón: `P2B4S3`.

    Lo parsea `entreno_pipeline.route_tab`, que ya entiende ese formato —se enrutó en su
    día pensando justo en esto—, así que el panel no inventa su propia sintaxis. De
    regalo acepta también el nombre canónico ("Build II S3"), que lleva los mismos tres
    números dentro.
    """
    ruta = entreno_pipeline.route_tab(str(codigo).strip())
    if not ruta:
        raise ValueError(f"'{codigo}' no vale. Escríbelo como P2B4S3: plan 2, bloque 4, "
                         "semana 3.")
    plani, bloque, semana = ruta
    return resolver(pestana, plani, bloque, int(semana))


def _a1(fila: int, col: int) -> str:
    letras = ""
    while col:
        col, resto = divmod(col - 1, 26)
        letras = chr(65 + resto) + letras
    return f"{letras}{fila}"


if __name__ == "__main__":   # comprobación sin tocar la hoja
    assert _a1(2, 1) == "A2" and _a1(10, 4) == "D10" and _a1(1, 27) == "AA1"
    print("OK")
