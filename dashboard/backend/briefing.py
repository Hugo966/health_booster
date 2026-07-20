"""Parte de estado — convierte la hoja en un párrafo que el modelo entiende.

Dos criterios de diseño que no son negociables:

  1. **Cada métrica va con su antigüedad.** Intervals rellena HRV/sueño/FC horas
     (a veces días) después que los formularios, así que la última fila del hub
     suele estar medio vacía. Si el briefing cogiera la última fila sin más,
     Jarvis diría "no sé nada de tu HRV" cada mañana; y si cogiera el último
     valor sin decir de cuándo es, opinaría sobre un dato de hace una semana
     como si fuera de hoy. Ambas cosas destruyen la confianza, así que se
     reporta valor + fecha + días, y se marca lo viejo como OBSOLETO.

  2. **Los umbrales replican los del frontend.** Si el briefing y el panel no
     coinciden, Jarvis contradice lo que Hugo ve en pantalla. Los de readiness
     salen de `readinessBand` en lib/theme.ts (<40 COOKED, 40-65 CAUTION,
     >65 READY) y las bandas de carga son percentiles del histórico propio,
     igual que en LoadPanel.
"""
from datetime import date, datetime

from sheets import fetch_all

OBJETIVO_SUENO_H = 7.5
# A partir de cuántos días un dato deja de valer como "ahora mismo". Es por
# métrica porque no todas envejecen igual: el HRV es diario y a los 3 días ya no
# dice nada del presente, pero Hugo se pesa ~una vez por semana, así que un peso
# de hace 4 días es perfectamente normal y marcarlo sería un falso positivo.
DIAS_OBSOLETO = {"peso": 10, "_defecto": 2}


