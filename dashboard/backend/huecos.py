"""Qué falta por rellenar — el semáforo de la sección Formularios.

Hay que construirlo contra un CALENDARIO, no contra las filas de la hoja: `derived_diario`
solo tiene fila para los días con algún dato (`status_pipeline.consolidate`), así que un
día totalmente vacío —justo el que hay que detectar— no existe como fila.

Se lee de las pestañas ORIGEN (`wellness_am`, `wellness_pm`, `peso`), no de
`derived_diario`: así el semáforo dice la verdad aunque el pipeline lleve días sin correr,
y refleja al instante lo que se acaba de guardar desde la app.

Tres estados y no dos: `pendiente` es lo que evita que esto esté en rojo todas las mañanas
antes de que a Hugo le dé tiempo a rellenar nada.
"""
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import formularios
import sheets

ROOT = Path(__file__).resolve().parents[2]

# Antes de esta hora, el formulario AM del día está "pendiente", no "falta": se rellena
# al levantarse, y marcarlo en rojo a las 8 de la mañana sería ruido.
HORA_LIMITE_AM = 12

# El peso es SEMANAL (martes, en ayunas). Con la tolerancia de 2 días del resto estaría
# siempre en rojo. Mismo criterio que DIAS_OBSOLETO en briefing.py.
DIAS_PESO = 10
# El keep se vuelca a mano cada pocos días; no es un diario.
DIAS_KEEP = 4
VENTANA_RPE_D = 7

# Un formulario cuenta como puesto si tiene SUS campos núcleo. Hay filas reales con la
# fecha y las notas rellenas pero sin ningún número, así que "hay fila" no basta.
NUCLEO = {
    "am": ["sueno_calidad", "sensacion_am", "animo", "estres", "molestias_nivel"],
    "pm": ["energia", "sensacion_global"],
}

_CABECERA_KEEP = re.compile(r"^\s*SEM\s*\d+\s*-\s*D[IÍ]A\s*\d+.*?(\d{4}-\d{2}-\d{2})", re.I)


