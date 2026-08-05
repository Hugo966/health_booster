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
import re, sys, unicodedata
import pandas as pd
from openpyxl import load_workbook

# El plan de TODOS los bloques vive en la misma hoja ("Hugo the GOAT"): las pestañas
# "Semana N" son el bloque 3 y las "Peaking SN" el bloque 4. El bloque no se puede
# deducir del número (Semana 3 y Peaking S3 colisionarían), así que cada familia de
# pestañas se enruta por regla; el número capturado es la semana dentro del bloque.
# Al empezar un bloque 5 basta con añadir aquí su patrón de pestaña.
PLAN_TAB_RULES = [
    (re.compile(r'^\s*semana\s*0*(\d+)\s*$', re.I),      3),
    (re.compile(r'^\s*peaking\s*s\s*0*(\d+)\s*$', re.I), 4),
    # Offseason (S1-S5): es la PRIMERA etapa de PLANI 2, el plan nuevo. Hugo reinicia
    # la numeración de bloques con cada plan, así que en su keep esta etapa es
    # "BLOQUE 1" (no la continuación 3/4/5 de PLANI 1) — el número aquí debe cuadrar
    # con el del keep o el join se queda sin nombres. Tolera "offseason"/"offseasion"
    # y separadores sueltos porque la pestaña la escribe a mano cada semana.
    # PENDIENTE: cuando PLANI 2 añada su etapa de volumen/peaking, sus "BLOQUE 2/3…"
    # chocarán con los de PLANI 1 (3=Semana, 4=Peaking). Habrá que meter dimensión de
    # plan; hoy no hace falta porque bloque 1 y 2 están libres.
    (re.compile(r'^\s*off[\s\-_]*seasi?on\s*[\s\-_]*s\s*0*(\d+)\s*$', re.I), 1),
]

def route_tab(title):
    """Título de pestaña -> (bloque, semana) o None si no es una semana de plan."""
    for rx, bloque in PLAN_TAB_RULES:
        m = rx.match(title)
        if m:
            return bloque, m.group(1)
    return None

# Fuente local del plan (solo para el modo __main__ de depuración; el pipeline real
# lo lee de Drive).
PLAN_XLSX = "/home/hugo/Desktop/Hugo the GOAT.xlsx"

# Correcciones puntuales: semanas donde desviaste el plan del Excel.
# (bloque, semana): {dia_que_entrenaste: dia_del_que_sacaste_los_BÁSICOS}
# Solo rotan los básicos; los accesorios se quedan en su día.
BASIC_SWAP = {
    (3, '4'): {'2': '3', '3': '4', '4': '2'},   # B3-SEM4: básicos rotados DIA2<-3, DIA3<-4, DIA4<-2
}

def apply_basic_swaps(lk_by_bloque):
    for (bloque, sem), mapping in BASIC_SWAP.items():
        lk = lk_by_bloque.get(bloque)
        if not lk:
            continue
        nuevo = {}
        for perf_dia, src_dia in mapping.items():
            basicos = [e for e in lk.get((sem, src_dia), []) if e['block'] == 'básico']
            access  = [e for e in lk.get((sem, perf_dia), []) if e['block'] == 'accesorio']
            nuevo[(sem, perf_dia)] = [dict(order=i, name=e['name'], block=e['block'], bw=e['bw'])
                                      for i, e in enumerate(basicos + access, 1)]
        lk.update(nuevo)
    return lk_by_bloque

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
# "Sentadilla LB" (low bar). Lo que NO se fusiona nunca son variantes distintas:
# Banca comp / Banca 3ct / Banca mid grip, o Sq high bar / Sq high bar pausa 2ct.
ALIAS = {
    'comp bp':                             'Banca comp',
    'sq low bar':                          'Sentadilla LB',
    'dl sumo':                             'Sumo dl',
    'ext triceps katana':                  'Extensión tríceps katana',
    'ext triceps barra polea':             'Extensión tríceps en polea con barra',
    'elevaciones lat en polea':            'Elevaciones laterales en polea',
    'press militar en maquina':            'Press militar máquina',
    'hip thrust unilateral con mancuerna': 'Hip thrust unilateral',
    'curl arana inclinado con barra z':    'Curl araña barra Z',
    'plancha+abduccion lateral de cadera': 'Plancha+abd lateral',
    'pull over unilateral polea alta':     'Pull over unilateral',
    'leg extension 2ct arriba':            'Leg extension 2ct',
}

def canon_exercise(name):
    """'Banca 3ct 4x3 @7' -> 'Banca 3ct'; 'Comp bp' -> 'Banca comp'."""
    if not name: return name
    t = _SCHEME_RE.sub('', name.strip())
    t = _TRAIL_RPE_RE.sub('', t).strip()
    return ALIAS.get(_key(t), t)

SKIP={'básicos','basicos','accesorios','nombre','protocolo','comentario','observaciones','kg','repes','rir/rpe'}
# "RPE EN LA SESIÓN (0-10)" y su errata "RPD EN LA SESIÓN" no son ejercicios.
RPE_ROW_RE = re.compile(r'rp[ed]\s+en\s+la\s+sesi', re.I)
SES_RE  = re.compile(r'sesi[oó]n\s*0*(\d+)', re.I)

def _colA_from_xlsx(path):
    """Genera (titulo_pestaña, [valores columna A]) desde un .xlsx local."""
    wb=load_workbook(path, read_only=True, data_only=True)
    for sh in wb.sheetnames:
        yield sh, [(row[0] if row else None) for row in wb[sh].iter_rows(values_only=True)]

