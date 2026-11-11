"""Escritura de los formularios diarios (AM, PM, peso) en la hoja.

Hasta ahora los datos solo entraban por Google Forms. Este módulo permite escribirlos
—y CORREGIRLOS— desde la app, en las MISMAS pestañas (`wellness_am`, `wellness_pm`,
`peso`), para que el pipeline, el briefing y los paneles sigan funcionando sin cambios
y el histórico quede unificado con lo que ya escriben los Forms.

Dos decisiones que conviene entender antes de tocar nada:

**Upsert por fecha, no append.** Hugo quiere poder corregir lo que ya metió ("puse RPE 6
y en verdad era 7"). Si añadiéramos una fila nueva por corrección, el valor vigente sería
ambiguo al releer para precargar el editor. Así que si ya hay fila para esa fecha se
actualiza en su sitio, y solo las celdas de los campos recibidos: una corrección parcial
desde la voz no puede borrar lo que ya había.

**No se usa `write_tab` de status_pipeline.py**: hace clear() + reescritura completa de la
pestaña. Sobre `wellness_am` sería destructivo.

Las escalas salen de la pestaña "Léeme" de la propia hoja y NO son 1-10. Validarlas es
obligatorio, no cosmético: `readiness` (status_pipeline.py) divide entre 9, así que un 10
colado en una bipolar da un readiness por encima de 100 sin que nadie se entere.
"""
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

import sheets

ROOT = Path(__file__).resolve().parents[2]

# El vocabulario de zonas vive en el pipeline y es el mismo que usa el form AM. Se importa
# en vez de copiarlo para que no puedan divergir; por eso hace falta meter la raíz en el
# path (el backend se ejecuta con cwd en dashboard/backend/).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from entreno_pipeline import ZONE_KEYWORDS  # noqa: E402

ZONAS = sorted(ZONE_KEYWORDS)

# Scope de ESCRITURA. El mismo service account ya escribe la hoja desde el pipeline; el
# cliente de sheets.py es readonly a propósito y se deja como está.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_HORA = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


@dataclass
class Campo:
    """Un campo del formulario. `tipo` decide cómo se valida y cómo lo pinta la UI."""
    nombre: str
    etiqueta: str
    tipo: str                  # entero | decimal | hora | texto | zonas
    minimo: float | None = None
    maximo: float | None = None
    ayuda: str = ""
    # Salto de la rueda (el selector tipo Zepp). Si está puesto, la UI pinta una rueda
    # en vez de una caja de texto: no se puede escribir un valor fuera de formato y se
    # mete de un gesto. Va aquí y no en el frontend por lo mismo que los rangos: la
    # escala la define el backend, o acaban divergiendo.
    paso: float | None = None


@dataclass
class Formulario:
    tipo: str
    pestana: str
    titulo: str
    campos: list[Campo] = field(default_factory=list)

    def campo(self, nombre: str) -> Campo | None:
        return next((c for c in self.campos if c.nombre == nombre), None)


# Escalas de la pestaña "Léeme" de la hoja:
#   bipolares (centro=normal) 1-9, 5=normal, 9=mejor  -> sueño, ánimo, energía, sensación
#   unipolares (0=nada)       0-9, 9=máximo           -> estrés, molestias
#   alcohol 0-27 (escala personal de Hugo), rpd_sesion 0-10
_BIP = dict(tipo="entero", minimo=1, maximo=9, ayuda="1 a 9 · 5 = normal, 9 = mejor")
_UNI = dict(tipo="entero", minimo=0, maximo=9, ayuda="0 a 9 · 0 = nada, 9 = máximo")

