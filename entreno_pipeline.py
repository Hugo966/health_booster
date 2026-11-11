#!/usr/bin/env python3
"""
Pipeline de entreno v2 — consciente de BLOQUES.

  - Entiende cabeceras "BLOQUE N". Cada bloque se mapea a su Excel (BLOQUE_EXCEL).
    Solo se nombran los ejercicios de bloques con Excel; el resto entra con
    números + e1RM/volumen pero sin nombre y con flag 'sin_excel'.
  - Captura notas inline (dolor aductor, me caí, CONFÍE...) en columna `nota`.
  - Maneja casos reales: banda elástica (sin kg), isométricos por segundos (3x30"),
    tempo (3x12x2"), peso suelto sin reps (105), distancia (20m), RIR8+,
    e intensidades no parseables (RIRmario) -> flag, nunca se inventa.
"""
import os, re, sys, unicodedata

import pandas as pd
import requests

# El plan de TODOS los bloques vive en la misma hoja ("el usuario the GOAT"): las pestañas
# Pestaña del plan -> (PLAN, bloque). El plan es imprescindible en la clave: el usuario
# REINICIA la numeración de bloques con cada plan, así que "BLOQUE 1" de PLANI 1 y de
# PLANI 2 son etapas distintas. Indexando solo por bloque se pisaban: las sesiones de
# PLANI 1 bloque 1 estaban cogiendo los nombres de las pestañas Offseason (PLANI 2), y
# 21 de 67 ejercicios acababan con una "mejor marca" imposible —plancha copenhague a
# 101 kg, o una banca de 178 kg cuando la real son 101,8—. Verificado el 2026-09-09.
# El número de bloque debe cuadrar con el que el usuario escribe en SU keep, no ser correlativo.
# Una etapa NUEVA ya no hace falta darla de alta aquí: `rutas_automaticas()` la deduce
# (bloque siguiente del plan en curso) y el keep del usuario hace de red si se equivoca.
# Esta tabla sigue siendo la ANCLA de la que se cuenta, y lo único que fija su nombre.
# La 4ª columna es el NOMBRE de la etapa, y no es decoración: sin él, lo único que
# llega a Jarvis es "bloque 2", que no significa nada para el usuario —él la llama Build—.
# Va aquí para que al dar de alta una etapa nueva su nombre entre solo.
PLAN_TAB_RULES = [
    (re.compile(r'^\s*semana\s*0*(\d+)\s*$', re.I),      1, 3, "Volumen"),
    (re.compile(r'^\s*peaking\s*s\s*0*(\d+)\s*$', re.I), 1, 4, "Peaking"),
    # Offseason (S1-S5): primera etapa de PLANI 2. Tolera "offseason"/"offseasion" y
    # separadores sueltos porque la pestaña la escribe a mano cada semana.
    (re.compile(r'^\s*off[\s\-_]*seasi?on\s*[\s\-_]*s\s*0*(\d+)\s*$', re.I), 2, 1, "Offseason"),
    # Build (S1-S5): segunda etapa de PLANI 2, la que viene después del Offseason.
    (re.compile(r'^\s*build\s*[\s\-_]*s\s*0*(\d+)\s*$', re.I), 2, 2, "Build"),
    # Build II (desde 2026-10): tercera etapa de PLANI 2, y el BLOQUE 3 que el usuario ya
    # escribe en su keep. No choca con la regla de arriba: ahí, tras "build" solo puede
    # venir la "s" de la semana, y aquí viene la "II".
    (re.compile(r'^\s*build\s*(?:ii|2)\s*[\s\-_]*s\s*0*(\d+)\s*$', re.I), 2, 3, "Build II"),
    # Formato "P2B2S3": el que el usuario quiere usar cuando migre el plan del entrenador a
    # una hoja suya. Aún no existe ninguna pestaña así; se enruta ya para que ese día
    # no haya que tocar nada, y porque lleva el plan y el bloque dentro del nombre.
    (re.compile(r'^\s*p\s*0*(\d+)\s*b\s*0*(\d+)\s*s\s*0*(\d+)\s*$', re.I), None, None, None),
]

def _etapa(titulo):
    """'Build II S6' -> 'build ii s': la parte del nombre que identifica la ETAPA.

    Se quita el número final (la semana) y se normaliza con la misma clave que los alias
    de ejercicio, para que una errata tonta del entrenador —una tilde, una mayúscula, un
    espacio de más— no cuente como etapa nueva.
    """
    return _key(re.sub(r'\d+\s*$', '', titulo))


def _es_plan(colA):
    """¿Esta pestaña es una semana de plan? Lo dice su CONTENIDO, no su nombre.

    Una cabecera `Sesión N` en la columna A es la única señal que no depende de cómo la
    haya bautizado el entrenador. Nutrición, los gráficos y las tablas de movilidad no la
    tienen, aunque se llamen "Movilidad 2".
    """
    return any(isinstance(c, str) and SES_RE.match(c.strip()) for c in colA)