def extract_exercises(source, verbose=False):
    """Lee el plan y devuelve {bloque: {(semana, dia): [ejercicios]}}.

    `source`: ruta a .xlsx local ó iterable de (titulo, columna_A) (p.ej. leído de
    Google Drive vía gspread). Solo se usa la columna A. Las pestañas que no sean
    una semana de plan se ignoran (nutrición, gráficos, movilidad…).
    """
    sheets = _colA_from_xlsx(source) if isinstance(source, str) else source
    out={}; mapping=[]; skipped=[]
    for sh, colA in sheets:
        dest = route_tab(sh)
        if dest is None:
            skipped.append(sh); continue
        bloque, wk = dest
        mapping.append((sh, bloque, wk))
        lk = out.setdefault(bloque, {})
        dia=0; order=0; block=None
        for a in colA:
            if not isinstance(a,str): continue
            t=a.strip(); low=t.lower()
            if not t: continue   # gspread devuelve '' en celdas vacías; ignóralas (como openpyxl->None)
            ms=SES_RE.match(t)
            if ms: dia=ms.group(1); order=0; block=None; continue
            if low in ('básicos','basicos'): block='básico'; continue
            if low=='accesorios': block='accesorio'; continue
            if low in SKIP or RPE_ROW_RE.match(low) or t in ('#N/A','-'): continue
            if t=='#REF!':
                if dia: order+=1; lk.setdefault((wk,dia),[]).append(dict(order=order,name='(cambiado/#REF)',block=block,bw=False))
                continue
            if dia==0: continue
            order+=1
            lk.setdefault((wk,dia),[]).append(dict(order=order,name=canon_exercise(t),block=block,
                                                   bw=any(k in low for k in BW)))
    if verbose:
        src = source.split('/')[-1] if isinstance(source,str) else 'drive'
        print(f"  [Plan {src}] pestaña -> (bloque, semana): {mapping}")
        print(f"  [Plan] pestañas ignoradas: {skipped}")
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
    bad_int=bool(re.search(r'RIR(?!\s*\d)',s,re.I))
    s=re.sub(r'@[\d.]+(?:-[\d.]+)?',' ',s)
    s=re.sub(r'RIR\s*\d+(?:-\d+)?\+?',' ',s,flags=re.I)
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
    # segundos (isométrico / tempo)
    had_secs=bool(re.search(r'\d+\s*"',s))
    s=re.sub(r'\d+\s*"',' SECS ',s)
    # separar núcleo numérico de palabras-nota (conservando espacios)
    s=re.sub(r'[xX]',' ',s)
    nums=[]; words=[]
    for tok in s.split():
        if tok in ('SECS','BANDA'): nums.append(tok)
        elif re.fullmatch(r'[\d.]+', tok):
            try: nums.append(float(tok))
            except: pass
        else: words.append(tok)
    if words: note.append(' '.join(words))
    return dict(raw=raw, nums=nums, rpe=corr if corr is not None else rpe, rir=rir,
                bad_int=bad_int, banda=banda, carga=carga,
                metros=(int(metros.group(1)) if metros else None),
                had_secs=had_secs, note=' | '.join(n for n in note if n))

def interpret(nums, anchor, bw, banda, metros, carga=None):
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
        ns=numeric[0] if numeric else 1
        kg=numeric[1] if len(numeric)>=2 else None
        return ns,kg,None,'distancia','distancia_m'
    if has_secs:
        if len(numeric)>=2: return numeric[0],None,numeric[1],'tempo',''
        return (numeric[0] if numeric else 1),None,None,'isometrico',''
    # Convención de Hugo: 3 números = series × peso × reps; 2 números = peso × reps
    # (1 serie; el peso se escribe siempre, 0 incluido para peso corporal); 1 = solo reps.
    # `anchor`/`bw` ya no hacen falta: la notación es inequívoca.
    if len(numeric)==3: return numeric[0],numeric[1],numeric[2],None,''
    if len(numeric)==2: return 1,numeric[0],numeric[1],None,''
    if len(numeric)==1: return 1,None,numeric[0],None,'incompleto'
    return None,None,None,None,'sin_datos'

def parse_keep(text, lookups):
    rows=[]; plani=None; bloque=None; week=dia=None; slot=0; exs=[]; cur_fecha=''; dolores={}

    def flush_no_hechos():
        # Si en una sesión Hugo registró MENOS ejercicios de los que el plan tenía,
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
        # Hugo los usa en el keep para dividir un plan de otro. No son ni bloques ni
        # ejercicios, pero sin filtrarlos se colaban como series fantasma —y "PLANI 2"
        # llegaba a contar como 1 serie, inflando la sRPE de la última sesión.
        if re.fullmatch(r'[-=_*·—\s]+', line): continue
        mpl=re.match(r'PLANI\s*(\d+)', line, re.I)
        if mpl:
            # El nº de plan etiqueta el eje de fuerza (P2B1S1). Va en el keep porque Hugo
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
            exs=lookups.get(bloque,{}).get((week,dia),[]); continue
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
        for p in segs:
            ns,kg,reps,sp,flag=interpret(p['nums'],anchor,bw,p['banda'],p['metros'],p.get('carga'))
            rpe,rir=p['rpe'],p['rir']
            if p['bad_int']: flag=(flag+' int_no_parseable').strip()
            if not has_excel: flag=(flag+' sin_excel').strip()
            # Intento a 0 reps: marca de fallo (el frontend lo pinta distinto y no es récord).
            # Un fallo es esfuerzo máximo por definición, así que se fija RPE 10: así destaca
            # en el detalle de fatiga aunque no se anotara el @. El peso extra que un fallo
            # mete en la carga (sRPE) lo aplica el frontend con su propio factor.
            if reps == 0:
                flag=(flag+' fallo').strip(); rpe,rir=10.0,None
            est,met=e1rm(kg,reps,rpe,rir) if (kg is not None and sp is None) else (None,None)
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
