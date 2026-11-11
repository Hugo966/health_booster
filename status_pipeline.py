#!/usr/bin/env python3
"""
status_pipeline.py — Consolidador del dashboard de estado personal.

Une las 5 fuentes y las escribe en la hoja hub (Health_booster_data):
  1. Intervals.icu  -> pestaña `objetivo` (HRV rMSSD, FC reposo, sueño, pasos)
                       + duraciones de sesión (para sRPE)
  2. Keep + Excel    -> `entreno_sets` (vía entreno_pipeline) + `entreno_sesion`
  3. Hub (gspread)   -> lee `wellness_am`, `wellness_pm`, `peso`
  4. entreno_sesion  -> `rm1` (mejor e1RM por semana, derivado)
  5. Consolidación   -> `derived_diario` (readiness, sRPE, lags, ACWR, delta_am_pm)

Solo ESCRIBE en: objetivo, entreno_sets, entreno_sesion, rm1, derived_diario.
NUNCA toca wellness_am / wellness_pm / peso (esas las llenan los Forms / tú).

Credenciales: se leen de un .env (ver .env.example). No hay secretos en el código.
Uso:
    pip install -r requirements.txt
    python3 status_pipeline.py            # últimos 120 días
    python3 status_pipeline.py --since 2026-06-01
"""
import os, re, sys, time, argparse, datetime as dt
import requests
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread

import entreno_pipeline as ep   # el parser que ya validamos

# La consola de Windows va en cp1252 y los símbolos de los mensajes (✓, …) la revientan
# con UnicodeEncodeError. No es cosmético: petaba en el print del PRIMER write_tab, así
# que las 4 pestañas siguientes —derived_diario incluida— no llegaban a escribirse y los
# datos se quedaban congelados sin más aviso que un traceback al final.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()
API_KEY  = os.getenv("INTERVALS_API_KEY")
ATHLETE  = os.getenv("INTERVALS_ATHLETE_ID")
SA_JSON  = os.getenv("GOOGLE_SA_JSON")
SHEET_ID = os.getenv("SHEET_ID")
KEEP_TXT = os.getenv("KEEP_TXT")
DRIVE_EXCEL_ID = os.getenv("DRIVE_EXCEL_ID")   # Hoja de Google "Hugo the GOAT" (plan de entreno)
INTERVALS = "https://intervals.icu/api/v1"

# ----------------------------------------------------------------------------
# 1. INTERVALS
# ----------------------------------------------------------------------------
def intervals_get(path, params=None):
    r = requests.get(f"{INTERVALS}{path}", params=params, auth=("API_KEY", API_KEY), timeout=30)
    r.raise_for_status()
    return r.json()

# POR QUÉ HAY QUE ESPERAR TANTO (y por qué antes "había que ejecutarlo dos veces"):
# Intervals no guarda el HRV al momento — lo va a buscar al proveedor (Zepp) de forma
# PEREZOSA, cuando alguien refresca su web. Una petición a la API dispara esa
# sincronización pero devuelve lo que había: los datos aparecen minutos después. Está
# reportado en su foro (t/hrv-not-available-from-the-api-without-ui-refresh/128220) y
# NO hay endpoint público para forzarla, así que la única vía es esperar y reintentar.
#
# De ahí el presupuesto de ~5 minutos con esperas crecientes: con los 3 intentos de 8 s
# de antes (24 s en total) casi nunca llegaba, y hacía falta una segunda ejecución.
# El refetch es siempre igual o mejor: Intervals solo añade datos, no los borra.
#
# OJO: el HRV del propio día NO llega nunca (va con un día de retraso, es normal). Por
# eso lo que se espera es el de AYER; ver _falta_hrv_de_ayer.
# La primera espera es de UN MINUTO, no de unos segundos: la sincronización de Intervals
# nunca aterriza en 20 s, así que reintentar antes solo gasta peticiones y da un falso
# "sigue sin datos". Mejor esperar de verdad la primera vez y crecer desde ahí.
INTERVALS_REINTENTOS = int(os.getenv("INTERVALS_REINTENTOS", "6"))
INTERVALS_ESPERA_S = int(os.getenv("INTERVALS_ESPERA_S", "60"))        # primera espera
INTERVALS_ESPERA_MAX_S = int(os.getenv("INTERVALS_ESPERA_MAX_S", "300"))  # tope total

