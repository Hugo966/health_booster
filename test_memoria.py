#!/usr/bin/env python3
"""Comprobaciones de la conciencia del tiempo.  `./venv/bin/python test_memoria.py`

Contra una base TEMPORAL: `jarvis.db` son sus conversaciones privadas y no se ensucia
con mensajes inventados (HANDOFF §15).

Lo que se vigila es cuándo Jarvis debe decir "llevas una semana sin pasar". Equivocarse
aquí no da error: o le saluda como si acabara de hablar con él después de un mes, o le
suelta lo de la ausencia cada mensaje del mismo día.
"""
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "dashboard" / "backend"))
import memoria

memoria.DB = Path(tempfile.mkdtemp()) / "prueba.db"
memoria.init()

HOY = "hugo-2026-11-11"


def apuntar(sesion, rol, hace_dias, hora="10:00"):
    f = (datetime.now() - timedelta(days=hace_dias)).date().isoformat()
    with memoria._conn() as con:
        con.execute("INSERT INTO conversaciones (sesion, ts, rol, texto) VALUES (?,?,?,?)",
                    (sesion, f"{f}T{hora}:00", rol, "lo que fuera"))


# --- sin historial, no hay ausencia que contar -------------------------------
assert memoria.ultima_visita(HOY) is None

# --- habló hace 7 días: eso es lo que hay que saber --------------------------
apuntar("hugo-2026-11-04", "usuario", 7)
v = memoria.ultima_visita(HOY)
assert v and v["dias"] == 7, v

# --- lo de HOY no cuenta como visita anterior --------------------------------
# La sesión es diaria: lo de hoy ya lo tiene delante en el hilo, y contarlo haría que
# "hace 7 días" pasara a ser "hace 0" en cuanto dijera "hola".
apuntar(HOY, "usuario", 0)
assert memoria.ultima_visita(HOY)["dias"] == 7

# --- que hablara JARVIS no es que pasara él ----------------------------------
# Si contara, un mensaje suelto suyo borraría la ausencia sin que el usuario volviera.
apuntar("hugo-2026-11-10", "jarvis", 1)
assert memoria.ultima_visita(HOY)["dias"] == 7

# --- y cuando vuelve de verdad, manda lo último ------------------------------
apuntar("hugo-2026-11-10", "usuario", 1)
assert memoria.ultima_visita(HOY)["dias"] == 1

# --- la frase del parte -------------------------------------------------------
import briefing

assert "ayer" in briefing._linea_ultima_visita(HOY)
# Otra sesión del MISMO día no es una ausencia: no se menciona.
memoria.DB = Path(tempfile.mkdtemp()) / "otra.db"
memoria.init()
apuntar("hugo-otra", "usuario", 0)
assert briefing._linea_ultima_visita(HOY) is None
# Y sin sesión (el parte por línea de comandos) tampoco se inventa nada.
assert briefing._linea_ultima_visita(None) is None

print("OK")
