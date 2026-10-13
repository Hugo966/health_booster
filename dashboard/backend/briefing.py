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
import sys
from datetime import date, datetime
from pathlib import Path

from sheets import fetch_all

# La raíz del proyecto en el path: el backend arranca con cwd en dashboard/backend, así
# que `entreno_pipeline` (que vive en la raíz) no se encuentra solo. Se hace aquí de forma
# explícita y no confiando en que otro módulo lo haya hecho antes.
_RAIZ = str(Path(__file__).resolve().parents[2])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import entreno_pipeline  # noqa: E402

OBJETIVO_SUENO_H = 7.5
# Días de la ventana de carga. Es el mismo 7 que usan `sRPE_series_7d` en el pipeline y
# `VENTANA` en LoadPanel.tsx: si se cambia, hay que cambiarlo en los tres.
VENTANA_CARGA_D = 7
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

    # FC en reposo: se ingiere desde el principio pero no se pintaba en ningún panel ni
    # se le pasaba a Jarvis. Va justo detrás del HRV porque son pareja: cuando las dos se
    # mueven el mismo día en direcciones opuestas (HRV abajo, pulso arriba) la señal es
    # mucho más fiable que cualquiera de las dos por separado.
    fc = _ultimo(dd, "fc_reposo")
    extra = ""
    histfc = [v for _, v in _serie(dd, "fc_reposo")][-60:]
    if fc and len(histfc) >= 10:
        m = _media(histfc)
        d = fc[0] - m
        comp = ("por encima de" if d > 1 else "por debajo de" if d < -1 else "en")
        extra = f" — {comp} su media de {m:.0f} ppm"
        # Pulso alto + HRV bajo el mismo día es la combinación que de verdad importa.
        if hrv and histfc and len(hist) >= 10 and d > 2 and hrv[0] < _media(hist):
            extra += ". OJO: pulso por encima de su media Y HRV por debajo el mismo día"
    partes.append(_linea("FC en reposo", fc, " ppm", extra))

    # Sueño: lo que importa es la media reciente contra el objetivo
    sue = _ultimo(dd, "sueno_horas")
    ult7 = [v for _, v in _serie(dd, "sueno_horas")][-7:]
    extra = ""
    if ult7:
        m = _media(ult7)
        comp = "por debajo de" if m < OBJETIVO_SUENO_H else "por encima de"
        extra = f" — media 7d {m:.1f} h, {comp} su objetivo de {OBJETIVO_SUENO_H} h"
    partes.append(_linea("Sueño", sue, " h", extra))

    # Score de sueño del reloj (0-100). Estaba ingerido y sin usar en ningún sitio. Es la
    # otra mitad del sueño: las horas dicen CUÁNTO durmió y esto QUÉ TAL, así que sin él
    # no se distingue una noche corta buena de una corta y mala.
    sc = _ultimo(dd, "sueno_score")
    extra = ""
    histsc = [v for _, v in _serie(dd, "sueno_score")][-30:]
    if sc and len(histsc) >= 10:
        extra = f" — su media de 30 días es {_media(histsc):.0f}"
    partes.append(_linea("Score de sueño (reloj, 0-100)", sc, "", extra))

    cal = _ultimo(dd, "sueno_calidad")
    partes.append(_linea("Calidad de sueño (percibida, 1-9: 5 normal, 9 mejor)", cal))

    # Peso: se coge el MÁS RECIENTE de las dos fuentes, no el de derived_diario a secas.
    # La tabla `peso` se alimenta aparte y suele ir por delante: si el pipeline lleva días
    # sin correr, derived_diario tiene un peso viejo —no vacío— y antes ganaba igual, así
    # que Jarvis daba por última una pesada de hace semanas que el panel ya mostraba.
    peso = _ultimo(dd, "peso_kg")
    pr = [r for r in data.get("peso", []) if _num(r.get("peso_kg")) is not None]
    if pr:
        f = str(pr[-1].get("fecha", ""))
        suelto = (_num(pr[-1]["peso_kg"]), f, _dias_desde(f))
        if peso is None or f > peso[1]:  # fechas ISO: comparar como texto vale
            peso = suelto
    ritmo = _ritmo_peso(data.get("peso", []))
    extra = f" — {ritmo:+.2f} kg/semana (últimas 6 sem)" if ritmo is not None else ""
    partes.append(_linea("Peso", peso, " kg", extra, clave="peso"))

    # Carga: sRPE de 7 días contra los percentiles de su propio histórico.
    # `sRPE_series_7d` (RPE de sesión × series) sale de la MISMA columna que pinta el panel
    # de Carga. `sRPE_7d` (rpd × duración) queda de respaldo para el histórico anterior a
    # que existiera la columna.
    # OJO con comparar este número con el del panel: la fórmula es la misma, pero la fecha
    # de referencia no. Aquí se ancla a HOY (la carga aguda decae con el descanso, que es lo
    # correcto), mientras que el panel ancla a la última sesión. Tras unos días de descanso
    # los dos números difieren mucho y AMBOS son ciertos. No se "arregla" igualándolos: lo
    # que engaña de verdad son las sesiones que aún no cuentan, y de eso avisa el bloque de
    # abajo.
    col = "sRPE_series_7d" if _ultimo(dd, "sRPE_series_7d") else "sRPE_7d"
    srpe = _ultimo(dd, col)
    hist_srpe = [v for _, v in _serie(dd, col)]
    extra = ""
    if srpe and len(hist_srpe) >= 5:
        p33, p67 = _percentil(hist_srpe, 0.33), _percentil(hist_srpe, 0.67)
        nivel = "baja" if srpe[0] < p33 else ("alta" if srpe[0] > p67 else "normal")
        extra = f" — carga {nivel} para él"
    partes.append(_linea("Carga sRPE 7 días", srpe, "", extra))

    # Sesiones recientes que NO están contadas en esa cifra. El sRPE necesita el RPE de
    # sesión del formulario PM, y ese formulario puede tardar días en llegar: mientras tanto
    # una sesión dura y reciente no entra en la ventana, y el parte dice "carga baja" justo
    # el día después de ella. Sin este aviso Jarvis concluye lo contrario de lo que pasa.
    # Entrenos sin RPE de sesión. Se pregunta a `huecos`, que lee la pestaña ORIGEN
    # (`wellness_pm`), y NO a derived_diario: esa columna solo se rellena cuando corre el
    # pipeline, así que un RPE puesto después de la última pasada se veía como ausente y
    # Jarvis reclamaba un formulario que Hugo ya había rellenado.
    try:
        import huecos
        sin_rpe = huecos.estado(dias=VENTANA_CARGA_D)["fuentes"]["rpe"]["faltan"]
    except Exception:
        sin_rpe = []
    if sin_rpe:
        partes.append(
            f"  AVISO: esa carga NO incluye {len(sin_rpe)} entreno(s) de los últimos "
            f"{VENTANA_CARGA_D} días ({', '.join(sin_rpe)}): les falta el RPE de "
            "sesión porque el formulario PM está sin rellenar. La carga real es MAYOR que "
            "ese número, así que no concluyas que va descargado. Puedes rellenárselo tú "
            "con `guardar_pm` si te dice qué tal fue la sesión."
        )

    # Formularios pendientes. Se calcula contra las pestañas ORIGEN (huecos.estado), no
    # contra derived_diario: un día sin ningún dato no tiene fila ahí, así que los huecos
    # de verdad serían invisibles.
    try:
        import huecos
        est = huecos.estado(dias=7)
        pend = []
        for clave in ("am", "pm"):
            f = est["fuentes"][clave]
            if f["faltan"]:
                pend.append(f"{f['etiqueta']}: {', '.join(f['faltan'])}")
        if est["fuentes"]["peso"]["estado"] == "falta":
            pend.append(f"Peso: {est['fuentes']['peso']['detalle'].lower()}")
        if pend:
            partes.append("")
            partes.append("LE FALTAN FORMULARIOS POR RELLENAR:")
            partes += [f"- {t}" for t in pend]
            partes.append("  Puedes rellenárselos tú si te los cuenta (guardar_am / "
                          "guardar_pm / guardar_peso). Suéltalo cuando venga a cuento, "
                          "una vez y sin dar la brasa.")
    except Exception:
        pass  # que un fallo leyendo huecos no deje a Jarvis sin parte de estado

    mol = _ultimo(dd, "molestias_nivel")
    partes.append(_linea("Molestias (0-9: 0 nada, 9 máximo)", mol))
    ene = _ultimo(dd, "energia")
    partes.append(_linea("Energía (1-9: 5 normal, 9 mejor)", ene))

    # Momento del plan: de dónde viene y dónde está
    ses = [r for r in data.get("entreno_sesion", []) if r.get("bloque") not in ("", None)]
    if ses:
        u = ses[-1]
        # El nombre de la etapa sale del enrutado del plan, no de aquí: "bloque 2" no
        # significa nada para Hugo, que la llama Build. Antes esto estaba escrito a mano
        # en el prompt y se quedaba viejo — en septiembre Jarvis seguía diciendo que
        # estaba en offseason.
        etapa = entreno_pipeline.nombre_etapa(u.get("plani"), u.get("bloque"))
        # Cuántas semanas lleva ya en esta etapa: sitúa el "semana 2" sin inventarse
        # cuántas tiene en total, que eso solo lo sabe el plan del entrenador.
        mismas = {str(r.get("semana")) for r in ses
                  if str(r.get("bloque")) == str(u.get("bloque"))
                  and str(r.get("plani")) == str(u.get("plani"))}
        como = f"{etapa}" if etapa else f"bloque {u.get('bloque')}"
        linea = (
            f"- Momento del plan: {como} (plan {u.get('plani')}, bloque "
            f"{u.get('bloque')}), semana {u.get('semana')} — lleva {len(mismas)} "
            f"semana(s) en esta etapa"
            f"\n- Último entreno registrado: {u.get('fecha')}"
        )
        # Cómo FUE la sesión, no solo cuándo. Los agregados (volumen, series) bajan cuando
        # algo se tuerce, pero no dicen por qué, así que Jarvis daba por normal una sesión
        # en la que Hugo falló series o no pudo ni valorar el esfuerzo. Estas dos marcas
        # vienen del keep: `peso x0` -> falló la repe, `0x0` o ejercicio sin apuntar ->
        # no lo hizo, `@?`/`RIR?` -> no pudo valorar (dolor, lesión, prisa). Son lo único
        # que distingue una sesión mala de una sesión corta.
        marcas = []
        nf, nsi = _num(u.get("n_fallos_total")), _num(u.get("n_sin_intensidad_total"))
        if nf:
            marcas.append(f"{nf:g} series falladas (0 repes)")
        if nsi:
            marcas.append(f"{nsi:g} series sin poder valorar el esfuerzo (@?)")
        if marcas:
            linea += " — " + ", ".join(marcas)
        # Los ejercicios que no hizo, por su nombre. Si el motivo no está ya en las notas
        # de ese día (las tienes más abajo), ESO es lo que hay que preguntarle.
        nohech = str(u.get("no_hechos", "") or "").strip()
        if nohech:
            linea += f"\n- Ejercicios que NO hizo ese día: {nohech}"
        partes.append(linea)

    # Notas de los formularios AM/PM: texto libre de Hugo (cómo se sintió, lesiones,
    # vida, contexto…). Dan mucha información que los números no capturan, así que se le
    # pasan a Jarvis. Solo las que tienen algo escrito, las más recientes.
    notas = []
    for row in dd:
        f = str(row.get("fecha", ""))
        # El dolor de la sesión está DUPLICADO a propósito: Hugo lo escribe en el keep al
        # acabar de entrenar (`dolor_sesion_keep`) y más tarde copia el mismo texto al campo
        # "dolor de entreno" del formulario PM (`dolor_sesion_nota`). Pasarle los dos haría
        # que Jarvis leyera un único episodio como dos, así que el del keep entra solo
        # mientras el del formulario siga vacío: cubre la ventana entre entrenar y
        # rellenarlo, y desaparece en cuanto llega el bueno.
        campos = [("notas_am", "AM"), ("notas_pm", "PM"), ("dolor_sesion_nota", "dolor")]
        if not str(row.get("dolor_sesion_nota", "") or "").strip():
            campos.append(("dolor_sesion_keep", "dolor (del keep, aún sin pasar al form)"))
        trozos = [
            f"{etq}: {v.strip()}"
            for campo, etq in campos
            for v in [str(row.get(campo, "") or "")]
            if v.strip()
        ]
        if trozos:
            notas.append(f"- {f} · " + " · ".join(trozos))
    if notas:
        partes += ["", "Notas recientes de Hugo (texto libre de sus formularios):"] + notas[-8:]

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