def _dm(iso: str | None) -> str:
    """'2026-08-18' -> '18/08'. Saber CUÁNDO fue el último dato dice más que 'hace 6 días'."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso else "—"


def _hoy() -> date:
    return date.today()


def _por_fecha(pestana: str) -> dict[str, dict]:
    """{fecha: fila} de una pestaña. La última gana, igual que en consolidate()."""
    fuera = {}
    for fila in sheets.fetch_all().get(pestana, []):
        f = str(fila.get("fecha", ""))[:10]
        if f:
            fuera[f] = fila
    return fuera


def _relleno(fila: dict | None, campos: list[str]) -> bool:
    return bool(fila) and all(str(fila.get(c, "")).strip() != "" for c in campos)


def _ultima_sesion_keep() -> str | None:
    """Fecha de la última sesión escrita en keep.txt, o None si no se puede leer.

    El keep es un fichero LOCAL: en la máquina que no lo tenga, esta señal no existe y
    la luz sale en gris, no en rojo.
    """
    ruta = os.getenv("KEEP_TXT")
    if not ruta or not Path(ruta).exists():
        return None
    fechas = []
    for linea in Path(ruta).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = _CABECERA_KEEP.match(linea)
        if m:
            fechas.append(m.group(1))
    return max(fechas) if fechas else None


def _color(estados: list[str]) -> str:
    if "falta" in estados:
        return "rojo"
    if "pendiente" in estados or "aviso" in estados:
        return "ambar"
    return "verde"


def estado(dias: int = 14, ahora: datetime | None = None) -> dict:
    """El semáforo: qué falta por fuente en los últimos `dias`."""
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    calendario = [(hoy - timedelta(days=i)).isoformat() for i in range(dias - 1, -1, -1)]

    am, pm = _por_fecha("wellness_am"), _por_fecha("wellness_pm")
    pesos = _por_fecha("peso")
    sesiones = {str(s.get("fecha", ""))[:10]: s
                for s in sheets.fetch_all().get("entreno_sesion", [])}

    fuentes: dict[str, dict] = {}
    dias_detalle = []

    # --- formularios AM y PM, día a día -------------------------------------
    for tipo, tabla in (("am", am), ("pm", pm)):
        faltan = []
        for f in calendario:
            if _relleno(tabla.get(f), NUCLEO[tipo]):
                continue
            # El PM se rellena al CERRAR el día, así que el de hoy no se juzga hasta
            # mañana: tenerlo en ámbar desde por la mañana es ruido, no información.
            if f == hoy.isoformat() and (tipo == "pm" or ahora.hour < HORA_LIMITE_AM):
                continue
            faltan.append(f)
        hoy_pendiente = (tipo == "am"
                         and not _relleno(tabla.get(hoy.isoformat()), NUCLEO["am"])
                         and hoy.isoformat() not in faltan)
        # Último día que SÍ está relleno: es lo que hay que enseñar cuando falta algo.
        ultimo = max((f for f in tabla if _relleno(tabla[f], NUCLEO[tipo])), default=None)
        estado_f = "falta" if faltan else ("pendiente" if hoy_pendiente else "ok")
        fuentes[tipo] = {
            "etiqueta": formularios.ESQUEMA[tipo].titulo,
            "estado": estado_f,
            "faltan": faltan,
            "ultima": ultimo,
            "detalle": (f"Faltan {len(faltan)} de {dias} días · el último relleno, "
                        f"{_dm(ultimo)}" if faltan else
                        ("Pendiente el de hoy" if hoy_pendiente else
                         f"Al día · último {_dm(ultimo)}" if ultimo else "Sin datos")),
        }

    # Un día cuenta como ENTRENADO si tiene `rpd_sesion` puesto en el PM: Hugo lo rellena
    # cuando ha entrenado y lo deja vacío cuando no. Esa señal es más fiable que el keep,
    # porque no depende de que haya volcado sus notas (ni de en qué máquina estén).
    entrenados = {f for f, r in pm.items() if str(r.get("rpd_sesion", "")).strip() != ""}
    entrenados |= set(sesiones)
    for f in calendario:
        dias_detalle.append({
            "fecha": f,
            "am": _relleno(am.get(f), NUCLEO["am"]),
            "pm": _relleno(pm.get(f), NUCLEO["pm"]),
            "entreno": f in entrenados,
            # entrenó pero no está volcado: el aviso de "mete este día en el keep"
            "sin_keep": f in entrenados and f not in sesiones,
        })

    # --- peso: por antigüedad, no por día ------------------------------------
    ultimo_peso = max(pesos, default=None)
    dias_peso = (hoy - date.fromisoformat(ultimo_peso)).days if ultimo_peso else 999
    fuentes["peso"] = {
        "etiqueta": "Peso",
        "estado": "falta" if dias_peso > DIAS_PESO else "ok",
        "ultima": ultimo_peso,
        "detalle": (f"Última pesada hace {dias_peso} días · {_dm(ultimo_peso)}"
                    if ultimo_peso else "Sin ninguna pesada"),
    }

    # --- RPE de sesión: hubo entreno pero falta el rpd_sesion del PM ----------
    # Sin él no hay sRPE_series y la sesión entera se cae de la carga. Es el hueco que
    # más rompe los datos, y por eso va aparte de "falta el PM".
    sin_rpe = [f for f in sesiones
               if (hoy - date.fromisoformat(f)).days <= VENTANA_RPE_D
               and str(pm.get(f, {}).get("rpd_sesion", "")).strip() == ""]
    ultimo_entreno = max(sesiones, default=None)
    fuentes["rpe"] = {
        "etiqueta": "RPE de sesión",
        "estado": "falta" if sin_rpe else "ok",
        "faltan": sorted(sin_rpe),
        "ultima": ultimo_entreno,
        "detalle": (", ".join(_dm(f) for f in sorted(sin_rpe)) + " sin RPE: no cuentan "
                    "para la carga" if sin_rpe else
                    f"Al día · último entreno {_dm(ultimo_entreno)}" if ultimo_entreno
                    else "Sin entrenos"),
    }

    # --- entreno sin volcar al keep ------------------------------------------
    # La señal buena es el RPE del PM: si está puesto, entrenó. Comparándolo con
    # `entreno_sesion` (que sale del keep) salen los días que le falta escribir.
    # Antes esto solo miraba la frescura del fichero local, que además no va por git:
    # si el keep está en la otra máquina, "hace 7 días sin entrenar" es falso.
    sin_volcar = sorted(f for f in calendario
                        if f in entrenados and f not in sesiones)
    ultimo_keep = _ultima_sesion_keep()
    ultimo_hoja = max(sesiones, default=None)
    if sin_volcar:
        fuentes["keep"] = {
            "etiqueta": "Entreno (keep)",
            "estado": "falta",
            "faltan": sin_volcar,
            "ultima": ultimo_hoja,
            "detalle": f"Entrenaste {', '.join(_dm(f) for f in sin_volcar)} y no está en "
                       "el keep: vuelca esas sesiones",
        }
    elif ultimo_keep and ultimo_hoja and ultimo_keep < ultimo_hoja:
        fuentes["keep"] = {
            "etiqueta": "Entreno (keep)",
            "estado": "aviso",
            "ultima": ultimo_hoja,
            "detalle": f"El keep de esta máquina ({_dm(ultimo_keep)}) va por detrás de la "
                       f"hoja ({_dm(ultimo_hoja)}): tráetelo del otro equipo",
        }
    else:
        ultima = ultimo_hoja or ultimo_keep
        if ultima is None:
            fuentes["keep"] = {"etiqueta": "Entreno (keep)", "estado": "no_disponible",
                               "detalle": "Sin sesiones registradas"}
        else:
            dias_keep = (hoy - date.fromisoformat(ultima)).days
            fuentes["keep"] = {
                "etiqueta": "Entreno (keep)",
                "estado": "ok",
                "ultima": ultima,
                "detalle": f"Al día · última sesión {_dm(ultima)} (hace {dias_keep} días)",
            }

    estados = [v["estado"] for v in fuentes.values() if v["estado"] != "no_disponible"]
    color = _color(estados)
    # El resumen dice QUÉ falla, no cuántas cosas: "1 cosa pendiente" obliga a abrir el
    # panel para enterarte de nada.
    flojas = [v["etiqueta"] for v in fuentes.values()
              if v["estado"] in ("falta", "pendiente", "aviso")]
    return {
        "hoy": hoy.isoformat(),
        "color": color,
        "resumen": "Todo en orden" if color == "verde" else ", ".join(flojas),
        "fuentes": fuentes,
        "dias": dias_detalle,
    }