def rutas_automaticas(pestanas, manual=None):
    """(rutas, pendientes) para las pestañas que no casan con ninguna regla.

    `pestanas`: iterable de (título, columna_A), en el orden en que están en la hoja.
    `manual`: {clave_normalizada: (plani, bloque, semana)} con lo que el usuario ya contestó
    sobre una pestaña que no se podía resolver sola. Manda sobre la deducción.

    `rutas` son las resueltas; `pendientes` son las que SON plan —traen `Sesión N`— pero
    no se pueden resolver porque el nombre no acaba en número y nadie ha dicho aún qué
    semana son. Esas no se adivinan: la semana decide a qué sesión van los ejercicios, y
    equivocarse ahí le pone a las series el nombre de otro día. Se devuelven para
    preguntárselo.

    El nombre de la etapa lo pone el entrenador y se lo inventa cada vez; el plan y el
    bloque son del usuario y NO están en ese nombre. Pero en todo su histórico una etapa
    nueva ha sido siempre el bloque siguiente del plan en curso (Offseason → 1,
    Build → 2, Build II → 3), así que se asigna eso y se deja de esperar a que alguien
    añada un patrón a mano.

    Adivinar aquí sale barato PORQUE el error se ve: el keep lleva el `BLOQUE n` que
    escribe el usuario, y si no coincide, sus series entran sin nombre de ejercicio y
    `huecos.py` lo pinta en ámbar ese mismo día.

    Dos frenos para no tragarse lo que no es plan:
    - la pestaña tiene que acabar en número (la semana), y
    - su columna A tiene que traer alguna cabecera `Sesión N`. Una pestaña de
      movilidad o de gráficos no la tiene, aunque se llame "Movilidad 2".
    """
    manual = manual or {}
    conocidas = [route_tab(t) for t, _ in pestanas]
    # Lo que el usuario ya contestó cuenta como ancla: si dijo que una es el bloque 4, la
    # siguiente etapa nueva tiene que ser la 5, no volver a ser la 4.
    out = {t: manual[_key(t)] for (t, _), d in zip(pestanas, conocidas)
           if not d and _key(t) in manual}
    anclas = [d for d in conocidas if d] + list(out.values())
    pendientes = [t for (t, colA), d in zip(pestanas, conocidas)
                  if not d and _key(t) not in manual
                  and not re.search(r'\d\s*$', t) and _es_plan(colA)]
    if not anclas:
        # Sin una sola pestaña conocida no hay de dónde contar: no se inventa nada, pero
        # las que son plan se siguen preguntando.
        return out, pendientes + [t for (t, colA), d in zip(pestanas, conocidas)
                                  if not d and _key(t) not in manual and _es_plan(colA)
                                  and re.search(r'\d\s*$', t)]
    plani = max(p for p, _, _ in anclas)
    siguiente = max(b for p, b, _ in anclas if p == plani) + 1

    vistas = {}
    for (titulo, colA), dest in zip(pestanas, conocidas):
        if dest or titulo in out or not re.search(r'\d\s*$', titulo) or not _es_plan(colA):
            continue
        etapa = _etapa(titulo)
        if etapa not in vistas:
            vistas[etapa] = siguiente
            siguiente += 1
        out[titulo] = (plani, vistas[etapa], re.search(r'(\d+)\s*$', titulo).group(1))
    return out, pendientes


def route_tab(title):
    """Título de pestaña -> (plani, bloque, semana), o None si no es una semana de plan."""
    for rx, plani, bloque, _ in PLAN_TAB_RULES:
        m = rx.match(title)
        if not m:
            continue
        if plani is None:            # formato PxBySz: los tres números van en el título
            return int(m.group(1)), int(m.group(2)), m.group(3)
        return plani, bloque, m.group(1)
    return None


def nombre_etapa(plani, bloque):
    """(plan, bloque) -> 'Build', 'Peaking'… o None si esa etapa no tiene nombre.

    Existe para que el parte de estado pueda decir "Build" en vez de "bloque 2": el
    número es interno del pipeline, el nombre es como lo llama el usuario.
    """
    try:
        plani, bloque = int(plani), int(bloque)
    except (TypeError, ValueError):
        return None
    for _, p, b, nombre in PLAN_TAB_RULES:
        if p == plani and b == bloque:
            return nombre
    return None

# Fuente local del plan (solo para el modo __main__ de depuración; el pipeline real
# lo lee de Drive).
PLAN_XLSX = "/home/hugo/Desktop/el usuario the GOAT.xlsx"

# Correcciones puntuales: semanas donde desviaste el plan del Excel.
# (plani, bloque, semana): {dia_que_entrenaste: dia_del_que_sacaste_los_BÁSICOS}
# Solo rotan los básicos; los accesorios se quedan en su día.
BASIC_SWAP = {
    (1, 3, '4'): {'2': '3', '3': '4', '4': '2'},   # P1-B3-SEM4: básicos rotados DIA2<-3, DIA3<-4, DIA4<-2
}

def apply_basic_swaps(lk_by_etapa):
    for (plani, bloque, sem), mapping in BASIC_SWAP.items():
        lk = lk_by_etapa.get((plani, bloque))
        if not lk:
            continue
        nuevo = {}
        for perf_dia, src_dia in mapping.items():
            basicos = [e for e in lk.get((sem, src_dia), []) if e['block'] == 'básico']
            access  = [e for e in lk.get((sem, perf_dia), []) if e['block'] == 'accesorio']
            nuevo[(sem, perf_dia)] = [dict(order=i, name=e['name'], block=e['block'], bw=e['bw'])
                                      for i, e in enumerate(basicos + access, 1)]
        lk.update(nuevo)
    return lk_by_etapa

RPE_TABLE = {
    10.0:[100,95.5,92.2,89.2,86.3,83.7,81.1,78.6,76.2,73.9,70.7,68.0],
    9.5:[97.8,93.9,90.7,87.8,85.0,82.4,79.9,77.4,75.1,72.3,69.4,66.7],
    9.0:[95.5,92.2,89.2,86.3,83.7,81.1,78.6,76.2,73.9,70.7,68.0,65.3],
    8.5:[93.9,90.7,87.8,85.0,82.4,79.9,77.4,75.1,72.3,69.4,66.7,64.0],
    8.0:[92.2,89.2,86.3,83.7,81.1,78.6,76.2,73.9,70.7,68.0,65.3,62.6],
    7.5:[90.7,87.8,85.0,82.4,79.9,77.4,75.1,72.3,69.4,66.7,64.0,61.3],
    7.0:[89.2,86.3,83.7,81.1,78.6,76.4,73.9,70.7,68.0,65.3,62.6,59.9],
    6.5:[87.8,85.0,82.4,79.9,77.4,75.1,72.3,69.4,66.7,64.0,61.3,58.6],
    6.0:[86.3,83.7,81.1,78.6,76.2,73.9,70.7,68.0,65.3,62.6,59.9,57.4],
}
RPE_KEYS=sorted(RPE_TABLE); BW=('plancha','abduc','retrac','dominada','fondo','hollow','gusano')

# Ejercicios que NUNCA llevan carga. En ellos dos números son SERIES × REPES, no peso ×
# repes: "2x5RIR2" en la rueda abdominal son 2 series de 5, no 2 kg. No vale con el flag
# `bw` (peso corporal) para decidirlo, porque una dominada también es peso corporal y ahí
# "5x3" SÍ son 5 kg lastrados. Por eso va por ejercicio concreto y no por categoría: hay
# abdominales que sí llevan peso (el crunch en polea son 55 kg de verdad).
# Se compara en minúsculas contra el nombre del plan de Drive, así que basta un fragmento.
SIN_CARGA=('rueda abdominal','plancha','step down lateral','w slides')