def _num(v):
    """La hoja devuelve '' en los huecos, nunca null. Equivale a num() del front."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _serie(dd, col):
    """[(fecha, valor)] con solo las filas que tienen dato, en orden."""
    out = []
    for r in dd:
        v = _num(r.get(col))
        if v is not None:
            out.append((str(r.get("fecha", "")), v))
    return out


def _dias_desde(fecha_iso: str) -> int:
    try:
        return (date.today() - datetime.fromisoformat(fecha_iso).date()).days
    except ValueError:
        return 999


def _ultimo(dd, col):
    """(valor, fecha, dias) del dato más reciente, o None si nunca hubo."""
    s = _serie(dd, col)
    if not s:
        return None
    f, v = s[-1]
    return v, f, _dias_desde(f)


def _media(vals):
    return sum(vals) / len(vals) if vals else None


def _tendencia(dd, col, ventana=7):
    """Media de la última ventana menos la de la anterior. None si no hay datos."""
    s = [v for _, v in _serie(dd, col)]
    if len(s) < ventana + 2:
        return None
    act, prev = s[-ventana:], s[-2 * ventana : -ventana]
    if not prev:
        return None
    return _media(act) - _media(prev)


def _flecha(delta, umbral=0.0):
    if delta is None:
        return ""
    if delta > umbral:
        return f" (↗ +{delta:.1f} vs semana anterior)"
    if delta < -umbral:
        return f" (↘ {delta:.1f} vs semana anterior)"
    return " (estable)"


def _percentil(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    i = p * (len(s) - 1)
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def _banda_readiness(v):
    if v < 40:
        return "COOKED"
    if v <= 65:
        return "CAUTION"
    return "READY"


def _ritmo_peso(peso_rows, dias=42):
    """kg/semana por regresión lineal, como hace WeightTrend en el panel."""
    pts = []
    for r in peso_rows:
        v = _num(r.get("peso_kg"))
        f = str(r.get("fecha", ""))
        if v is None or not f:
            continue
        d = _dias_desde(f)
        if d <= dias:
            pts.append((-d, v))  # x en días, creciente hacia hoy
    if len(pts) < 3:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    if den == 0:
        return None
    return num / den * 7  # kg/día -> kg/semana


def _obsoleto(dato, clave="_defecto") -> bool:
    return dato is not None and dato[2] > DIAS_OBSOLETO.get(clave, DIAS_OBSOLETO["_defecto"])


def _linea(nombre, dato, unidad="", extra="", clave="_defecto"):
    """Formatea una métrica marcando la antigüedad si el dato ya no es de ahora."""
    if dato is None:
        return f"- {nombre}: sin datos"
    v, f, d = dato
    val = f"{v:g}{unidad}"
    if d == 0:
        cuando = "hoy"
    elif d == 1:
        cuando = "ayer"
    else:
        cuando = f"{f}, hace {d} días"
    marca = "  [OBSOLETO]" if _obsoleto(dato, clave) else ""
    return f"- {nombre}: {val} ({cuando}){extra}{marca}"


def generar() -> str:
    """El parte que se inyecta en cada conversación."""
    data = fetch_all()
    dd = data.get("derived_diario", [])
    if not dd:
        return "No hay datos disponibles ahora mismo."

    partes = [f"Parte de estado de Hugo — {date.today().isoformat()}", ""]

    # Readiness
    r = _ultimo(dd, "readiness")
    extra = ""
    if r:
        extra = f" — {_banda_readiness(r[0])}{_flecha(_tendencia(dd, 'readiness'), 1.0)}"
    partes.append(_linea("Readiness", r, "", extra))

    # HRV, con su rango habitual para que "68" signifique algo
    hrv = _ultimo(dd, "hrv_rmssd")
    extra = ""
    hist = [v for _, v in _serie(dd, "hrv_rmssd")][-60:]
    if hrv and len(hist) >= 10:
        m = _media(hist)
        sd = (sum((x - m) ** 2 for x in hist) / len(hist)) ** 0.5
        dentro = "dentro de" if abs(hrv[0] - m) <= sd else "fuera de"
        extra = f" — {dentro} su rango normal ({m - sd:.0f}-{m + sd:.0f} ms)"
    partes.append(_linea("HRV", hrv, " ms", extra))

    # Sueño: lo que importa es la media reciente contra el objetivo
    sue = _ultimo(dd, "sueno_horas")
    ult7 = [v for _, v in _serie(dd, "sueno_horas")][-7:]
    extra = ""
    if ult7:
        m = _media(ult7)
        comp = "por debajo de" if m < OBJETIVO_SUENO_H else "por encima de"
        extra = f" — media 7d {m:.1f} h, {comp} su objetivo de {OBJETIVO_SUENO_H} h"
    partes.append(_linea("Sueño", sue, " h", extra))

    cal = _ultimo(dd, "sueno_calidad")
    partes.append(_linea("Calidad de sueño (percibida 1-10)", cal))

    # Peso
    peso = _ultimo(dd, "peso_kg")
    if peso is None:
        pr = [r for r in data.get("peso", []) if _num(r.get("peso_kg")) is not None]
        if pr:
            f = str(pr[-1].get("fecha", ""))
            peso = (_num(pr[-1]["peso_kg"]), f, _dias_desde(f))
    ritmo = _ritmo_peso(data.get("peso", []))
    extra = f" — {ritmo:+.2f} kg/semana (últimas 6 sem)" if ritmo is not None else ""
    partes.append(_linea("Peso", peso, " kg", extra, clave="peso"))

    # Carga: sRPE de 7 días contra los percentiles de su propio histórico
    srpe = _ultimo(dd, "sRPE_7d")
    hist_srpe = [v for _, v in _serie(dd, "sRPE_7d")]
    extra = ""
    if srpe and len(hist_srpe) >= 5:
        p33, p67 = _percentil(hist_srpe, 0.33), _percentil(hist_srpe, 0.67)
        nivel = "baja" if srpe[0] < p33 else ("alta" if srpe[0] > p67 else "normal")
        extra = f" — carga {nivel} para él"
    partes.append(_linea("Carga sRPE 7 días", srpe, "", extra))

    mol = _ultimo(dd, "molestias_nivel")
    partes.append(_linea("Molestias (1-10)", mol))
    ene = _ultimo(dd, "energia")
    partes.append(_linea("Energía (1-10)", ene))

    # Momento del plan: de dónde viene y dónde está
    ses = [r for r in data.get("entreno_sesion", []) if r.get("bloque") not in ("", None)]
    if ses:
        u = ses[-1]
        partes.append(
            f"- Último entreno registrado: bloque {u.get('bloque')} semana "
            f"{u.get('semana')} ({u.get('fecha')})"
        )

    # Aviso de frescura, para que no opine sobre datos viejos como si fueran de hoy
    viejos = [
        n
        for n, d, k in [
            ("HRV", hrv, "_defecto"),
            ("sueño", sue, "_defecto"),
            ("peso", peso, "peso"),
            ("readiness", r, "_defecto"),
        ]
        if _obsoleto(d, k)
    ]
    if viejos:
        partes += [
            "",
            f"AVISO: {', '.join(viejos)} llevan días sin actualizarse. No hables de "
            "esos valores como si fueran de hoy; si vienen a cuento, comenta que "
            "están desactualizados (el reloj puede llevar días sin sincronizar).",
        ]

    return "\n".join(partes)


if __name__ == "__main__":
    print(generar())