ESQUEMA: dict[str, Formulario] = {
    "am": Formulario("am", "wellness_am", "Formulario AM", [
        Campo("hora_acostarse", "¿A qué hora te acostaste?", "hora", ayuda="HH:MM"),
        Campo("hora_despertar", "¿A qué hora te levantaste?", "hora", ayuda="HH:MM"),
        Campo("sueno_calidad", "Calidad del sueño", **_BIP),
        Campo("sensacion_am", "Sensación al despertar", **_BIP),
        Campo("animo", "Ánimo", **_BIP),
        Campo("estres", "Estrés", **_UNI),
        Campo("molestias_nivel", "Nivel de molestias", **_UNI),
        Campo("molestias_zona", "Zonas con molestias", "zonas"),
        # La cafeína se pregunta SOLO en el PM, el día que se la toma. Aquí se preguntaba
        # también (como "la de ayer") porque afecta al sueño de esa noche, pero era
        # rellenar lo mismo dos veces. Esa relación la resuelve ahora el pipeline:
        # `derived_diario.cafeina_ayer_mg` se calcula desplazando la del PM un día.
        # El alcohol sí se queda: lo bebe después de las 12 y le pega al día siguiente,
        # así que apuntarlo a la mañana siguiente es lo correcto.
        Campo("alcohol_ayer", "Alcohol de ayer", "entero", 0, 27, "0 a 27 · 0 = nada"),
        Campo("notas_am", "Notas de la mañana", "texto"),
    ]),
    "pm": Formulario("pm", "wellness_pm", "Formulario PM", [
        Campo("energia", "Energía del día", **_BIP),
        Campo("sensacion_global", "Sensación global del día", **_BIP),
        Campo("cafeina_hoy_mg", "Cafeína (mg)", "entero", 0, 2000, paso=50),
        Campo("cafeina_hoy_hora", "Hora de la última cafeína", "hora", ayuda="HH:MM"),
        # Sin esto no hay carga: sRPE_series no se calcula y la sesión entera se cae fuera.
        Campo("rpd_sesion", "RPE de la sesión", "decimal", 0, 10, "0 a 10 · esfuerzo del entreno"),
        Campo("dolor_sesion_zona", "Zonas con dolor en el entreno", "zonas"),
        Campo("dolor_sesion_nota", "Dolor de entreno (descripción)", "texto"),
        Campo("notas_pm", "Notas de la tarde", "texto"),
    ]),
    "peso": Formulario("peso", "peso", "Peso", [
        Campo("peso_kg", "Peso (kg)", "decimal", 30, 300, "en ayunas", paso=0.1),
    ]),
}


def esquema_publico() -> dict:
    """El ESQUEMA en JSON, para que la UI pinte los campos sin duplicar rangos."""
    return {
        t: {
            "titulo": f.titulo,
            "campos": [vars(c) for c in f.campos],
        }
        for t, f in ESQUEMA.items()
    } | {"zonas": ZONAS}


# --- validación ---------------------------------------------------------------

def normalizar_zonas(texto: str) -> str:
    """Texto libre -> vocabulario controlado, separado por ', ' como en la hoja.

    Sirve sobre todo para la voz: Hugo dice "me duele el cuello y la lumbar" y hay que
    dejarlo escrito exactamente como lo escribiría el desplegable del formulario, o el
    dato no casaría con los 63 registros que ya hay.
    """
    if not texto:
        return ""
    # Si ya vienen zonas canónicas (de la UI, separadas por comas), respetarlas.
    partes = [p.strip() for p in str(texto).split(",") if p.strip()]
    if partes and all(p in ZONAS for p in partes):
        return ", ".join(dict.fromkeys(partes))
    low = str(texto).lower()
    zonas = [z for z, kws in ZONE_KEYWORDS.items() if any(k in low for k in kws)]
    return ", ".join(zonas)