def _wellness_once(oldest, newest):
    data = intervals_get(f"/athlete/{ATHLETE}/wellness",
                         {"oldest": oldest, "newest": newest})
    rows = []
    for d in data:
        secs = d.get("sleepSecs")
        rows.append(dict(
            fecha       = d.get("id"),
            hrv_rmssd   = d.get("hrv"),
            fc_reposo   = d.get("restingHR"),
            sueno_horas = round(secs/3600, 2) if secs else None,
            sueno_score = d.get("sleepScore"),
            pasos       = d.get("steps"),
            # Cuándo dice Intervals que tocó esa fila. Es el único dato que distingue
            # "el reloj aún no ha subido la noche" de "nos ha servido una respuesta
            # cacheada": si `updated` es viejo, el dato no existe; si es reciente pero
            # no lo vemos, es que nos han dado caché. Ver _diag() y el aviso de abajo.
            _updated    = d.get("updated"),
        ))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[df["fecha"].notna()].sort_values("fecha").reset_index(drop=True)

def _falta_hrv_de_ayer(df):
    """True si el día más reciente ANTERIOR a hoy no tiene HRV (debería tenerlo)."""
    if df.empty:
        return False
    prev = df[df["fecha"] < str(dt.date.today())]
    return not prev.empty and pd.isna(prev.iloc[-1]["hrv_rmssd"])

def _diag(df):
    """Resumen de una respuesta de Intervals: hasta dónde llega el HRV y cuándo dice la
    propia API que se tocaron esas filas."""
    if df.empty:
        return "sin filas"
    con = df[df["hrv_rmssd"].notna()]
    ult = con.iloc[-1]["fecha"] if not con.empty else "(ninguna)"
    upd = str(df["_updated"].dropna().max())[:19] if "_updated" in df else "?"
    return f"HRV hasta {ult} | updated más reciente {upd}"


def fetch_objetivo(oldest, newest):
    """Wellness diario: HRV rMSSD, FC reposo, sueño, pasos. Reintenta si Intervals
    aún no ha rellenado el HRV de ayer (ver INTERVALS_REINTENTOS).

    Hugo tiene la sensación de que "siempre hay que ejecutarlo dos veces". Por eso cada
    intento imprime hasta dónde llega el HRV y el `updated` más reciente: si en el primer
    intento el `updated` ya es de hace horas pero el HRV no aparece, es que la API nos
    está sirviendo caché (y entonces habría que atacar eso). Si el `updated` va cambiando
    entre intentos, es el reloj subiendo tarde y no hay nada que arreglar."""
    df = _wellness_once(oldest, newest)
    print(f"   [intervals] intento 1: {_diag(df)}")

    # Esta primera petición es la que dispara la sincronización de Intervals con el
    # proveedor. A partir de aquí solo cabe esperar a que aterrice, con esperas cada vez
    # más largas para no machacar la API (su límite es 2500 peticiones/15 min).
    espera, gastado = INTERVALS_ESPERA_S, 0
    for intento in range(2, INTERVALS_REINTENTOS + 2):
        if not _falta_hrv_de_ayer(df):
            break
        if gastado + espera > INTERVALS_ESPERA_MAX_S:
            break
        ultimo = df[df["fecha"] < str(dt.date.today())].iloc[-1]["fecha"]
        print(f"   (HRV de {ultimo} aún vacío. Su sincronización es perezosa y la "
              f"acabamos de disparar: esperando {espera}s…)")
        time.sleep(espera)
        gastado += espera
        df = _wellness_once(oldest, newest)
        print(f"   [intervals] intento {intento} (t+{gastado}s): {_diag(df)}")
        espera = min(int(espera * 1.6), 120)

    if _falta_hrv_de_ayer(df):
        print(f"   (Tras {gastado}s sigue sin HRV de ayer. Aquí ya no es la caché: el "
              f"reloj no ha subido la noche todavía. Reejecuta más tarde.)")
    return df.drop(columns=["_updated"], errors="ignore")

