"""Orquestación del chat — monta el contexto, habla con el modelo y ejecuta herramientas.

Hay DOS familias de herramientas y la diferencia es estructural:

  - **De lectura** (`dia`, `ejercicio`, `recordar`): las ejecuta este backend y el
    resultado vuelve al modelo, que sigue razonando con él.
  - **De actuación** (`abrir_panel`, `cerrar_panel`, `resaltar`, `grafico`): el
    servidor NO puede ejecutarlas — pasan al navegador como una lista de acciones.

Por eso una respuesta es `{texto, acciones}`. Un tour guiado no necesita motor
propio: es una respuesta con varias acciones seguidas.

**Sobre los resultados de herramienta:** se inyectan en el hilo como texto plano
("[resultado de dia(...)]: ..."), no con los bloques formales de tool_result.
Ollama y Anthropic los formatean distinto y esa divergencia sería la parte más
frágil de `proveedor.py`; en texto plano funciona igual en ambos y los modelos
pequeños lo siguen sin problema. Si algún día estorba, se cambia ahí dentro.
"""
import json

import briefing
import memoria
import personalidad
import proveedor
from sheets import fetch_all

MAX_VUELTAS = 4  # tope de idas y venidas con herramientas, por si el modelo se atasca

PANELES = ["readiness", "hrv", "sueno", "carga", "fuerza", "peso", "correlaciones"]

HERRAMIENTAS_LECTURA = [
    {
        "nombre": "dia",
        "descripcion": "Consulta los datos de un día concreto: readiness, HRV, sueño, "
                       "ánimo y qué entrenó. Úsala cuando Hugo pregunte por una fecha.",
        "params": {"fecha": {"type": "string", "description": "Fecha en formato AAAA-MM-DD"}},
        "requeridos": ["fecha"],
    },
    {
        "nombre": "ejercicio",
        "descripcion": "Histórico de un ejercicio: mejor marca y series recientes. "
                       "Úsala cuando pregunte por cómo va en un movimiento concreto.",
        "params": {"nombre": {"type": "string", "description": "Nombre del ejercicio, p.ej. 'banca'"}},
        "requeridos": ["nombre"],
    },
    {
        "nombre": "recordar",
        "descripcion": "Guarda algo de la vida de Hugo para acordarte en futuras "
                       "conversaciones (lo que lee, viajes, gente, cómo se siente, metas). "
                       "NO la uses para números del dashboard: esos ya te llegan solos.",
        "params": {
            "tema": {"type": "string", "description": "Etiqueta corta, p.ej. 'lectura'"},
            "texto": {"type": "string", "description": "El hecho, en una frase"},
        },
        "requeridos": ["tema", "texto"],
    },
]

HERRAMIENTAS_UI = [
    {
        "nombre": "abrir_panel",
        "descripcion": f"Abre un panel del dashboard para enseñárselo. Paneles: {', '.join(PANELES)}.",
        "params": {"panel": {"type": "string", "enum": PANELES}},
        "requeridos": ["panel"],
    },
    {
        "nombre": "cerrar_panel",
        "descripcion": "Cierra el panel que esté abierto.",
        "params": {},
        "requeridos": [],
    },
    {
        "nombre": "resaltar",
        "descripcion": "Ilumina una zona concreta del panel abierto para señalarla.",
        "params": {"ancla": {"type": "string", "description": "Identificador de la zona"}},
        "requeridos": ["ancla"],
    },
]

HERRAMIENTAS = HERRAMIENTAS_LECTURA + HERRAMIENTAS_UI
NOMBRES_UI = {h["nombre"] for h in HERRAMIENTAS_UI}


# --- herramientas de lectura -------------------------------------------------

def _tool_dia(fecha: str) -> dict:
    data = fetch_all()
    fila = next((r for r in data.get("derived_diario", []) if str(r.get("fecha")) == fecha), None)
    if fila is None:
        return {"error": f"no hay datos del {fecha}"}
    interesa = ["readiness", "hrv_rmssd", "sueno_horas", "sueno_calidad", "energia",
                "molestias_nivel", "rpd_sesion", "volumen_total", "n_series_total"]
    resumen = {k: fila[k] for k in interesa if fila.get(k) not in ("", None)}
    sets = [
        {"ejercicio": s.get("ejercicio"), "kg": s.get("kg"), "reps": s.get("reps"),
         "n_series": s.get("n_series"), "rpe": s.get("rpe")}
        for s in data.get("entreno_sets", [])
        if str(s.get("fecha")) == fecha and s.get("ejercicio")
    ]
    return {"fecha": fecha, "datos": resumen, "series": sets}


