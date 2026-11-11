"""Cómo LLAMA el usuario a sus ejercicios, que no es como los apunta el entrenador.

Esto NO es `entreno_pipeline.ALIAS`, y la diferencia importa:

- `ALIAS` reetiqueta DATOS. Dos nombres se funden en uno y se reescribe el histórico, así
  que equivocarse ahí junta ejercicios distintos y sale caro (una banca de 178 kg que
  nadie hizo). Por eso es exacta y hay que ganársela a mano.
- Esto es una BÚSQUEDA. Traduce lo que alguien dice en voz alta —"mi squat", "la bp",
  "sumo"— al nombre que de verdad está en la hoja. Equivocarse aquí no estropea nada:
  se devuelve otro ejercicio y se dice en voz alta cuál, y quien pregunta lo corrige.

Por eso aquí sí se tolera la falta de ortografía y el inglés, y ahí no.

La regla que no se rompe: **las variantes no se mezclan nunca**. "Banca" encuentra la de
competición, la larssen y el complex; se contesta por la PRINCIPAL y se dicen las otras,
pero jamás se suman en un solo número.
"""
import difflib
import sys
import unicodedata
from pathlib import Path

_RAIZ = str(Path(__file__).resolve().parents[2])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import entreno_pipeline  # noqa: E402

# Lo que se dice -> el ejercicio que se busca. La clave es el nombre canónico normalizado
# tal como aparece en la hoja; si ese ejercicio no existe en los datos, no se inventa.
#
# Los básicos van cargados a propósito: son los tres que se nombran noventa veces de cada
# cien, en castellano, en inglés y en abreviatura de gimnasio.
BASICOS = {
    "sentadilla low bar": (
        "squat", "sq", "sentadilla", "sentadillas", "low bar", "lowbar", "lb",
        "barra baja", "sq low bar", "sentadilla lb", "sentadilla barra baja",
        "back squat", "squat low bar", "low bar squat", ),
    "banca comp": (
        "banca", "bench", "bench press", "bp", "press banca", "press de banca",
        "banca competicion", "banca comp", "comp bp", "press de pecho", "bench comp", "banca plana",
    ),
    # "Peso muerto" a secas es el SUMO: es el que tira en competición, y es el que quiere
    # decir cuando dice "mi peso muerto" (dicho por él, 2026-11-11). Antes no estaba en
    # ninguna lista y se resolvía por subcadena, que ordena por longitud y devolvía
    # "Peso muerto comp" — o sea que preguntar por su básico le contestaba por otro
    # ejercicio, y el sumo no aparecía ni como primero ni como variante.
    "peso muerto sumo": (
        "sumo", "sumo dl", "dl sumo", "sumo deadlift", "deadlift sumo", "pm sumo",
        "peso muerto sumo", "muerto sumo", "sumo deadlifts",
        "peso muerto", "muerto", "deadlift", "deadlifts", "dead lift", "dl", "pm",
    ),
    # El convencional hay que pedirlo POR SU NOMBRE. No es el que se lleva "peso muerto"
    # a secas, aunque se llame "convencional": el suyo de siempre es el sumo.
    "peso muerto convencional deficit 2cm": (
        "peso muerto convencional", "convencional", "deadlift convencional",
        "pm convencional", "deficit", "peso muerto deficit",
    ),
}

# Cuánto se parece algo para darlo por lo mismo. 0,78 deja pasar "sentadila", "squad" y
# "sumo deadlight" (que es como salió escrito de verdad) y NO deja pasar "banca" contra
# "barra", que son cuatro letras de ocho.
PARECIDO = 0.78


def _key(t: str) -> str:
    return entreno_pipeline._key(str(t))


def _sin_tildes(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


# Nadie dice "banca": dice "la banca", "el peso muerto". Se quitan delante
# porque si no "la bp" no se parece a "bp" ni para difflib (dos letras de cinco).
_ARTICULOS = ("la ", "el ", "los ", "las ", "mi ", "mis ", "un ", "una ", "de ")


def _pelado(q: str) -> str:
    cambiado = True
    while cambiado:
        cambiado = False
        for a in _ARTICULOS:
            if q.startswith(a):
                q, cambiado = q[len(a):], True
    return q.strip()


_TERMINOS = {_sin_tildes(t): _sin_tildes(canon)
             for canon, terminos in BASICOS.items() for t in terminos}


def resolver(texto: str, nombres: list[str]) -> tuple[list[str], str]:
    """Qué ejercicios de `nombres` quiere decir `texto`. Devuelve (lista, cómo).

    La lista va de más a menos probable y NUNCA se fusiona: quien la use contesta por el
    primero y menciona los demás. `cómo` dice por qué camino salió, para que Jarvis pueda
    decir "entiendo que te refieres a X" cuando ha tenido que adivinar.
    """
    q = _pelado(_sin_tildes(_key(texto)))
    if not q:
        return [], "vacio"
    por_clave = {_sin_tildes(_key(n)): n for n in nombres}

    # 1) El nombre tal cual.
    if q in por_clave:
        return [por_clave[q]], "exacto"

    # 2) Como lo llama él. Si el canónico no está en los datos se sigue buscando: el
    #    vocabulario no puede inventar un ejercicio que no ha hecho nunca.
    canon = _TERMINOS.get(q)
    if canon and canon in por_clave:
        principal = por_clave[canon]
        # Las demás variantes del mismo movimiento, para poder ofrecerlas. Se buscan por
        # lo que se ha dicho ("banca" saca la larssen) Y por la primera palabra del
        # canónico ("sentadilla" saca la del tacón), que no siempre es lo mismo.
        pistas = {q, canon.split()[0]}
        otros = [n for k, n in por_clave.items()
                 if n != principal and any(p in k for p in pistas)]
        return [principal] + sorted(otros), "vocabulario"

    # 3) Subcadena: "banca" saca las tres bancas. Se ordenan por longitud para que el
    #    nombre más corto —casi siempre el básico— sea el primero.
    contiene = sorted((n for k, n in por_clave.items() if q in k), key=len)
    if contiene:
        return contiene, "contiene"

    # 4) Y si no, falta de ortografía: se compara contra lo que él dice y contra los
    #    nombres de la hoja. Es lo último porque es lo único que puede equivocarse.
    cerca = difflib.get_close_matches(q, list(_TERMINOS), n=1, cutoff=PARECIDO)
    if cerca:
        canon = _TERMINOS[cerca[0]]
        if canon in por_clave:
            return [por_clave[canon]], "parecido"
        contiene = sorted((n for k, n in por_clave.items() if canon in k), key=len)
        if contiene:
            return contiene, "parecido"
    cerca = difflib.get_close_matches(q, list(por_clave), n=3, cutoff=PARECIDO)
    if cerca:
        return [por_clave[c] for c in cerca], "parecido"
    return [], "nada"