# Vocabulario controlado de zonas (mismo que el form AM) + sinónimos para normalizar texto libre.
ZONE_KEYWORDS = {
    'Abdomen':['abdomen','abdominal','core'], 'Aductor':['aductor','adductor'],
    'Antebrazos':['antebrazo'], 'Bíceps':['biceps','bíceps'], 'Cadera':['cadera'],
    'Codo':['codo'], 'Cuádriceps':['cuadricep','cuádricep','cuadriceps','cuádriceps'],
    'Cuello':['cuello','cervical'], 'Dorsal/Trapecios':['dorsal','trapecio','trapa'],
    'Gemelos':['gemelo','soleo','sóleo'], 'Glúteo':['gluteo','glúteo'],
    'Hombro':['hombro','deltoid'], 'Isquios':['isquio','femoral'],
    'Lumbar':['lumbar','espalda baja'], 'Manos':['mano'], 'Muñeca':['muñeca','muneca'],
    'Pectoral':['pectoral','pecho'], 'Rodilla':['rodilla'], 'Tobillo':['tobillo'],
    'Triceps':['triceps','tríceps'],
}
def normalize_zones(text):
    if not text: return '', ''
    low=text.lower()
    zonas=[z for z,kws in ZONE_KEYWORDS.items() if any(k in low for k in kws)]
    lado=''
    if re.search(r'\bizq', low): lado='izq'
    if re.search(r'\bder', low): lado='der' if not lado else 'bilateral'
    if re.search(r'bilat|ambos|los dos|amb\b', low): lado='bilateral'
    return ' | '.join(zonas), lado
def rir_to_rpe(r): return max(6.0,min(10.0,10.0-float(r)))
def snap(r): return min(RPE_KEYS,key=lambda k:abs(k-r))
def e1rm(w,reps,rpe=None,rir=None):
    if w is None or reps is None: return None,None
    # 0 reps = intento fallido (no sacó la repetición). Sin rep completada no hay e1RM
    # que valga: si se dejara pasar, el fallback Epley devolvería el propio peso (200x0
    # -> "e1RM 200") y se colaría como récord/estrella. Cuenta como fatiga, no como marca.
    if reps < 1: return None,None
    if rpe is None and rir is not None: rpe=rir_to_rpe(rir)
    if rpe is None: rpe=10.0
    ri=int(round(reps))
    if 1<=ri<=12 and 6.0<=rpe<=10.0: return round(w/(RPE_TABLE[snap(rpe)][ri-1]/100.0),1),"tabla_RPE"
    return round(w*(1+(reps+(10.0-rpe))/30.0),1),"epley_fallback"

# ---------------------------------------------------------------------------
# Normalización de nombres de ejercicio.
#
# El plan escribe el mismo ejercicio de formas distintas según la pestaña
# ("Ext tríceps katana" vs "Extensión tríceps katana") y a veces le pega el esquema
# de series ("Banca 3ct 4x3 @7"). Aquí se unifica.
#
# CUIDADO: las variantes de un mismo patrón son ejercicios DISTINTOS y no se
# fusionan nunca. Banca comp ≠ Banca 3ct ≠ Banca mid grip.
# ---------------------------------------------------------------------------
_SCHEME_RE = re.compile(r'\s+\d+\s*x\s*\d+.*$', re.I)   # "... 4x3 @7", "... 1x2 y 3x4 @6"
_TRAIL_RPE_RE = re.compile(r'\s*@[\d.]+\s*$')

def _key(name):
    """Clave de comparación: sin tildes, minúsculas, espacios colapsados."""
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().lower()

# clave normalizada -> nombre canónico para mostrar.
#
# Solo fusiona ABREVIATURAS del mismo ejercicio. "Sq low bar" es literalmente
# "Sentadilla low bar". Lo que NO se fusiona nunca son variantes distintas:
# Banca comp / Banca 3ct / Banca mid grip, o Sq high bar / Sq high bar pausa 2ct.
ALIAS = {
    'comp bp':                             'Banca comp',
    # Low bar SIN tacón, los tres nombres. El entrenador le puso un tacón de 2 cm en
    # septiembre por un dolor de pie y se lo quitó en Build II S6 al quitarse el dolor:
    # al quitárselo no empieza un ejercicio nuevo, VUELVE al de junio-julio, que estaba
    # apuntado como 'Sentadilla LB' y llega a 170 kg. Sin esto su sentadilla nacía el
    # 10/11 en 125 kg y la progresión se medía contra un suelo falso. Confirmado por Hugo
    # el 2026-11-11. El del tacón NO entra aquí: ese sí es otro movimiento.
    'sq low bar':                          'Sentadilla low bar',
    'sentadilla lb':                       'Sentadilla low bar',
    # Los dos nombres del sumo van al que usa el plan HOY; si se quedara 'Sumo dl', el
    # mismo básico tendría dos históricos (Peaking/Volumen por un lado, Build II por otro).
    'dl sumo':                             'Peso muerto sumo',
    'sumo dl':                             'Peso muerto sumo',
    'ext triceps katana':                  'Extensión tríceps katana',
    'ext triceps barra polea':             'Extensión tríceps en polea con barra',
    'extension de triceps barra polea':    'Extensión tríceps en polea con barra',
    'extension triceps barra':             'Extensión tríceps en polea con barra',
    'banca competicion':                   'Banca comp',
    'ext cuadriceps':                      'Extensión cuádriceps',
    'jalon al pecho agarre cerrado':       'Jalón al pecho agarre estrecho',
    'seal row multigrip o la otra':        'Seal row multigrip',
    'pajaros w en banco video':            'Pájaros W en banco',
    'sq high bar':                         'Sentadilla high bar',
    'bp mid grip':                         'Banca mid grip',
    'peck deck inverso':                   'Reverse peck deck',
    'curl bayesian en polea baja':         'Curl bayesian en polea',
    'elevaciones laterales en polea baja': 'Elevaciones laterales en polea',
    'cruce de poleas en banco':            'Cruce de poleas en banco sentado',
    'cruce de poleas (media) en banco':    'Cruce de poleas en banco sentado',
    'jalon unilateral':                    'Jalón unilateral en polea',
    'curl martillo alterno':               'Curl martillo mancuerna',
    'elevaciones lat en polea':            'Elevaciones laterales en polea',
    'press militar en maquina':            'Press militar máquina',
    'hip thrust unilateral con mancuerna': 'Hip thrust unilateral',
    'curl arana inclinado con barra z':    'Curl araña barra Z',
    'plancha+abduccion lateral de cadera': 'Plancha+abd lateral',
    'pull over unilateral polea alta':     'Pull over unilateral',
    'leg extension 2ct arriba':            'Leg extension 2ct',
    # Mismo ejercicio, dos formas de escribirlo en la hoja (encontradas el 2026-10-13 al
    # entrar Build II). Sin unificarlas, el histórico se parte en dos justo al cambiar de
    # etapa: la sentadilla principal del usuario pasaba a ser "otro ejercicio" en Build II.
    # `_key` ya ignora mayúsculas, tildes y espacios de más, así que aquí solo hace falta
    # lo que cambia de verdad (un espacio dentro de "2 cm", una palabra de menos).
    'sentadilla low bar tacon 2 cm':       'Sentadilla low bar tacón 2cm',
    'plancha copenhague':                  'Plancha copenhague',
    'hip thrust maquina':                  'Hip thrust en máquina',
    'hip thrust en maquina':               'Hip thrust en máquina',
    'remo maquina':                        'Remo en máquina',
}