# Una actividad de Intervals con tiempo 0 = Hugo olvidó registrarla en Zepp: la sesión
# ocurrió, pero llegó sin duración. Asumimos una sesión media (2 h) en vez de un 0, que
# se colaría como carga nula y reventaría el sRPE de ese día (y sus correlaciones). El
# gimnasio no lleva GPS, así que estos ceros son habituales; 2 h es una media razonable.
DURACION_DEFECTO_MIN = 120.0

def fetch_duraciones(oldest, newest):
    """Minutos de entreno por fecha (para sRPE), sumando actividades del día. Las
    actividades con tiempo 0 (registro olvidado) se asumen de DURACION_DEFECTO_MIN,
    pero solo si ese día no hay ninguna otra con duración real (no se suma encima)."""
    try:
        acts = intervals_get(f"/athlete/{ATHLETE}/activities",
                            {"oldest": oldest, "newest": newest})
    except Exception as e:
        print(f"  (aviso) no pude leer actividades: {e}")
        return pd.DataFrame(columns=["fecha", "duracion_min"])
    reales = {}         # fecha -> minutos reales sumados
    solo_cero = set()   # fechas con actividad, pero de tiempo 0
    for a in acts:
        start = (a.get("start_date_local") or "")[:10]
        if not start:
            continue
        secs = a.get("moving_time") or a.get("elapsed_time") or 0
        if secs:
            reales[start] = reales.get(start, 0.0) + secs / 60.0
        else:
            solo_cero.add(start)
    for f in solo_cero:
        reales.setdefault(f, DURACION_DEFECTO_MIN)   # solo si ese día no hubo duración real
    if not reales:
        return pd.DataFrame(columns=["fecha", "duracion_min"])
    return pd.DataFrame(sorted(reales.items()), columns=["fecha", "duracion_min"]).round(1)

# ----------------------------------------------------------------------------
# 2. ENTRENO  (Keep + Excel -> sets -> sesión)
# ----------------------------------------------------------------------------
# El plan de todos los bloques vive en un único archivo de Drive (Hoja de Google
# "Hugo the GOAT"). Se lee la columna A de cada pestaña vía gspread (la exportación
# a .xlsx falla por el límite de 10 MB de la API de Drive, y no hace falta el resto).
# El reparto pestaña -> (bloque, semana) está en ep.TAB_ROUTE.

# Pestaña del hub donde viven las pestañas del plan que no se pudieron enrutar solas.
# Es una ENTRADA, no una salida: el pipeline solo añade filas a medias (el nombre, sin
# números) y quien las completa es Hugo contestándole a Jarvis. Por eso se escribe con
# `append_row` y nunca con `write_tab`, que borra la pestaña entera antes de escribir.
TAB_RUTAS = "plan_pestanas"


def rutas_manuales(sh_hub):
    """{clave_de_pestaña: (plani, bloque, semana)} con lo que Hugo ya contestó."""
    df = read_tab(sh_hub, TAB_RUTAS)
    out = {}
    for r in (df.to_dict("records") if not df.empty else []):
        titulo = str(r.get("pestana", "")).strip()
        if not titulo:
            continue
        try:
            out[ep._key(titulo)] = (int(r["plani"]), int(r["bloque"]), str(int(r["semana"])))
        except (KeyError, TypeError, ValueError):
            continue   # fila a medias: es justo la que está esperando respuesta
    return out


def anotar_pendientes(sh_hub, pendientes):
    """Deja apuntada la pestaña que no se puede enrutar, para que Jarvis pregunte."""
    if not pendientes:
        return
    try:
        ws = sh_hub.worksheet(TAB_RUTAS)
    except gspread.WorksheetNotFound:
        ws = sh_hub.add_worksheet(title=TAB_RUTAS, rows=200, cols=4)
        ws.update([["pestana", "plani", "bloque", "semana"]], value_input_option="USER_ENTERED")
    ya = {str(v).strip() for v in ws.col_values(1)[1:]}
    for titulo in pendientes:
        if titulo not in ya:
            ws.append_row([titulo, "", "", ""], value_input_option="USER_ENTERED")
            print(f"  [Plan] pestaña sin enrutar anotada para preguntar: '{titulo}'")