def _tool_ejercicio(nombre: str) -> dict:
    data = fetch_all()
    aguja = nombre.lower().strip()
    filas = [s for s in data.get("entreno_sets", [])
             if aguja in str(s.get("ejercicio", "")).lower()]
    if not filas:
        return {"error": f"no encuentro ningún ejercicio que contenga '{nombre}'"}

    variantes = sorted({str(s.get("ejercicio")) for s in filas})
    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    e1rms = [(_f(s.get("e1rm")), str(s.get("fecha"))) for s in filas]
    e1rms = [(v, f) for v, f in e1rms if v is not None]
    mejor = max(e1rms, default=None)

    recientes = [
        {"fecha": str(s.get("fecha")), "ejercicio": s.get("ejercicio"),
         "kg": s.get("kg"), "reps": s.get("reps"), "rpe": s.get("rpe")}
        for s in filas[-8:]
    ]
    return {
        "buscado": nombre,
        # Las variantes NO se fusionan: banca competición y banca 3ct son ejercicios
        # distintos, así que se listan para que el modelo no las mezcle al hablar.
        "variantes_encontradas": variantes,
        "mejor_e1rm": {"valor": mejor[0], "fecha": mejor[1]} if mejor else None,
        "series_recientes": recientes,
    }


def _ejecutar_lectura(llamada) -> str:
    """Ejecuta una herramienta de backend y devuelve su resultado como texto."""
    try:
        if llamada.nombre == "dia":
            res = _tool_dia(str(llamada.args.get("fecha", "")))
        elif llamada.nombre == "ejercicio":
            res = _tool_ejercicio(str(llamada.args.get("nombre", "")))
        elif llamada.nombre == "recordar":
            tema = str(llamada.args.get("tema", "general"))
            texto = str(llamada.args.get("texto", "")).strip()
            if not texto:
                res = {"error": "hace falta el texto del hecho"}
            else:
                memoria.recordar(tema, texto)
                res = {"guardado": True, "tema": tema, "texto": texto}
        else:
            res = {"error": f"herramienta desconocida: {llamada.nombre}"}
    except Exception as e:  # que un fallo de herramienta no tumbe la conversación
        res = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(res, ensure_ascii=False, default=str)


# --- el ciclo de conversación ------------------------------------------------

def responder(sesion: str, mensaje: str, forzar_proveedor: str | None = None) -> dict:
    """Un turno completo: guarda, pregunta al modelo, ejecuta herramientas, devuelve."""
    memoria.init()
    memoria.guardar_mensaje(sesion, "usuario", mensaje)

    sistema = personalidad.sistema(briefing.generar(), memoria.hechos_relevantes())
    prov = proveedor.obtener(forzar_proveedor)

    # El hilo ya incluye el mensaje recién guardado.
    mensajes = [
        {"role": "user" if m["rol"] == "usuario" else "assistant", "content": m["texto"]}
        for m in memoria.hilo_reciente(sesion)
    ]

    acciones, texto = [], ""
    uso = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    for _ in range(MAX_VUELTAS):
        r = prov.responder(sistema, mensajes, HERRAMIENTAS)
        for k in uso:
            uso[k] += r.uso.get(k, 0)
        if r.texto:
            texto = (texto + "\n" + r.texto).strip() if texto else r.texto

        if not r.llamadas:
            break

        # Las de UI se acumulan para el navegador; las de lectura se ejecutan aquí.
        lecturas = []
        for ll in r.llamadas:
            if ll.nombre in NOMBRES_UI:
                acciones.append({"tipo": ll.nombre, **ll.args})
            else:
                lecturas.append(ll)

        # Acción de UI y ni una palabra: el modelo suele emitir `abrir_panel` a secas.
        # Si cortáramos aquí, Hugo vería abrirse el panel y a Jarvis mudo (ni burbuja ni
        # voz). Se le confirma que ya está hecho para que dé UNA vuelta más y lo comente.
        if not lecturas and not texto:
            mensajes.append({"role": "assistant", "content": r.texto or ""})
            hechas = ", ".join(a["tipo"] for a in acciones) or "ninguna"
            mensajes.append({
                "role": "user",
                "content": f"[hecho: {hechas}. El panel ya está abierto en su pantalla. "
                           f"Comenta ahora lo que ve, en una o dos frases. No vuelvas a "
                           f"llamar a la herramienta.]",
            })
            continue

        if not lecturas:
            break

        mensajes.append({"role": "assistant", "content": r.texto or ""})
        for ll in lecturas:
            args = json.dumps(ll.args, ensure_ascii=False)
            mensajes.append({
                "role": "user",
                "content": f"[resultado de {ll.nombre}({args})]: {_ejecutar_lectura(ll)}",
            })

    # Al pedirle que comente una acción de UI, a veces vuelve a llamar a la herramienta
    # en esa vuelta extra y el panel se abriría dos veces. Se quitan las repetidas,
    # conservando el orden (un tour guiado sí puede abrir varios paneles distintos).
    vistas, unicas = set(), []
    for a in acciones:
        clave = json.dumps(a, sort_keys=True, ensure_ascii=False)
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(a)

    if texto:
        memoria.guardar_mensaje(sesion, "jarvis", texto)
    return {"texto": texto, "acciones": unicas, "uso": uso}