def canon_exercise(name):
    """'Banca 3ct 4x3 @7' -> 'Banca 3ct'; 'Comp bp' -> 'Banca comp'."""
    if not name: return name
    t = _SCHEME_RE.sub('', name.strip())
    t = _TRAIL_RPE_RE.sub('', t).strip()
    # Espacios de más colapsados: "Hip thrust  en máquina" venía con dos en la hoja, y un
    # espacio invisible convierte un ejercicio en dos en el panel de Fuerza.
    t = re.sub(r'\s+', ' ', t)
    return ALIAS.get(_key(t), t)

SKIP={'básicos','basicos','accesorios','nombre','protocolo','comentario','observaciones','kg','repes','rir/rpe'}
# "RPE EN LA SESIÓN (0-10)" y su errata "RPD EN LA SESIÓN" no son ejercicios.
RPE_ROW_RE = re.compile(r'rp[ed]\s+en\s+la\s+sesi', re.I)
SES_RE  = re.compile(r'sesi[oó]n\s*0*(\d+)', re.I)

def _colA_from_xlsx(path):
    """Genera (titulo_pestaña, [valores columna A]) desde un .xlsx local."""
    # Import perezoso: openpyxl solo hace falta para el modo de depuración con el xlsx
    # local. El pipeline real lee el plan de Drive, y la VM no tiene esa dependencia.
    from openpyxl import load_workbook
    wb=load_workbook(path, read_only=True, data_only=True)
    for sh in wb.sheetnames:
        yield sh, [(row[0] if row else None) for row in wb[sh].iter_rows(values_only=True)]

# ---------------------------------------------------------------------------
# Origen del keep: documento de Drive o fichero local
# ---------------------------------------------------------------------------
# El keep vivía solo en disco, y eso ataba el pipeline a una máquina concreta: las dos
# del usuario se desincronizaban sin avisar, y en la VM directamente no existe. Con
# KEEP_DOC_ID pasa a ser un documento de Google que él edita desde donde quiera (el
# móvil incluido) y que el pipeline exporta como texto plano.

# Google Docs "corrige" al escribir, y sus sustituciones rompen el parser en silencio:
# el guion de separar series se convierte en raya (– —) y el split de `parse_keep` deja
# de cortar, y la comilla de los tempos (3x8x2"RIR0) se vuelve tipográfica. Se
# normalizan al leer, no en el parser, para que el keep local siga comportándose igual.
_TIPOGRAFICOS = {
    '\u2013': '-', '\u2014': '-', '\u2212': '-',      # – — −  -> guion normal
    '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u2033': '"',   # comillas dobles
    '\u2018': "'", '\u2019': "'", '\u2032': "'",      # comillas simples
    '\u00a0': ' ', '\u202f': ' ', '\u2009': ' ',      # espacios duros y finos
    '\u2026': '...',
}

def normalizar_texto(t):
    t = t.lstrip('\ufeff')
    for malo, bueno in _TIPOGRAFICOS.items():
        t = t.replace(malo, bueno)
    return t


def leer_keep(sa_json=None, doc_id=None, ruta=None):
    """Devuelve el contenido del keep, de Drive si hay KEEP_DOC_ID y si no del disco.

    Se exporta como `text/plain` con las credenciales del service account, así que el
    documento tiene que estar COMPARTIDO con él (el mismo `client_email` que ya lee el
    plan del entrenador); si no, Drive responde 404 y no se distingue de "no existe".
    """
    doc_id = doc_id or os.getenv("KEEP_DOC_ID", "").strip()
    ruta = ruta or os.getenv("KEEP_TXT", "")
    if doc_id:
        from google.auth.transport.requests import Request as _Req
        from google.oauth2.service_account import Credentials as _Cred
        creds = _Cred.from_service_account_file(
            sa_json or os.environ["GOOGLE_SA_JSON"],
            scopes=["https://www.googleapis.com/auth/drive.readonly"])
        creds.refresh(_Req())
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{doc_id}/export",
            params={"mimeType": "text/plain"},
            headers={"Authorization": f"Bearer {creds.token}"}, timeout=30)
        if r.status_code == 404:
            raise RuntimeError(
                f"Drive no encuentra el documento {doc_id}. Lo más probable es que no esté "
                "compartido con el service account que lee el plan.")
        r.raise_for_status()
        r.encoding = "utf-8"
        return normalizar_texto(r.text)
    if not ruta or not os.path.exists(ruta):
        return ""
    return normalizar_texto(open(ruta, encoding="utf-8").read())