def validar(tipo: str, valores: dict) -> tuple[dict, list[str], list[str]]:
    """Devuelve (valores limpios, errores en español, avisos en español).

    Los rangos salen del ESQUEMA, que es la única fuente: si algún día cambian las
    escalas se tocan ahí y la UI, la API y las herramientas de Jarvis quedan alineadas.

    La diferencia entre error y aviso: el error tumba el guardado entero, el aviso deja
    pasar el resto. Una zona que no está en el vocabulario no puede tirar abajo la
    energía y el RPE que Hugo ha dictado en la misma frase.
    """
    form = ESQUEMA.get(tipo)
    if form is None:
        return {}, [f"No existe el formulario '{tipo}'. Son: {', '.join(ESQUEMA)}."], []

    limpios: dict = {}
    errores: list[str] = []
    avisos: list[str] = []
    for nombre, bruto in valores.items():
        if nombre == "fecha":
            continue
        campo = form.campo(nombre)
        if campo is None:
            errores.append(f"'{nombre}' no es un campo del formulario {tipo.upper()}.")
            continue
        if bruto is None or str(bruto).strip() == "":
            continue  # campo no contestado: no se toca lo que hubiera

        crudo = str(bruto).strip()
        if campo.tipo == "texto":
            limpios[nombre] = crudo
        elif campo.tipo == "zonas":
            zonas = normalizar_zonas(crudo)
            if zonas:
                limpios[nombre] = zonas
            else:
                # Antes esto entraba como cadena vacía: la zona se perdía Y borraba lo que
                # hubiera en la celda, sin error ni rastro en el log. Peor todavía, la
                # herramienta le devolvía a Jarvis un "así queda" que contradecía lo que él
                # acababa de mandar, y lo leía como que había fallado el sistema.
                # Ahora no se toca la celda y se dice qué palabra no se ha entendido: la
                # zona más parecida la propone Jarvis, que para eso sabe de anatomía.
                avisos.append(
                    f"{campo.etiqueta}: no reconozco '{crudo}', así que ese campo se ha "
                    f"quedado como estaba. Las zonas válidas son: {', '.join(ZONAS)}."
                )
        elif campo.tipo == "hora":
            m = _HORA.match(crudo)
            if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
                errores.append(f"{campo.etiqueta}: '{crudo}' no es una hora válida (HH:MM).")
            else:
                limpios[nombre] = f"{int(m.group(1)):02d}:{m.group(2)}"
        else:
            try:
                num = float(crudo.replace(",", "."))
            except ValueError:
                errores.append(f"{campo.etiqueta}: '{crudo}' no es un número.")
                continue
            if campo.tipo == "entero" and num != int(num):
                errores.append(f"{campo.etiqueta}: tiene que ser un número entero.")
                continue
            if campo.minimo is not None and num < campo.minimo:
                errores.append(f"{campo.etiqueta}: {crudo} se sale de la escala ({campo.ayuda or f'{campo.minimo} a {campo.maximo}'}).")
                continue
            if campo.maximo is not None and num > campo.maximo:
                errores.append(f"{campo.etiqueta}: {crudo} se sale de la escala ({campo.ayuda or f'{campo.minimo} a {campo.maximo}'}).")
                continue
            limpios[nombre] = int(num) if campo.tipo == "entero" else num
    return limpios, errores, avisos


def _fecha_valida(fecha: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(fecha or "").strip()))


# --- acceso a la hoja ---------------------------------------------------------

_cliente = None
_lock = threading.Lock()  # FastAPI atiende en varios hilos: dos guardados del mismo día se pisarían


def cliente():
    global _cliente
    if _cliente is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SA_JSON"], scopes=SCOPES
        )
        _cliente = gspread.authorize(creds)
    return _cliente


def _hoja(tipo: str):
    form = ESQUEMA[tipo]
    sh = cliente().open_by_key(os.environ["SHEET_ID"])
    return sh.worksheet(form.pestana)


def leer(tipo: str, fecha: str) -> dict:
    """Lo que ya hay guardado de ese día (para precargar el editor). {} si no hay fila."""
    if tipo not in ESQUEMA:
        return {}
    filas = sheets.fetch_all().get(ESQUEMA[tipo].pestana, [])
    # La última gana, igual que hace consolidate() en el pipeline.
    encontrada = {}
    for f in filas:
        if str(f.get("fecha", ""))[:10] == fecha:
            encontrada = f
    return {k: v for k, v in encontrada.items() if str(v).strip() != ""}


