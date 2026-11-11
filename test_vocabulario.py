#!/usr/bin/env python3
"""La batería de nombres de los básicos.  `./venv/bin/python test_vocabulario.py`

Dos cosas que vigilar, y la segunda es la que duele:

1. Que lo que se dice en voz alta encuentre el ejercicio: "squat", "la bp", "sumo
   deadlight" con la falta y todo.
2. Que NUNCA se fundan variantes. Banca competición, banca 3ct y banca mid grip son
   ejercicios distintos: juntarlas da una "mejor marca" que no es de ninguna, y eso no
   da error, solo un número que se cree.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "dashboard" / "backend"))
import vocabulario as v

# Los nombres tal como están en la hoja.
NOMBRES = [
    "Sentadilla low bar", "Sentadilla low bar tacón 2cm", "Sentadilla high bar",
    "Sentadilla búlgara", "Banca comp", "Banca 3ct", "Banca mid grip",
    "Banca larssen mid grip", "Peso muerto sumo", "Peso muerto comp",
    "Peso muerto convencional déficit 2cm", "Curl femoral",
]


def primero(texto):
    lista, como = v.resolver(texto, NOMBRES)
    return (lista[0] if lista else None), como


# --- los tres básicos, como se digan -----------------------------------------
for dicho in ("squat", "sq", "sentadilla", "low bar", "lb", "barra baja",
              "Sentadilla low bar", "back squat", "mi squat"):
    assert primero(dicho)[0] == "Sentadilla low bar", dicho

for dicho in ("banca", "bench", "bench press", "bp", "press banca", "la bp",
              "banca comp", "comp bp", "press de banca"):
    assert primero(dicho)[0] == "Banca comp", dicho

for dicho in ("sumo", "sumo dl", "dl sumo", "sumo deadlift", "peso muerto sumo",
              "el sumo"):
    assert primero(dicho)[0] == "Peso muerto sumo", dicho

# --- con faltas, que es como se escribe de verdad ----------------------------
for dicho, espera in (("sentadila", "Sentadilla low bar"),
                      ("squad", "Sentadilla low bar"),
                      ("sumo deadlight", "Peso muerto sumo"),
                      ("bench pres", "Banca comp")):
    ej, como = primero(dicho)
    assert ej == espera, (dicho, ej)
    assert como in ("vocabulario", "parecido"), (dicho, como)

# --- LO QUE NO PUEDE PASAR: fundir variantes ---------------------------------
# "banca" contesta por la de competición y DEJA LAS OTRAS APARTE, nunca en el mismo saco.
lista, _ = v.resolver("banca", NOMBRES)
assert lista[0] == "Banca comp"
assert "Banca 3ct" in lista[1:] and "Banca mid grip" in lista[1:], lista
# Y el del tacón no es el de ahora: sale como otra variante, no como la principal.
lista, _ = v.resolver("squat", NOMBRES)
assert lista[0] == "Sentadilla low bar"
assert "Sentadilla low bar tacón 2cm" in lista[1:], lista
# Pedir una variante CONCRETA da esa, no la principal.
assert primero("Sentadilla high bar")[0] == "Sentadilla high bar"
assert primero("banca 3ct")[0] == "Banca 3ct"

# --- no inventa --------------------------------------------------------------
assert v.resolver("rodillo abdominal", NOMBRES)[0] == [], "eso no lo ha hecho nunca"
assert v.resolver("", NOMBRES)[0] == []
# Un término del vocabulario cuyo ejercicio no está en los datos no se saca de la manga.
assert v.resolver("squat", ["Curl femoral"])[0] == []

print("OK")