def _sin_calentamiento(ejs):
    """Quita el calentamiento de la lista de una sesión y renumera los slots.

    El usuario NO apunta el calentamiento en el keep, así que si se queda aquí los nombres se
    corren un puesto y la sentadilla acaba llamándose "Tibial raises".

    No basta con saltarse la sección que cuelga de la cabecera `Warm up`: el MISMO
    ejercicio se repite suelto al final de Accesorios (Build II S2, sesiones 1 y 3). Y
    tampoco vale filtrar por el prefijo "Warm up" del nombre, que hoy está pero el usuario no
    garantiza que siga. Así que se recoge el nombre de lo que cuelga de la cabecera y se
    quita donde vuelva a salir EN ESA MISMA SESIÓN.
    """
    nombres = {_key(e['name']) for e in ejs if e['warm']}
    limpios = [e for e in ejs if not e['warm'] and _key(e['name']) not in nombres]
    return [dict(order=i, name=e['name'], block=e['block'], bw=e['bw'])
            for i, e in enumerate(limpios, 1)]


def extract_exercises(source, verbose=False, manual=None):
    """Lee el plan y devuelve {(plani, bloque): {(semana, dia): [ejercicios]}}.

    `source`: ruta a .xlsx local ó iterable de (titulo, columna_A) (p.ej. leído de
    Google Drive vía gspread). Solo se usa la columna A. Las pestañas que no sean
    una semana de plan se ignoran (nutrición, gráficos, movilidad…).
    """
    # Hay que recorrerlas dos veces (una para contar los bloques conocidos y otra para
    # leer), así que no vale un generador.
    sheets = list(_colA_from_xlsx(source) if isinstance(source, str) else source)
    auto, _ = rutas_automaticas(sheets, manual)
    out={}; mapping=[]; skipped=[]
    for sh, colA in sheets:
        dest = route_tab(sh) or auto.get(sh)
        if dest is None:
            skipped.append(sh); continue
        plani, bloque, wk = dest
        mapping.append((sh, plani, bloque, wk))
        lk = out.setdefault((plani, bloque), {})
        dia=0; order=0; block=None
        for a in colA:
            if not isinstance(a,str): continue
            t=a.strip(); low=t.lower()
            if not t: continue   # gspread devuelve '' en celdas vacías; ignóralas (como openpyxl->None)
            ms=SES_RE.match(t)
            if ms: dia=ms.group(1); order=0; block=None; continue
            if low in ('básicos','basicos'): block='básico'; continue
            if low in ('warm up','warm-up','warmup','calentamiento'): block='warm'; continue
            if low=='accesorios': block='accesorio'; continue
            if low in SKIP or RPE_ROW_RE.match(low) or t in ('#N/A','-'): continue
            if t=='#REF!':
                if dia: order+=1; lk.setdefault((wk,dia),[]).append(dict(order=order,name='(cambiado/#REF)',block=block,bw=False,warm=block=='warm'))
                continue
            if dia==0: continue
            order+=1
            lk.setdefault((wk,dia),[]).append(dict(order=order,name=canon_exercise(t),block=block,
                                                   bw=any(k in low for k in BW),warm=block=='warm'))
        # Al cerrar la pestaña, fuera el calentamiento de cada sesión suya.
        for clave, ejs in lk.items():
            if clave[0] == wk:
                lk[clave] = _sin_calentamiento(ejs)
    if verbose:
        src = source.split('/')[-1] if isinstance(source,str) else 'drive'
        print(f"  [Plan {src}] pestaña -> (plani, bloque, semana): {mapping}")
        print(f"  [Plan] pestañas ignoradas: {skipped}")
        if auto:
            print(f"  [Plan] ⚠ ETAPA NUEVA, enrutada SOLA (no hay patrón para ella): "
                  f"{ {t: auto[t] for t in auto} }")
            print(f"  [Plan]   el bloque es una deducción: si no cuadra con el que "
                  f"escribes en el keep, el semáforo se pondrá en ámbar.")
    return out