def drive_lookups():
    """Lee el plan de entreno desde Drive -> {(plani, bloque): lookup_de_ejercicios}."""
    if not DRIVE_EXCEL_ID:
        return {}
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(DRIVE_EXCEL_ID)
    sheets, fallidas = [], []
    for ws in sh.worksheets():
        # Un fallo aquí NO es lo mismo que una pestaña de gráfico sin columna A: la API de
        # Google devuelve errores transitorios (429 y compañía) cada dos por tres. Antes los
        # dos casos caían en el mismo `except: continue`, así que una pestaña de plan podía
        # esfumarse en silencio y sus sesiones se escribían en la hoja SIN nombre de
        # ejercicio, sin `tipo` y fuera de vol_basicos/vol_accesorios y de rm1. Medido: 2 de
        # cada 7 lecturas devolvían el plan incompleto. Se reintenta, y lo que siga fallando
        # se anota para decidir abajo si importa.
        # Espera creciente (3, 6, 12, 24 s): lo que falla suele ser el límite de cuota de
        # Google, y ese no se pasa en dos segundos. Son ~45 s en el peor caso y solo cuando
        # algo va mal; el camino bueno no espera nada.
        col = None
        for intento in range(5):
            try:
                col = ws.col_values(1)
                break
            except Exception:
                if intento < 4:
                    time.sleep(3 * 2 ** intento)
        if col is None:
            fallidas.append(ws.title)
            continue
        sheets.append((ws.title, col))

    # Si lo que se perdió era una pestaña de PLAN, los datos saldrían degradados sin que
    # nadie se entere. Mejor reventar aquí que escribir una hoja a medias.
    # Una pestaña que acaba en número puede ser una etapa nueva (`ep.rutas_automaticas`),
    # y eso no se puede comprobar aquí porque justo lo que falló fue leer su columna A.
    # Ante la duda cuenta como plan: perder una semana entera en silencio es peor que
    # abortar de más.
    plan_perdidas = [t for t in fallidas if ep.route_tab(t) or re.search(r'\d\s*$', t)]
    if plan_perdidas:
        raise RuntimeError(
            "Drive no ha devuelto pestañas del plan tras 5 intentos: "
            f"{', '.join(plan_perdidas)}. Sus sesiones se escribirían sin nombre de "
            "ejercicio, así que se aborta. Reintenta en un rato."
        )
    if fallidas:
        print(f"  (aviso) pestañas sin columna A, ignoradas: {', '.join(fallidas)}")
    # Lo que Hugo haya contestado sobre pestañas raras manda sobre la deducción; lo que
    # sigue sin poder resolverse se apunta para que Jarvis se lo pregunte.
    hub = open_sheet()
    manual = rutas_manuales(hub)
    _, pendientes = ep.rutas_automaticas(sheets, manual)
    anotar_pendientes(hub, pendientes)
    return ep.extract_exercises(sheets, verbose=True, manual=manual)