def sugerencias(tipo: str, fecha: str) -> dict:
    """El último valor conocido de cada campo numérico ANTES de esa fecha.

    Es donde arranca la rueda: Hugo pesa 79,8 y a la semana siguiente 79,9, así que
    empezar en su último peso le ahorra casi todo el giro.

    NO es un valor guardado ni se guarda solo: la UI lo usa como punto de partida y solo
    lo manda si él toca la rueda. Si se enviara sin tocarla, darle a Guardar sin pesarse
    apuntaría el peso de la semana pasada como el de hoy.
    """
    if tipo not in ESQUEMA:
        return {}
    numericos = [c.nombre for c in ESQUEMA[tipo].campos
                 if c.tipo in ("entero", "decimal", "hora")]
    filas = sheets.fetch_all().get(ESQUEMA[tipo].pestana, [])
    previas = sorted((f for f in filas if str(f.get("fecha", ""))[:10] < fecha),
                     key=lambda f: str(f.get("fecha", ""))[:10])
    ultimos: dict = {}
    for f in previas:                     # en orden: la fila más reciente es la que manda
        for n in numericos:
            if str(f.get(n, "")).strip() != "":
                ultimos[n] = f[n]
    return ultimos


def guardar(tipo: str, fecha: str, valores: dict, borrar=()) -> dict:
    """Upsert por fecha. Devuelve lo guardado y qué campos siguen sin contestar.

    `borrar` son los campos que hay que VACIAR, por su nombre. Van aparte de `valores` y
    NO como un valor vacío, a propósito: en estos formularios un campo vacío significa
    "no lo he contestado, deja lo que hubiera" —es lo que permite corregir un solo número
    sin reenviar el día entero—, así que si las dos cosas viajaran igual, mandar un campo
    sin rellenar borraría lo que ya había. Quien borra tiene que decir qué borra.
    """
    if tipo not in ESQUEMA:
        raise ValueError(f"No existe el formulario '{tipo}'. Son: {', '.join(ESQUEMA)}.")
    if not _fecha_valida(fecha):
        raise ValueError(f"La fecha '{fecha}' no tiene el formato AAAA-MM-DD.")

    limpios, errores, avisos_val = validar(tipo, valores)
    if errores:
        raise ValueError(" ".join(errores))

    conocidos = {c.nombre for c in ESQUEMA[tipo].campos}
    a_vaciar = [n for n in dict.fromkeys(borrar or ()) if n != "fecha"]
    if [n for n in a_vaciar if n not in conocidos]:
        malos = ", ".join(n for n in a_vaciar if n not in conocidos)
        raise ValueError(f"No puedo borrar {malos}: no son campos del formulario {tipo.upper()}.")
    if not limpios and not a_vaciar:
        # Si lo ÚNICO que mandó era una zona que no se entiende, decir "no has mandado
        # ningún campo" despistaría: lo mandó, no se reconoció. Que se vea el motivo.
        raise ValueError(" ".join(avisos_val) if avisos_val
                         else "No has mandado ningún campo con valor.")

    coincidencias: list[int] = []
    with _lock:
        ws = _hoja(tipo)
        cabeceras = ws.row_values(1)
        if "fecha" not in cabeceras:
            raise RuntimeError(f"La pestaña '{ESQUEMA[tipo].pestana}' no tiene columna 'fecha'.")
        col_fecha = cabeceras.index("fecha") + 1

        # Buscar la fila del día. La última coincidencia, por si el histórico traía alguna
        # repetida de antes de que existiera el upsert.
        columna = ws.col_values(col_fecha)
        coincidencias[:] = [i for i, v in enumerate(columna[1:], start=2)
                            if str(v).strip()[:10] == fecha]
        fila_idx = coincidencias[-1] if coincidencias else None

        desconocidos = [c for c in list(limpios) + a_vaciar if c not in cabeceras]
        if desconocidos:
            raise RuntimeError(
                f"La pestaña '{ESQUEMA[tipo].pestana}' no tiene columna(s): {', '.join(desconocidos)}."
            )

        # Las columnas de fecha y hora de la hoja NO son texto: guardan valores numéricos
        # (46258 = 2026-08-24, 0.9722 = 23:20) que se ven bien por el formato de la
        # columna. Por eso van con USER_ENTERED, igual que las escribe el Apps Script de
        # los Forms; con RAW quedarían como texto y la columna acabaría mixta.
        # El texto libre va al revés: con USER_ENTERED, una nota que empiece por "=" o "+"
        # se convertiría en fórmula. De ahí las dos escrituras separadas.
        es_texto = {c.nombre for c in ESQUEMA[tipo].campos if c.tipo in ("texto", "zonas")}
        crudos = {n: v for n, v in limpios.items() if n in es_texto}
        calculados = {n: v for n, v in limpios.items() if n not in es_texto}
        # Vaciar es escribir la celda en blanco, y eso va con RAW sea del tipo que sea.
        # Si no hay fila de ese día no hay nada que borrar: se ignora en vez de crear una
        # fila vacía, que es justo el "día que no existe" que se quiere quitar de en medio.
        if fila_idx is not None:
            crudos = crudos | {n: "" for n in a_vaciar}
            calculados = {n: v for n, v in calculados.items() if n not in a_vaciar}

        def _celda(fila: int, nombre: str) -> str:
            return gspread.utils.rowcol_to_a1(fila, cabeceras.index(nombre) + 1)

        if fila_idx is None and not limpios:
            # Solo había borrados y ese día no tiene fila: no hay nada que vaciar, y
            # crear una fila en blanco sería inventarse justo el día que se quiere
            # quitar de en medio.
            creada = False
        elif fila_idx is None:
            nueva = [""] * len(cabeceras)
            nueva[col_fecha - 1] = fecha
            for nombre, val in calculados.items():
                nueva[cabeceras.index(nombre)] = val
            resp = ws.append_row(nueva, value_input_option="USER_ENTERED",
                                 table_range="A1")
            # El texto se escribe aparte, sobre la fila que Google acaba de asignar.
            if crudos:
                rango = resp["updates"]["updatedRange"]
                fila_nueva = int("".join(ch for ch in rango.split("!")[-1].split(":")[0]
                                        if ch.isdigit()))
                ws.batch_update(
                    [{"range": _celda(fila_nueva, n), "values": [[v]]} for n, v in crudos.items()],
                    value_input_option="RAW")
            creada = True
        else:
            if calculados:
                ws.batch_update(
                    [{"range": _celda(fila_idx, n), "values": [[v]]} for n, v in calculados.items()],
                    value_input_option="USER_ENTERED")
            if crudos:
                ws.batch_update(
                    [{"range": _celda(fila_idx, n), "values": [[v]]} for n, v in crudos.items()],
                    value_input_option="RAW")
            creada = False

    # Sin esto el semáforo y el editor seguirían viendo el estado anterior hasta 300s.
    sheets.invalidar(ESQUEMA[tipo].pestana)

    actual = leer(tipo, fecha)
    faltan = [c.nombre for c in ESQUEMA[tipo].campos
              if str(actual.get(c.nombre, "")).strip() == ""]
    avisos = list(avisos_val)
    if len(coincidencias) > 1:
        # Ya hay duplicados de antes en la hoja (wellness_am 2026-06-25 y 2026-08-04,
        # peso 2026-08-11). Se edita la ÚLTIMA porque es la que gana en consolidate(),
        # pero callárselo sería esconder que ese día está raro.
        avisos.append(f"Hay {len(coincidencias)} filas para el {fecha}; he editado la "
                      "última, que es la que manda en el pipeline.")
    return {"tipo": tipo, "fecha": fecha, "creada": creada, "guardado": limpios,
            "faltan": faltan, "avisos": avisos}
