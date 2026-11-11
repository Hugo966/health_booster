"""Todo lo que enseñan los paneles, de una vez, para cuando algo no cuadra.

El parte de estado se monta en CADA mensaje, así que tiene que ser corto: meterle el
histórico de fuerza y la matriz de correlaciones encarecería todos los turnos de una
conversación normal para algo que hace falta de uvas a peras.

Esto es lo contrario: se pide a propósito (`refrescar`) y trae el resto —fuerza,
correlaciones, el detalle del sueño y la serie de carga—, que es justo lo que Hugo tiene
delante en pantalla cuando dice "pues yo veo otra cosa". Ligero por defecto, completo
cuando se necesita.

Las cuentas replican las de los paneles a propósito; si se tocan allí, hay que tocarlas
aquí, y por eso cada una dice de qué panel sale.
"""
from sheets import fetch_all

# Mismos umbrales que `CorrelationHeatmap.tsx`: por debajo de 14 pares una correlación es
# ruido con forma de conclusión, y por debajo de |0,2| no es ni débil.
MIN_PARES = 14
R_DEBIL = 0.2

# Los mismos cruces que pinta el panel de Correlaciones, en el mismo orden.
PARES = [
    ("sueno_horas_ayer", "sensacion_am", "Sueño ayer × sensación AM"),
    ("hrv_ayer", "readiness", "HRV ayer × readiness"),
    ("cafeina_ayer_mg", "sueno_horas", "Cafeína ayer × sueño"),
    ("alcohol_ayer", "hrv_rmssd", "Alcohol ayer × HRV"),
    ("sRPE", "readiness", "sRPE día × readiness"),
    ("sRPE_7d", "readiness", "sRPE 7d × readiness"),
    ("sRPE", "molestias_nivel", "sRPE día × molestias"),
    ("sRPE_7d", "molestias_nivel", "sRPE 7d × molestias"),
]

# Cuántos ejercicios se enseñan. Hay más de cien nombres distintos en el histórico y casi
# todos son accesorios que hizo cuatro veces; lo que importa es lo que entrena AHORA.
TOPE_EJERCICIOS = 14


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _pearson(pares):
    n = len(pares)
    if n < MIN_PARES:
        return None
    mx = sum(p[0] for p in pares) / n
    my = sum(p[1] for p in pares) / n
    sxy = sum((x - mx) * (y - my) for x, y in pares)
    sxx = sum((x - mx) ** 2 for x, _ in pares)
    syy = sum((y - my) ** 2 for _, y in pares)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def _correlaciones(dd) -> list[str]:
    out = []
    for a, b, etiqueta in PARES:
        pares = [(x, y) for x, y in
                 ((_num(r.get(a)), _num(r.get(b))) for r in dd)
                 if x is not None and y is not None]
        r = _pearson(pares)
        if r is None:
            out.append(f"- {etiqueta}: sin datos suficientes ({len(pares)} días, "
                       f"hacen falta {MIN_PARES})")
        else:
            fuerza = "nada" if abs(r) < R_DEBIL else ("fuerte" if abs(r) >= 0.5 else "débil")
            out.append(f"- {etiqueta}: r={r:+.2f} ({fuerza}, {len(pares)} días)")
    return out


def _fuerza(rm1) -> list[str]:
    """e1RM por bloque, que es lo que dibuja el panel de Fuerza.

    Es un ESTIMADO, no una marca: la línea lo dice en cada bloque porque es el error que
    más caro sale, presentarle como récord algo que no ha levantado nunca.
    """
    filas = [r for r in rm1 if r.get("ejercicio") and _num(r.get("mejor_e1rm")) is not None]
    if not filas:
        return ["(sin datos de fuerza)"]

    def clave(r):
        return (_num(r.get("plani")) or 0, _num(r.get("bloque")) or 0, _num(r.get("semana")) or 0)

    ultimo = max(clave(r) for r in filas)
    # Los que entrena en el plan y bloque de AHORA; si no, el histórico entero son
    # accesorios de hace un año.
    recientes = {r["ejercicio"] for r in filas if clave(r)[:2] == ultimo[:2]}
    out = []
    for ej in sorted(recientes)[:TOPE_EJERCICIOS]:
        suyas = sorted((r for r in filas if r["ejercicio"] == ej), key=clave)
        puntos = [f"P{int(_num(r['plani']) or 0)}B{int(_num(r['bloque']) or 0)}"
                  f"S{int(_num(r['semana']) or 0)}: {_num(r['mejor_e1rm']):g}" for r in suyas[-5:]]
        out.append(f"- {ej} (e1RM ESTIMADO, no es una marca) — {' · '.join(puntos)}")
    if len(recientes) > TOPE_EJERCICIOS:
        out.append(f"  (y {len(recientes) - TOPE_EJERCICIOS} ejercicios más del bloque; "
                   "pregunta por uno con la herramienta `ejercicio`)")
    return out


def _sueno(dd) -> list[str]:
    """Lo que el panel de Sueño enseña y el parte no: cama contra dormido."""
    ult = [r for r in dd if _num(r.get("eficiencia_sueno")) is not None][-30:]
    if not ult:
        return []
    ef = sum(_num(r["eficiencia_sueno"]) for r in ult) / len(ult)
    camas = [_num(r.get("tiempo_en_cama_h")) for r in ult if _num(r.get("tiempo_en_cama_h"))]
    horas = [_num(r.get("sueno_horas")) for r in ult if _num(r.get("sueno_horas"))]
    linea = f"- Eficiencia media (30 noches): {ef:.0f}% de lo que pasa en cama"
    if camas and horas:
        perdido = sum(camas) / len(camas) - sum(horas) / len(horas)
        linea += (f" · en cama {sum(camas)/len(camas):.1f} h y dormido "
                  f"{sum(horas)/len(horas):.1f} h, o sea ~{perdido*60:.0f} min entre "
                  "tardar en dormirse y despertares")
    return [linea]


def _carga(dd) -> list[str]:
    """La serie que dibujan las barras del panel de Carga, no solo el titular."""
    ult = [r for r in dd if _num(r.get("sRPE_series")) is not None][-10:]
    if not ult:
        return []
    return ["- Últimas sesiones (sRPE por sesión): " +
            " · ".join(f"{str(r['fecha'])[:10]}: {_num(r['sRPE_series']):g}" for r in ult)]


def completo() -> str:
    """El bloque entero. Se añade al parte cuando Jarvis llama a `refrescar`."""
    data = fetch_all()
    dd = data.get("derived_diario", [])
    trozos = ["LO QUE ENSEÑAN LOS PANELES (esto no va en el parte de cada mensaje; "
              "lo tienes porque acabas de refrescar)"]
    for titulo, lineas in (("FUERZA (panel de Fuerza)", _fuerza(data.get("rm1", []))),
                           ("CARGA (panel de Carga)", _carga(dd)),
                           ("SUEÑO (panel de Sueño)", _sueno(dd)),
                           ("CORRELACIONES (panel de Correlaciones)", _correlaciones(dd))):
        if lineas:
            trozos += ["", titulo] + lineas
    return "\n".join(trozos)