def build_entreno():
    # El keep sale de Drive si hay KEEP_DOC_ID, y si no del disco. En la VM no hay
    # fichero local, y entre las dos máquinas de Hugo el fichero se desincronizaba.
    keep = ep.leer_keep()
    if not keep.strip():
        print("  (aviso) keep vacío o no encontrado (ni KEEP_DOC_ID ni KEEP_TXT); salto entreno.")
        return pd.DataFrame(), pd.DataFrame()
    if not DRIVE_EXCEL_ID:
        print("  (aviso) DRIVE_EXCEL_ID no definido en .env; los sets saldrán sin nombres.")
    lookups = ep.apply_basic_swaps(drive_lookups())
    sets = ep.parse_keep(keep, lookups)
    # sesión: solo sesiones con fecha (las que pueden cruzarse con el resto)
    dated = sets[sets["fecha"].astype(str).str.len() == 10].copy()
    if dated.empty:
        return sets, pd.DataFrame()
    def agg(g):
        vb = g.loc[g["tipo"] == "básico", "volumen"].sum(min_count=1)
        va = g.loc[g["tipo"] == "accesorio", "volumen"].sum(min_count=1)
        # Series falladas (0 reps) de la sesión. El frontend las pondera aparte en la
        # carga (un fallo es esfuerzo máximo y fatiga mucho más que una serie normal).
        nfallos = g.loc[g["flag"].astype(str).str.contains("fallo", na=False), "n_series"].sum(min_count=1)
        # Series con `@?`/`RIR?`: Hugo levantó el peso pero no pudo valorar el esfuerzo
        # (dolor, lesión, ir contra el reloj). Se cuentan aparte de los fallos y de la
        # basura de tecleo (`int_no_parseable`) porque son la señal de que la sesión se
        # torció; sin agregarlas aquí, el flag no sale nunca de `entreno_sets`.
        nsinint = g.loc[g["flag"].astype(str).str.contains("sin_intensidad", na=False),
                        "n_series"].sum(min_count=1)
        # Qué ejercicios NO hizo, por su nombre. Vienen de dos sitios y significan lo
        # mismo: un `0x0` escrito a mano y los que se dejó sin apuntar al final de la
        # sesión. El número solo no sirve de nada —Jarvis necesita decir "no hiciste
        # plancha", no "te faltó un ejercicio"—, y es la señal de que la sesión se torció.
        nh = g.loc[g["flag"].astype(str).str.contains("no_hecho", na=False), "ejercicio"]
        no_hechos = ", ".join(dict.fromkeys(
            x for x in nh.astype(str) if x and x.lower() not in ("none", "nan")))
        dolor = ""
        if "dolor_sesion" in g:
            vals = g["dolor_sesion"].dropna().astype(str)
            vals = vals[vals != ""]
            if not vals.empty: dolor = vals.iloc[0]
        return pd.Series(dict(
            # `plani` se quedó fuera cuando se agregó por sesión, y sin él "bloque 2" es
            # ambiguo: Hugo reinicia la numeración con cada plan. Hace falta para poder
            # traducir (plan, bloque) al nombre de la etapa — Build, Peaking… — en el
            # parte de estado de Jarvis.
            plani=g["plani"].iloc[0],
            semana=g["semana"].iloc[0], dia=g["dia"].iloc[0], bloque=g["bloque"].iloc[0],
            volumen_total=g["volumen"].sum(min_count=1),
            n_series_total=g["n_series"].sum(min_count=1),
            n_fallos_total=nfallos,
            n_sin_intensidad_total=nsinint,
            no_hechos=no_hechos,
            mejor_e1rm=g["e1rm"].max(),
            vol_basicos=vb, vol_accesorios=va,
            dolor_sesion_keep=dolor,
        ))
    sesion = dated.groupby("fecha", as_index=False).apply(agg, include_groups=False)
    return sets, sesion

# ----------------------------------------------------------------------------
# 3/4. RM1 (derivado de entreno: mejor e1RM por semana y por ejercicio básico)
# ----------------------------------------------------------------------------
def build_rm1(sets):
    if sets.empty: return pd.DataFrame()
    b = sets[(sets["tipo"] == "básico") & sets["e1rm"].notna()]
    if b.empty: return pd.DataFrame()
    # `plani` va en la clave: Hugo REINICIA la numeración de bloques con cada plan, así que
    # sin él el bloque 2 de PLANI 2 (Build) se fusionaría con el bloque 2 de PLANI 1 y los
    # e1RM de dos etapas distintas saldrían mezclados. Ya se solapan de verdad desde que
    # entró Build (P1 usa 1/2/3/4, P2 usa 1/2), así que esto dejó de ser hipotético.
    # El panel de Fuerza ya etiqueta P{plani}B{bloque}S{semana}.
    piv = (b.groupby(["plani", "bloque", "semana", "ejercicio"])["e1rm"].max()
             .reset_index().rename(columns={"e1rm": "mejor_e1rm"}))
    return piv

# ----------------------------------------------------------------------------
# 5. CONSOLIDACIÓN -> derived_diario
# ----------------------------------------------------------------------------
def to_num(df, cols):
    for c in cols:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

_HHMM = re.compile(r'^\s*(\d{1,2})[:.](\d{2})(?::\d{2})?\s*$')

def _hhmm(v):
    m = _HHMM.match(str(v)) if v is not None else None
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None

def tiempo_en_cama(acostarse, despertar):
    """Horas ENTRE acostarse y levantarse. Cruza medianoche.

    Ojo: esto NO son horas dormidas. El formulario AM pregunta a qué hora te
    metiste en la cama y a qué hora te levantaste, así que incluye lo que tardas
    en dormirte y los despertares. Las horas dormidas de verdad las mide el reloj
    (Intervals). La diferencia entre ambas es la eficiencia del sueño.
    """
    a, d = _hhmm(acostarse), _hhmm(despertar)
    if a is None or d is None:
        return None
    if d <= a:
        d += 24 * 60          # se acostó antes de medianoche, despertó después
    h = (d - a) / 60.0
    return round(h, 2) if 0 < h <= 16 else None   # fuera de rango = dato mal metido

