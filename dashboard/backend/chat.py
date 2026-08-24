"""Orquestación del chat — monta el contexto, habla con el modelo y ejecuta herramientas.

Hay DOS familias de herramientas y la diferencia es estructural:

  - **De lectura** (`dia`, `ejercicio`, `recordar`, `estado_formularios`): las ejecuta
    este backend y el resultado vuelve al modelo, que sigue razonando con él.
  - **De escritura** (`guardar_am`, `guardar_pm`, `guardar_peso`): también las ejecuta el
    backend, pero MODIFICAN la hoja de Hugo. Van en su propia lista para que se vea de un
    vistazo qué puede tocar sus datos.
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
import os
from datetime import date

import briefing
import formularios
import huecos
import memoria
import personalidad
import proveedor
from sheets import fetch_all

MAX_VUELTAS = 4  # tope de idas y venidas con herramientas, por si el modelo se atasca

PANELES = ["readiness", "hrv", "sueno", "carga", "fuerza", "peso", "correlaciones",
           "formularios"]

# El vocabulario sale del ESQUEMA para que no pueda divergir de lo que acepta la hoja.
ZONAS_DESC = ("Zonas separadas por coma, del vocabulario del formulario: "
              + ", ".join(formularios.ZONAS)
              + ". Si Hugo lo dice con sus palabras ('me duele el cuello'), mándalo tal "
                "cual: el backend lo traduce al vocabulario.")

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
    {
        "nombre": "estado_formularios",
        "descripcion": "Qué formularios ha rellenado Hugo y cuáles le faltan, con lo que "
                       "ya tiene puesto. Úsala cuando pregunte qué le falta, cuando "
                       "quieras recordárselo, y SIEMPRE antes de corregir algo.",
        "params": {"dias": {"type": "integer", "description": "Días atrás a mirar. Por defecto 14."}},
        "requeridos": [],
    },
]

HERRAMIENTAS_ESCRITURA = [
    {
        "nombre": "guardar_am",
        "descripcion": (
            "Guarda o CORRIGE el formulario de la MAÑANA. Manda SOLO los campos que Hugo "
            "haya dicho: lo que no mandes se queda como está, así que sirve igual para "
            "rellenarlo entero que para cambiar un solo número. "
            "ESCALAS: sueno_calidad, sensacion_am y animo van de 1 a 9 (5 = normal, "
            "9 = lo mejor); estres y molestias_nivel de 0 a 9 (0 = nada). Si te da una "
            "nota sobre 10, NO la conviertas tú: pregúntale sobre 9."
        ),
        "params": {
            "fecha": {"type": "string", "description": "AAAA-MM-DD. Por defecto hoy."},
            "hora_acostarse": {"type": "string", "description": "HH:MM, cuándo se metió en la cama"},
            "hora_despertar": {"type": "string", "description": "HH:MM, cuándo se levantó"},
            "sueno_calidad": {"type": "integer", "description": "1-9, qué tal durmió"},
            "sensacion_am": {"type": "integer", "description": "1-9, cómo se siente al levantarse"},
            "animo": {"type": "integer", "description": "1-9, de ánimo"},
            "estres": {"type": "integer", "description": "0-9, 0 = nada de estrés"},
            "molestias_nivel": {"type": "integer", "description": "0-9, 0 = sin molestias"},
            "molestias_zona": {"type": "string", "description": ZONAS_DESC},
            "cafeina_ayer_mg": {"type": "integer", "description": "mg de cafeína de AYER"},
            "cafeina_ayer_hora": {"type": "string", "description": "HH:MM de la última cafeína de ayer"},
            "alcohol_ayer": {"type": "integer", "description": "0-27, su escala personal"},
            "notas_am": {"type": "string", "description": "Texto libre, con SUS palabras, no las tuyas"},
        },
        "requeridos": [],
    },
    {
        "nombre": "guardar_pm",
        "descripcion": (
            "Guarda o CORRIGE el formulario de la TARDE. Manda solo lo que diga. "
            "ESCALAS: energia y sensacion_global van de 1 a 9 (5 = normal, 9 = lo mejor). "
            "OJO: rpd_sesion es el RPE del entreno y va de 0 a 10, escala DISTINTA. "
            "Sin rpd_sesion la sesión no cuenta para la carga, así que es el importante."
        ),
        "params": {
            "fecha": {"type": "string", "description": "AAAA-MM-DD. Por defecto hoy."},
            "energia": {"type": "integer", "description": "1-9, energía del día"},
            "sensacion_global": {"type": "integer", "description": "1-9, sensación al cerrar el día"},
            "cafeina_hoy_mg": {"type": "integer", "description": "mg de cafeína de HOY"},
            "cafeina_hoy_hora": {"type": "string", "description": "HH:MM de la última cafeína de hoy"},
            "rpd_sesion": {"type": "number", "description": "0-10, esfuerzo global del entreno"},
            "dolor_sesion_zona": {"type": "string", "description": ZONAS_DESC},
            "dolor_sesion_nota": {"type": "string", "description": "El dolor del entreno, con SUS palabras"},
            "notas_pm": {"type": "string", "description": "Texto libre, con SUS palabras"},
        },
        "requeridos": [],
    },
    {
        "nombre": "guardar_peso",
        "descripcion": "Apunta una pesada. Hugo se pesa en ayunas, más o menos una vez "
                       "por semana, así que no se lo persigas a diario.",
        "params": {
            "fecha": {"type": "string", "description": "AAAA-MM-DD. Por defecto hoy."},
            "peso_kg": {"type": "number", "description": "En kilos, p.ej. 81.8"},
        },
        "requeridos": ["peso_kg"],
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

HERRAMIENTAS_BACKEND = HERRAMIENTAS_LECTURA + HERRAMIENTAS_ESCRITURA
HERRAMIENTAS = HERRAMIENTAS_BACKEND + HERRAMIENTAS_UI
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


def _hoy() -> str:
    return date.today().isoformat()


def _tool_guardar(tipo: str, args: dict) -> dict:
    """Guarda o corrige un formulario. Devuelve también QUÉ FALTA todavía.

    Que la propia escritura diga lo que queda vacío es lo que hace que el relleno por voz
    quepa en un turno: Jarvis guarda lo que ha oído y ya sabe qué preguntar, sin gastar
    otra vuelta de MAX_VUELTAS.
    """
    fecha = str(args.get("fecha") or "").strip() or _hoy()
    valores = {k: v for k, v in args.items() if k != "fecha"}
    if not valores:
        return {"error": "no me has pasado ningún campo con valor"}
    try:
        res = formularios.guardar(tipo, fecha, valores)
    except ValueError as e:
        # El mensaje va en español y es el que Jarvis le repetirá a Hugo para re-preguntar.
        return {"error": str(e), "fecha": fecha}
    etiquetas = {c.nombre: c.etiqueta for c in formularios.ESQUEMA[tipo].campos}
    return {
        "guardado": res["guardado"],
        "fecha": res["fecha"],
        "asi_queda": res["valores"],
        "faltan": [etiquetas.get(n, n) for n in res["faltan"]],
        "avisos": res["avisos"],
    }


def _ejecutar_backend(llamada) -> str:
    """Ejecuta una herramienta de backend y devuelve su resultado como texto."""
    try:
        if llamada.nombre == "dia":
            res = _tool_dia(str(llamada.args.get("fecha", "")))
        elif llamada.nombre == "ejercicio":
            res = _tool_ejercicio(str(llamada.args.get("nombre", "")))
        elif llamada.nombre == "estado_formularios":
            res = huecos.estado(dias=int(llamada.args.get("dias") or 14))
        elif llamada.nombre in ("guardar_am", "guardar_pm", "guardar_peso"):
            res = _tool_guardar(llamada.nombre.removeprefix("guardar_"), llamada.args)
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


# --- muletilla ----------------------------------------------------------------

# Qué muletilla ("déjame que lo mire…") pega con lo que Hugo acaba de decir. Lo decide
# Haiku, no una regex: las palabras sueltas se equivocaban feo —"hoy me encuentro
# jodido" caía en 'consulta' por el "hoy" y le soltaba un "voy a mirar tus datos" a
# alguien que dice que está mal—. Haiku tarda ~1 s, corre EN PARALELO con la respuesta
# de verdad (no la retrasa) y cuesta ~0,00005 $ por mensaje.
_CLASIFICADOR = "claude-haiku-4-5-20251001"
# Corto a propósito: cada token de entrada y de salida se paga en latencia, y esto tiene
# que estar listo en ~1 s o no sirve para tapar nada.
_SIS_RUTA = """\
Eres Jarvis, colega de Hugo: sarcástico y cercano. Castellano de España (nada de "qué
onda", "ahorita" ni voseo). Hugo acaba de escribirte. Devuelve UNA línea:

- Si es un saludo, despedida, agradecimiento o reacción corta que NO necesita mirar sus
  datos de salud ni de entreno, contéstale tú, con gracia, en una frase:
      RESPUESTA: <lo que le dices>
  Si la frase va con retintín, márcala poniendo [sarcastic] delante (o [mischievously],
  [laughs], [curious]): es lo que hace que la voz lo diga con guasa y no en plano.
- Si pregunta por sus datos de salud o entreno (sueño, fuerza, peso, carga, un panel,
  una marca), o pide abrir algo del dashboard:
      CONSULTA
- Para cualquier otra cosa (charla, algo personal, cómo se siente):
      NEUTRA

Ej: "hola" -> RESPUESTA: [mischievously] Hombre, mira quién aparece.
Ej: "gracias tío" -> RESPUESTA: A mandar. Para eso estoy.
Ej: "¿qué tal he dormido?" -> CONSULTA
Ej: "ábreme el panel de fuerza" -> CONSULTA
Ej: "me duele el hombro" -> NEUTRA
Ej: "ayer estuve con mi hermano" -> NEUTRA
"""

# Un solo cliente para todo el proceso: crear uno por mensaje añadía el handshake TLS
# (~0,5 s) a algo que compite contra el reloj.
_cliente_rapido = None


def _cliente():
    global _cliente_rapido
    if _cliente_rapido is None:
        import anthropic

        _cliente_rapido = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _cliente_rapido


def enrutar(mensaje: str) -> dict:
    """Decide por dónde va el mensaje, ANTES de molestar a Sonnet. Devuelve
    `{"respuesta": str, "muletilla": str}`: o la contestación corta ya escrita, o qué
    pool de muletillas pega ('consulta' / 'neutra').

    La coletilla NO se escribe a medida aunque quedara más pegada al contexto: habría
    que sintetizarla en el momento y, en Flash (lo único rápido), sale plana y desentona
    con la ironía del resto. Pregrabadas se generan con v3 y suenan con retintín.

    Dos motivos para hacerlo primero y no en paralelo:
      1. Un "hola" no necesita a Sonnet ni el parte de estado entero: Haiku lo despacha
         en ~0,7 s en vez de los ~6 s que tardaba el camino largo.
      2. Lanzada a la vez que Sonnet, esta llamada pasaba de 0,7 s a 2,9 s (se pisan en
         el mismo proceso), y entonces la muletilla llegaba tarde para lo que sirve.

    Todo vacío = seguir por el camino normal sin coletilla. Es el fallo seguro."""
    try:
        r = _cliente().messages.create(
            model=_CLASIFICADOR, max_tokens=40, system=_SIS_RUTA,
            messages=[{"role": "user", "content": mensaje}],
        )
        t = r.content[0].text.strip()
        if t.upper().startswith("RESPUESTA:"):
            return {"respuesta": t.split(":", 1)[1].strip().strip('"'), "muletilla": ""}
        clase = t.strip().upper()
        if clase.startswith("CONSULTA"):
            return {"respuesta": "", "muletilla": "consulta"}
        if clase.startswith("NEUTRA"):
            return {"respuesta": "", "muletilla": "neutra"}
    except Exception:
        pass
    return {"respuesta": "", "muletilla": ""}


def responder_rapido(sesion: str, mensaje: str, respuesta: str) -> dict:
    """Cierra el turno corto: guarda el intercambio en el hilo para que la conversación
    siga siendo coherente aunque no haya pasado por Sonnet."""
    memoria.init()
    memoria.guardar_mensaje(sesion, "usuario", mensaje)
    memoria.guardar_mensaje(sesion, "jarvis", respuesta)
    return {"texto": respuesta, "acciones": [], "uso": {}}


# --- el ciclo de conversación ------------------------------------------------

def responder(sesion: str, mensaje: str, forzar_proveedor: str | None = None,
              al_texto=None) -> dict:
    """Un turno completo: guarda, pregunta al modelo, ejecuta herramientas, devuelve.

    Si se pasa `al_texto`, se le van entregando los trozos según el modelo escribe, para
    que el navegador pueda empezar a leer en alto la primera frase sin esperar al final
    (lo que se tarda en contestar lo marca la longitud de la respuesta)."""
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
        # Ollama y el proveedor falso no tienen streaming: se emite su texto de una vez,
        # así el frontend funciona igual con cualquiera de los tres.
        if al_texto and hasattr(prov, "responder_stream"):
            r = prov.responder_stream(sistema, mensajes, HERRAMIENTAS, al_texto)
        else:
            r = prov.responder(sistema, mensajes, HERRAMIENTAS)
            if al_texto and r.texto:
                al_texto(r.texto)
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
                "content": f"[resultado de {ll.nombre}({args})]: {_ejecutar_backend(ll)}",
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