def parse_segment(seg):
    raw=seg.strip()
    if not raw: return None
    note=[]
    for m in re.findall(r'\(([^)]*)\)', raw): note.append(m.strip())
    s=re.sub(r'\([^)]*\)',' ',raw)
    mc=re.search(r'es\s*@([\d.]+)',s); corr=float(mc.group(1)) if mc else None
    s=re.sub(r'es\s*@[\d.]+',' ',s)
    # RPE (rango @x-y SIN espacios -> media). El guion del rango va pegado a los
    # números; un guion con espacio separa SERIES, no es rango, así que no puede
    # tragarse el kg de la serie siguiente aunque falte un espacio.
    rpe=None
    m=re.search(r'@([\d.]+)(?:-([\d.]+))?',s)
    if m:
        a=float(m.group(1)); b=float(m.group(2)) if m.group(2) else None
        rpe=round((a+b)/2,2) if b is not None else a
    if rpe is not None and not (0 <= rpe <= 10): rpe=None   # a prueba de fallos
    # RIR (rango RIRx-y SIN espacios -> media, y RIRx+)
    rir=None
    m=re.search(r'RIR\s*(\d+)(?:-(\d+))?(\+?)',s,re.I)
    if m:
        a=int(m.group(1)); b=int(m.group(2)) if m.group(2) else None
        rir=round((a+b)/2,2) if b is not None else a
    if rir is not None and not (0 <= rir <= 10): rir=None   # a prueba de fallos
    # Dos motivos distintos para quedarse sin intensidad, y NO se mezclan:
    #   `@?` / `RIR?` -> el usuario no PUEDE valorar el esfuerzo (lesión, dolor, contra el
    #     reloj). Es información sobre la sesión, no un error: flag `sin_intensidad`,
    #     para poder contar estas series como señal de sesión comprometida.
    #   `RIRmario` y demás -> basura de tecleo: flag `int_no_parseable`. Contarla como
    #     señal daría falsos positivos, así que va aparte.
    # En ningún caso se inventa un valor de esfuerzo.
    # El `@?` además hay que borrarlo aquí igual que un `@7`: va pegado al número, así que
    # si sobrevive, "115x1@?" deja el token "1@?" fuera de los números y la serie se lee
    # como 115 REPES sin peso (kg, volumen y e1RM perdidos).
    sin_int=bool(re.search(r'@\s*\?|RIR\s*\?',s,re.I))
    bad_int=bool(re.search(r'RIR(?!\s*[\d?])',s,re.I))
    s=re.sub(r'@\s*\?+',' ',s)
    s=re.sub(r'@[\d.]+(?:-[\d.]+)?',' ',s)
    s=re.sub(r'RIR\s*\d+(?:-\d+)?\+?',' ',s,flags=re.I)
    # Tramos de tiempo con UNA sola comilla al final: el plan del entrenador escribe la
    # compuesta así (`2x30-30" 20" rest`), y de ahí se le puede pegar al keep. Se le pone
    # su unidad a cada tramo ANTES del promedio de rangos de aquí abajo; si no, "30-30"
    # se promedia a 30 y la serie compuesta se queda en un tramo solo.
    s=re.sub(r'(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)+)\s*(["\'])',
             lambda m: (m.group(2)+'-').join(m.group(1).split('-')) + m.group(2), s)
    # rango de REPES (unilateral: 8 en un lado, 10 en el otro -> "8-10" -> media 9).
    # A esta altura los rangos de @ y RIR ya se han quitado, así que un guion pegado
    # entre dígitos solo puede ser un rango de repes.
    s=re.sub(r'(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)',
             lambda m: f"{round((float(m.group(1))+float(m.group(2)))/2,2):g}", s)
    s=re.sub(r'RIR\w*',' ',s,flags=re.I)
    # Cargas que NO son kg: banda por color, y discos/caja como etiqueta (dificultad, no
    # peso). Se extraen ENTERAS —aunque vayan pegadas tras "Nx" sin separador, por eso sin
    # \b— y se sacan del texto para que el nº de series no acabe leído como kg. La etiqueta
    # va a la nota. (La banda incluye la 'x' final en el match; se recorta de la etiqueta.)
    carga=None
    mb=re.search(r'(?:banda|goma)[a-záéíóúüñ_x]*', s, re.I)
    banda=bool(mb)
    if mb:
        carga=re.sub(r'x+$','',mb.group(0)).replace('_',' ').strip()
        s=re.sub(r'(?:banda|goma)[a-záéíóúüñ_x]*',' ',s,flags=re.I)
    md=re.search(r'(\d+)\s*_?\s*discos?', s, re.I)
    if md:
        carga=f"{md.group(1)} discos"; s=re.sub(r'\d+\s*_?\s*discos?',' ',s,flags=re.I)
    elif re.search(r'\bcajas?\b', s, re.I):
        carga='caja'; s=re.sub(r'\bcajas?\b',' ',s,flags=re.I)
    if carga: note.append(carga)
    # distancia (metros) — toma la primera ocurrencia
    metros=re.search(r'(\d+)\s*m\b',s)
    if metros: note.append(f"{metros.group(1)}m")
    s=re.sub(r'\d+\s*m\b',' ',s)
    # 1' es un minuto y 1" un segundo. Se pasa todo a segundos aquí, para que de aquí
    # abajo haya una sola unidad.
    s=re.sub(r"(\d+(?:\.\d+)?)\s*'", lambda m: f'{float(m.group(1))*60:g}"', s)
    # Duraciones del segmento, en orden. MÁS DE UNA = serie compuesta: plancha 30" +
    # descanso + otros 30". Los tramos no son series sueltas —las series son el número
    # que va delante de la x—, así que se quedan en la nota y no tocan la carga.
    tiempos=[float(x) for x in re.findall(r'(\d+(?:\.\d+)?)\s*"',s)]
    had_secs=bool(tiempos)
    s=re.sub(r'\d+(?:\.\d+)?\s*"',' SECS ',s)
    # separar núcleo numérico de palabras-nota (conservando espacios)
    s=re.sub(r'[xX]',' ',s)
    nums=[]; words=[]
    for tok in s.split():
        if tok in ('SECS','BANDA'): nums.append(tok)
        elif re.fullmatch(r'[\d.]+', tok):
            try: nums.append(float(tok))
            except: pass
        elif re.fullmatch(r'\?+', tok): pass   # marcador de `RIR?`, ya está en el flag
        elif re.fullmatch(r'-+', tok): pass    # guion que separaba los tramos de una compuesta
        else: words.append(tok)
    if words: note.append(' '.join(words))
    # Los segundos se perdían enteros: un 3x30" guardaba "3 series" y nada más, así que
    # ni el usuario ni Jarvis podían saber si la plancha fue de 30" o de un minuto. Van a la
    # nota —no a una columna— porque de momento se quieren para leerlos, no para graficar.
    if tiempos:
        otros=len([n for n in nums if isinstance(n,float)])
        if len(tiempos)>1:
            note.append('+'.join(f'{t:g}"' for t in tiempos) + f' = {sum(tiempos):g}s')
        elif otros>=2:
            note.append(f'tempo {tiempos[0]:g}"')   # 3x8x2" -> 2" por repe, no isométrico
        else:
            note.append(f'{tiempos[0]:g}"')
    return dict(raw=raw, nums=nums, rpe=corr if corr is not None else rpe, rir=rir,
                bad_int=bad_int, sin_int=sin_int, banda=banda, carga=carga,
                metros=(int(metros.group(1)) if metros else None),
                had_secs=had_secs, tiempos=tiempos, note=' | '.join(n for n in note if n))

# Un segmento con un solo número son repes por convención ("1x12"). Pero cuando el usuario
# apunta el peso y se deja las repes ("77.5x6@7.5 - 77.5@8"), ese número es un KG, y
# guardarlo como repes mete basura en la tabla. Se distingue mirando las series hermanas
# de la MISMA línea: si se parece a su peso, es un peso. Dos condiciones, y hacen falta
# las dos:
#   - TOL_KG_HERMANA: a cuánto puede estar del peso de una hermana (sube o baja algún kilo
#     dentro del mismo ejercicio).
#   - REPS_MAX_PLAUSIBLE: medido sobre el histórico del keep, las repes reales del usuario
#     nunca pasan de 20 (p99 = 16). Sin este tope, en un accesorio de 2 kg la ventana de
#     ±5 se traga el rango de repeticiones y "6RIR0 - 2x5RIR2" convertiría 6 repes en 6 kg.
TOL_KG_HERMANA = 5.0
REPS_MAX_PLAUSIBLE = 20