def cafeina_de_ayer(df):
    """La cafeína que explica el sueño de una noche es la del día ANTERIOR.

    Desde el 2026-11-11 solo se apunta el día que se la toma (formulario PM), así que la
    columna que el panel de Correlaciones cruza con el sueño se calcula aquí en vez de
    preguntarse. Se desplaza por FECHA NATURAL y no con `shift(1)` como `hrv_ayer`:
    `derived_diario` solo tiene los días con datos, y un hueco de dos días le colgaría el
    café del martes a la noche del jueves. Donde no hay PM del día anterior manda el
    histórico del formulario AM, que es donde se preguntaba hasta esa fecha.
    """
    if "cafeina_hoy_mg" not in df:
        return df["cafeina_ayer_mg"] if "cafeina_ayer_mg" in df else None
    f = pd.to_datetime(df["fecha"], errors="coerce")
    tomada = pd.Series(df["cafeina_hoy_mg"].values, index=f)
    # Fechas ilegibles o repetidas romperían el map; en `consolidate` no las hay (se
    # deduplica antes), pero la función se usa suelta desde el test.
    tomada = tomada[~tomada.index.isna()]
    tomada = tomada[~tomada.index.duplicated(keep="last")]
    ayer = pd.Series((f - pd.Timedelta(days=1)).map(tomada).values, index=df.index)
    return ayer.fillna(df["cafeina_ayer_mg"]) if "cafeina_ayer_mg" in df else ayer


