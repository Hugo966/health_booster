#!/usr/bin/env python3
"""Comprobaciones del panorama.  `./venv/bin/python test_panorama.py`

Son cuentas que ya existen en los paneles y se replican en el backend, así que lo que se
vigila es que digan LO MISMO. Una correlación mal calculada no da error: da una frase con
pinta de conclusión sobre su salud.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "dashboard" / "backend"))
import panorama as pa


# --- Pearson: los dos extremos y el caso plano -------------------------------
recta = [(x, 2 * x + 1) for x in range(20)]
assert abs(pa._pearson(recta) - 1.0) < 1e-9
assert abs(pa._pearson([(x, -3 * x) for x in range(20)]) + 1.0) < 1e-9
assert pa._pearson([(x, 7) for x in range(20)]) is None      # sin varianza no hay r

# --- por debajo del mínimo NO se contesta ------------------------------------
# Es el mismo umbral que el panel (14). Con cuatro días cualquier par da r=±1 y eso
# dicho en voz alta suena a hallazgo.
assert pa._pearson(recta[:13]) is None
assert pa._pearson(recta[:14]) is not None

# --- la frase lo dice cuando no hay datos ------------------------------------
dd = [{"sueno_horas_ayer": 7, "sensacion_am": 6}] * 5
linea = pa._correlaciones(dd)[0]
assert "sin datos suficientes" in linea and "5 días" in linea, linea

# --- fuerza: solo lo que entrena AHORA, no el histórico entero ---------------
rm1 = (
    [{"plani": 1, "bloque": 4, "semana": 1, "ejercicio": "Press militar", "mejor_e1rm": 60}]
    + [{"plani": 2, "bloque": 3, "semana": w, "ejercicio": "Banca comp", "mejor_e1rm": 90 + w}
       for w in range(1, 7)]
)
salida = "\n".join(pa._fuerza(rm1))
assert "Banca comp" in salida
assert "Press militar" not in salida, "un accesorio de otro plan no pinta nada aquí"
# Se enseñan las ÚLTIMAS cinco semanas, no las seis.
assert "P2B3S2" in salida and "P2B3S1" not in salida, salida
# Y nunca sin el aviso: un e1RM no es una marca.
assert "ESTIMADO" in salida

print("OK")