def interpret(nums, anchor, bw, banda, metros, carga=None, kgs_linea=(), sin_carga=False):
    numeric=[n for n in nums if isinstance(n,float)]; has_secs='SECS' in nums
    # Cargas que NO son kg (banda por color, discos/caja como dificultad): los números son
    # series y reps, nunca peso. La etiqueta ya va en la nota. Series se omite si es 1.
    if banda or carga or 'BANDA' in nums:
        esp = 'banda' if banda else 'carga'
        if metros is not None or has_secs:
            return (numeric[0] if numeric else 1),None,None,esp,''
        if len(numeric)>=2: return numeric[0],None,numeric[-1],esp,''
        if len(numeric)==1: return 1,None,numeric[0],esp,''
        return 1,None,None,esp,'carga_rara'
    if metros is not None:
        # Farmer walks y demás por distancia: guarda series + PESO cargado + metros (en nota).
        # Con UN solo número es el peso, no las series: "32.5x20m" son 32,5 kg cargados una
        # vez, y leerlo como 32,5 SERIES infla el sRPE (RPE × nº de series) de toda la
        # semana. La serie se omite cuando es 1, igual que en el resto de la notación.
        if len(numeric)>=2: ns,kg=numeric[0],numeric[1]
        else:               ns,kg=1,(numeric[0] if numeric else None)
        return ns,kg,None,'distancia','distancia_m'
    if has_secs:
        # La comilla ya ha marcado CUÁL es el número de segundos y lo ha sacado de la lista,
        # así que los que quedan son la notación normal: 3 -> series × PESO × repes,
        # 2 -> series × repes (en tempo el peso se omite si no lo hay). Antes se leían solo
        # los dos primeros y el tercero se perdía: "2x4x12x2"" guardaba 2 series de 4 repes
        # en vez de 2 series × 4 kg × 12 repes.
        if len(numeric)>=3: return numeric[0],numeric[1],numeric[2],'tempo',''
        if len(numeric)==2: return numeric[0],None,numeric[1],'tempo',''
        return (numeric[0] if numeric else 1),None,None,'isometrico',''
    # Convención del usuario: 3 números = series × peso × reps; 2 números = peso × reps
    # (1 serie; el peso se escribe siempre, 0 incluido para peso corporal); 1 = solo reps.
    # `anchor`/`bw` ya no hacen falta: la notación es inequívoca.
    if len(numeric)==3: return numeric[0],numeric[1],numeric[2],None,''
    # En un ejercicio sin carga posible el peso no existe, así que los dos números solo
    # pueden ser series y repes. Con tres (3x0x4) El usuario ya escribe el 0, y ese caso cae
    # arriba sin tocar nada. El "0x0" queda FUERA: no son 0 series de 0 repes, es su marca
    # de serie fallada o no hecha, y leerlo como 0 series la borraría de la carga (un fallo
    # pesa 10 × FACTOR_FALLO en el sRPE).
    if len(numeric)==2:
        if sin_carga and numeric[0] >= 1 and numeric[1] >= 1:
            return numeric[0],None,numeric[1],None,''
        return 1,numeric[0],numeric[1],None,''
    if len(numeric)==1:
        n=numeric[0]
        if n>REPS_MAX_PLAUSIBLE and any(abs(n-k)<=TOL_KG_HERMANA for k in kgs_linea):
            return 1,n,None,None,'incompleto'    # peso sin repes
        return 1,None,n,None,'incompleto'        # repes sin peso
    return None,None,None,None,'sin_datos'