def consolidate(am, pm, peso, objetivo, sesion, duraciones):
    # normaliza claves de fecha
    for d in (am, pm, peso, objetivo, sesion, duraciones):
        if not d.empty and "fecha" in d:
            d["fecha"] = d["fecha"].astype(str).str[:10]

    am = to_num(am, ["sueno_calidad","sensacion_am","animo","estres","molestias_nivel",
                     "cafeina_ayer_mg","alcohol_ayer","latencia_min"])
    pm = to_num(pm, ["energia","sensacion_global","cafeina_hoy_mg","rpd_sesion"])
    peso = to_num(peso, ["peso_kg"])

    # Varias pesadas el mismo día -> una sola fila (media). Si no, el merge duplica
    # filas en derived_diario y rompe los lags y las ventanas móviles de abajo.
    if not peso.empty and "fecha" in peso:
        peso = peso.groupby("fecha", as_index=False)["peso_kg"].mean().round(2)

    base = pd.DataFrame({"fecha": pd.unique(pd.concat(
        [x["fecha"] for x in (am, pm, objetivo, sesion) if not x.empty and "fecha" in x],
        ignore_index=True))}) if any(not x.empty for x in (am,pm,objetivo,sesion)) else pd.DataFrame(columns=["fecha"])
    if base.empty: return base

    # `latencia_min` (cuánto tardas en dormirte) aún no existe en el formulario AM.
    # Se arrastra si algún día aparece; hasta entonces, la mezcla de latencia y
    # despertares se ve como el hueco entre tiempo en cama y horas dormidas.
    am_cols = ["fecha","sueno_calidad","sensacion_am","animo","estres","molestias_nivel",
               "cafeina_ayer_mg","alcohol_ayer","hora_acostarse","hora_despertar","latencia_min",
               "notas_am"]
    pm_cols = ["fecha","energia","sensacion_global","cafeina_hoy_mg","cafeina_hoy_hora","rpd_sesion",
               "dolor_sesion_zona","dolor_sesion_nota","notas_pm"]
    df = base.merge(am[[c for c in am_cols if c in am]], on="fecha", how="left") \
             .merge(pm[[c for c in pm_cols if c in pm]], on="fecha", how="left") \
             .merge(objetivo, on="fecha", how="left") \
             .merge(sesion, on="fecha", how="left") \
             .merge(duraciones, on="fecha", how="left") \
             .merge(peso[["fecha","peso_kg"]] if not peso.empty else peso, on="fecha", how="left")

    df = df.sort_values("fecha").drop_duplicates(subset="fecha", keep="last").reset_index(drop=True)

    # Sueño. Dos magnitudes distintas que NO se mezclan:
    #   sueno_horas       -> horas realmente dormidas, las mide el reloj (Intervals).
    #   tiempo_en_cama_h  -> horas entre acostarse y levantarse, del formulario AM.
    # La segunda incluye lo que tardas en dormirte y los despertares, así que
    # rellenar la primera con la segunda inflaría tu sueño. Su cociente es la
    # eficiencia: cuánto de lo que pasas en cama duermes de verdad.
    if "sueno_horas" not in df:
        df["sueno_horas"] = None
    df["sueno_horas"] = pd.to_numeric(df["sueno_horas"], errors="coerce")
    df["tiempo_en_cama_h"] = df.apply(
        lambda r: tiempo_en_cama(r.get("hora_acostarse"), r.get("hora_despertar")), axis=1)
    ef = df["sueno_horas"] / df["tiempo_en_cama_h"]
    df["eficiencia_sueno"] = (ef * 100).round(1).where(ef.between(0, 1))

    # readiness 0-100 (bipolares directas, unipolares invertidas)
    def readiness(r):
        bip = [r.get(k) for k in ("sueno_calidad","sensacion_am","animo","energia")]
        uni = [9 - r.get(k) if pd.notna(r.get(k)) else None for k in ("estres","molestias_nivel")]
        vals = [v for v in bip + uni if pd.notna(v)]
        return round(sum(vals)/len(vals)/9*100, 1) if vals else None
    df["readiness"] = df.apply(readiness, axis=1)

    # delta AM->PM
    df["delta_am_pm"] = df["sensacion_global"] - df["sensacion_am"]

    # sRPE por SERIES — la métrica de carga PRINCIPAL (ver CLAUDE.md). Se calcula aquí y en
    # ningún otro sitio: hasta ahora el panel de Carga la recalculaba en TypeScript mientras
    # la hoja guardaba otra fórmula con el mismo nombre (`sRPE` = rpd × duración), así que
    # Jarvis —que lee la hoja— podía contradecir lo que Hugo veía en pantalla.
    # Un fallo (0 repes) es esfuerzo máximo y fatiga mucho más que una serie normal, así que
    # cuenta como una serie a RPE 10 por este factor. Si algún día dispara demasiado la
    # carga, bajarlo a 2 — y solo aquí.
    FACTOR_FALLO = 3
    if "rpd_sesion" in df and "n_series_total" in df:
        fallos = df["n_fallos_total"].fillna(0) if "n_fallos_total" in df else 0
        completas = (df["n_series_total"] - fallos).clip(lower=0)
        df["sRPE_series"] = (df["rpd_sesion"] * completas + fallos * 10 * FACTOR_FALLO).round(0)
        # Ventana de 7 DÍAS NATURALES, no de 7 filas: `derived_diario` solo tiene los días
        # con datos, así que contar filas metería en la ventana sesiones de hace semanas.
        _idx = pd.to_datetime(df["fecha"], errors="coerce")
        df["sRPE_series_7d"] = (df.set_index(_idx)["sRPE_series"]
                                  .rolling("7D", min_periods=1).sum().values)

    # sRPE por DURACIÓN (heredado). Depende de Intervals, que a veces no manda duración, así
    # que es el flojo; se mantiene porque ACWR y el panel de Correlaciones aún tiran de él.
    # sRPE = RPD * duración (min)
    if "rpd_sesion" in df and "duracion_min" in df:
        df["sRPE"] = (df["rpd_sesion"] * df["duracion_min"]).round(0)

    # lags y carga
    df["cafeina_ayer_mg"] = cafeina_de_ayer(df)
    df["hrv_ayer"] = df["hrv_rmssd"].shift(1) if "hrv_rmssd" in df else None
    df["sueno_horas_ayer"] = df["sueno_horas"].shift(1) if "sueno_horas" in df else None
    if "sRPE" in df:
        df["sRPE_7d"]  = df["sRPE"].rolling(7,  min_periods=1).sum()
        df["sRPE_28d"] = df["sRPE"].rolling(28, min_periods=1).sum()
        df["ACWR"] = ((df["sRPE_7d"]/7) / (df["sRPE_28d"]/28)).round(2)
    return df

# ----------------------------------------------------------------------------
# gspread helpers — escribir SOLO en pestañas de salida
# ----------------------------------------------------------------------------
def open_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

def read_tab(sh, name):
    try:
        return pd.DataFrame(sh.worksheet(name).get_all_records())
    except Exception as e:
        print(f"  (aviso) no pude leer '{name}': {e}")
        return pd.DataFrame()

def write_tab(sh, name, df):
    if df is None or df.empty:
        print(f"  (aviso) '{name}' vacío, no escribo."); return
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(df.columns)))
    ws.clear()
    values = [df.columns.tolist()] + df.where(pd.notna(df), "").astype(object).values.tolist()
    ws.update(values, value_input_option="USER_ENTERED")
    print(f"  ✓ {name}: {len(df)} filas")

def informe_frescura(df, hoy):
    """Hasta qué día llega cada fuente.

    Sin esto, que el reloj lleve una semana sin sincronizar con Intervals es
    indistinguible de que el pipeline no se haya ejecutado: la hoja se reescribe
    igual y el resumen dice "121 días" en ambos casos.
    """
    print("\n· Frescura de los datos (último día con valor):")
    fuentes = [("hrv_rmssd", "HRV (reloj)"), ("sueno_horas", "sueño (reloj)"),
               ("pasos", "pasos (reloj)"), ("sueno_calidad", "formulario AM"),
               ("rpd_sesion", "formulario PM"), ("volumen_total", "entreno (keep)"),
               ("peso_kg", "peso")]
    for col, etiqueta in fuentes:
        if col not in df:
            print(f"    {etiqueta:<18} —  (columna ausente)"); continue
        con_dato = df.loc[df[col].notna(), "fecha"]
        if con_dato.empty:
            print(f"    {etiqueta:<18} —  (sin datos)"); continue
        ultimo = con_dato.iloc[-1]
        atraso = (dt.date.fromisoformat(hoy) - dt.date.fromisoformat(ultimo)).days
        aviso = "" if atraso <= 1 else f"   ← {atraso} días de retraso"
        print(f"    {etiqueta:<18} {ultimo}{aviso}")

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    today = dt.date.today()
    ap.add_argument("--since", default=str(today - dt.timedelta(days=120)))
    ap.add_argument("--until", default=str(today))
    args = ap.parse_args()

    missing = [k for k,v in dict(INTERVALS_API_KEY=API_KEY, INTERVALS_ATHLETE_ID=ATHLETE,
                                 GOOGLE_SA_JSON=SA_JSON, SHEET_ID=SHEET_ID).items() if not v]
    if missing:
        sys.exit(f"Faltan variables en .env: {', '.join(missing)}")

    print(f"Rango: {args.since} -> {args.until}")
    print("1) Intervals…")
    objetivo   = fetch_objetivo(args.since, args.until)
    duraciones = fetch_duraciones(args.since, args.until)
    print(f"   objetivo: {len(objetivo)} días | actividades con duración: {len(duraciones)}")

    print("2) Entreno (Keep + Excel)…")
    sets, sesion = build_entreno()
    rm1 = build_rm1(sets)
    print(f"   sets: {len(sets)} | sesiones: {len(sesion)} | rm1: {len(rm1)}")

    print("3) Hub (lectura)…")
    sh = open_sheet()
    am   = read_tab(sh, "wellness_am")
    pm   = read_tab(sh, "wellness_pm")
    peso = read_tab(sh, "peso")
    print(f"   wellness_am: {len(am)} | wellness_pm: {len(pm)} | peso: {len(peso)}")

    print("4) Consolidando derived_diario…")
    derived = consolidate(am, pm, peso, objetivo, sesion, duraciones)
    print(f"   derived_diario: {len(derived)} días")

    print("5) Escribiendo en el hub…")
    write_tab(sh, "objetivo", objetivo)
    write_tab(sh, "entreno_sets", sets)
    write_tab(sh, "entreno_sesion", sesion)
    write_tab(sh, "rm1", rm1)
    write_tab(sh, "derived_diario", derived)

    if not derived.empty:
        informe_frescura(derived, args.until)
    print("\nHecho ✅")

if __name__ == "__main__":
    main()