def parse_keep(text, lookups):
    rows=[]; plani=None; bloque=None; week=dia=None; slot=0; exs=[]; cur_fecha=''; dolores={}

    def flush_no_hechos():
        # Si en una sesión el usuario registró MENOS ejercicios de los que el plan tenía,
        # es que la cortó por tiempo: se asume que no hizo los ÚLTIMOS que le tocaban.
        # Se anotan como 'no_hecho' (sin datos: no suman carga ni e1RM ni series) para
        # que la sesión incompleta conste. Solo si registró al menos uno (slot>0): una
        # sesión aún sin nada apuntado no es "no hecha", es que todavía no la ha metido.
        if week is None or not exs or slot <= 0 or slot >= len(exs):
            return
        for i in range(slot, len(exs)):
            e = exs[i]
            rows.append(dict(plani=plani, bloque=bloque, semana=week, dia=dia, fecha=cur_fecha,
                slot=i + 1, ejercicio=e['name'], tipo=e['block'], especial=None, token='',
                n_series=None, kg=None, reps=None, rpe=None, rir=None, e1rm=None, volumen=None,
                nota='', flag='no_hecho'))

    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        # Separadores visuales ("-----", "=====") y cabeceras de plan ("PLANI 2"):
        # El usuario los usa en el keep para dividir un plan de otro. No son ni bloques ni
        # ejercicios, pero sin filtrarlos se colaban como series fantasma —y "PLANI 2"
        # llegaba a contar como 1 serie, inflando la sRPE de la última sesión.
        if re.fullmatch(r'[-=_*·—\s]+', line): continue
        mpl=re.match(r'PLANI\s*(\d+)', line, re.I)
        if mpl:
            # El nº de plan etiqueta el eje de fuerza (P2B1S1). Va en el keep porque el usuario
            # reinicia bloque/semana con cada plan y sin la P se solaparían microciclos.
            flush_no_hechos()
            plani=int(mpl.group(1)); bloque=None; week=dia=None; slot=0; exs=[]; continue
        if re.match(r'PLANI\b', line, re.I):  # "PLANI" sin número: separador, se ignora igual
            flush_no_hechos()
            bloque=None; week=dia=None; slot=0; exs=[]; continue
        mb=re.match(r'BLOQUE\s+(\d+)',line,re.I)
        if mb:
            flush_no_hechos()
            bloque=int(mb.group(1)); week=dia=None; slot=0; exs=[]; continue
        h=re.match(r'SEM(\d+)\s*-\s*D[IÍ]A\s*(\d+)',line,re.I)
        if h:
            flush_no_hechos()   # cierra la sesión anterior antes de empezar la nueva
            week,dia=h.group(1),h.group(2); slot=0
            ex=re.search(r'-\s*(\d{4}-\d{2}-\d{2})',line); cur_fecha=ex.group(1) if ex else ''
            exs=lookups.get((plani,bloque),{}).get((week,dia),[]); continue
        # línea de dolores de sesión -> metadato de la sesión, NO un ejercicio
        md=re.match(r'\s*dolor(?:es)?\b', line, re.I)
        if md:
            txt=re.sub(r'^\s*dolor(?:es)?\s*(?:de\s*)?(?:sesi[oó]n)?\s*:?\s*','',line,flags=re.I).strip()
            dolores[(bloque,week,dia)] = txt or line
            continue
        # Línea sin ningún número: nota suelta ("Hora y media de entreno tu"), no un
        # ejercicio. Se ignora para no crear filas fantasma ni descuadrar la cuenta de
        # ejercicios (de la que depende detectar los 'no hechos').
        if not re.search(r'\d', line): continue
        slot+=1
        info=exs[slot-1] if slot-1 < len(exs) else None
        name=info['name'] if info else None; block=info['block'] if info else None; bw=info['bw'] if info else None
        # el plan cubre la sesión sólo si tiene ejercicios para ese (semana, día)
        has_excel=bool(exs)
        # Separador de series = guion con espacio en AL MENOS un lado (tolera que
        # falte un espacio: "@4.5 -75" o "@4.5- 75" separan igual). Un guion entre
        # dígitos sin espacios (RIR8-10, @7-8) NO separa: es un rango.
        segs=[parse_segment(t) for t in re.split(r'\s+-\s*|\s*-\s+', line)]; segs=[p for p in segs if p]
        anchor=next((p['nums'][1] for p in segs if len([n for n in p['nums'] if isinstance(n,float)])==3), None)
        # Pesos de las demás series de esta línea (mismo ejercicio), para resolver los
        # segmentos con un solo número. Se leen de los `nums` en crudo siguiendo la
        # convención (3 números -> series×PESO×repes; 2 -> PESO×repes) y se excluyen banda,
        # discos, distancia y tempo, donde los números no son kg.
        # En un ejercicio sin carga posible los números nunca son kg, así que no hay pesos
        # hermanos que ofrecer: la lista se queda vacía y un número suelto sigue siendo repes.
        sin_carga=bool(name) and any(k in str(name).lower() for k in SIN_CARGA)
        kgs_linea=[]
        for p in (() if sin_carga else segs):
            if p['banda'] or p.get('carga') or p['metros'] is not None or p['had_secs']: continue
            nn=[n for n in p['nums'] if isinstance(n,float)]
            if len(nn)==3: kgs_linea.append(nn[1])
            elif len(nn)==2: kgs_linea.append(nn[0])
        for p in segs:
            ns,kg,reps,sp,flag=interpret(p['nums'],anchor,bw,p['banda'],p['metros'],
                                         p.get('carga'),kgs_linea,sin_carga)
            rpe,rir=p['rpe'],p['rir']
            if p['sin_int']: flag=(flag+' sin_intensidad').strip()
            if p['bad_int']: flag=(flag+' int_no_parseable').strip()
            if not has_excel: flag=(flag+' sin_excel').strip()
            # Dos cosas MUY distintas se escriben con un 0 en las repes, y las separa el peso:
            #   `0x0` (sin peso) -> NO hizo el ejercicio. No es esfuerzo, es ausencia: ni
            #     series, ni volumen, ni carga. Contarlo como fallo le metía 30 puntos de
            #     sRPE (una serie a RPE 10 por el factor 3) a un ejercicio que no tocó.
            #   `200x0@10` (con peso) -> lo intentó y no sacó la repe. Eso SÍ es un fallo:
            #     esfuerzo máximo por definición, de ahí el RPE 10 aunque no lo anotara.
            # Sin repetición completada no hay e1RM en ninguno de los dos casos, así que
            # tampoco pueden salir en un récord.
            if reps == 0 and not kg:
                flag=(flag+' no_hecho').strip()
                ns,kg,reps,rpe,rir=None,None,None,None,None
            elif reps == 0:
                flag=(flag+' fallo').strip(); rpe,rir=10.0,None
            # Serie `@?`/`RIR?`: el peso y las repes son reales, así que suman volumen y
            # fatiga, pero el e1RM NO lo es —depende del esfuerzo, y justo eso es lo que
            # el usuario no pudo valorar—. Sin e1RM no compite por un PR, que es lo que importa:
            # un récord no puede salir de una serie que él marcó porque algo iba mal.
            calcula_e1rm = kg is not None and sp is None and not p['sin_int']
            est,met=e1rm(kg,reps,rpe,rir) if calcula_e1rm else (None,None)
            vol=round(ns*kg*reps,1) if (kg is not None and reps is not None and ns is not None) else None
            rows.append(dict(plani=plani,bloque=bloque,semana=week,dia=dia,fecha=cur_fecha,slot=slot,
                ejercicio=name,tipo=block,especial=sp,token=p['raw'],n_series=ns,kg=kg,reps=reps,
                rpe=rpe,rir=rir,e1rm=est,volumen=vol,nota=p['note'],flag=flag.strip()))
    flush_no_hechos()   # última sesión del fichero
    df=pd.DataFrame(rows)
    if not df.empty:
        df['dolor_sesion']=df.apply(lambda r: dolores.get((r['bloque'],r['semana'],r['dia']),''), axis=1)
    return df

if __name__=="__main__":
    keep=open(sys.argv[1],encoding="utf-8").read() if len(sys.argv)>1 else ""
    lookups=extract_exercises(PLAN_XLSX, verbose=True)
    apply_basic_swaps(lookups)
    df=parse_keep(keep, lookups)
    out="entreno_join.csv"; df.to_csv(out,index=False)
    pd.set_option("display.width",200,"display.max_columns",25)
    print("Slots por bloque:", {int(b):int(g.slot.nunique()) for b,g in df.groupby('bloque')})
    print("\nBLOQUE 3 / SEM5-DIA1 (nombres del Excel):")
    s=df[(df.bloque==3)&(df.semana=='5')&(df.dia=='1')]
    print(s[['slot','ejercicio','tipo','token','n_series','kg','reps','e1rm','volumen','especial','nota','flag']].to_string(index=False))
    print("\nBLOQUE 4 / SEM1-DIA2 (sin Excel, casos raros):")
    s2=df[(df.bloque==4)&(df.semana=='1')&(df.dia=='2')]
    print(s2[['slot','token','n_series','kg','reps','especial','nota','flag']].to_string(index=False))
    print(f"\nFilas: {len(df)} | e1RM: {df['e1rm'].notna().sum()} | notas: {(df['nota']!='').sum()} | flags: {(df['flag']!='').sum()}")
    print(f"CSV -> {out}")
