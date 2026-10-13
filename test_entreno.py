#!/usr/bin/env python3
"""Comprobaciones del parser del keep y del plan.  `./venv/bin/python test_entreno.py`

Solo lo que duele si se rompe y no se nota a simple vista: un ejercicio mal nombrado o
una serie de más no dan error, salen como un número raro tres paneles más allá.
"""
import entreno_pipeline as ep


def plan(*nombres):
    """Lista de ejercicios como la devuelve el Excel, para no repetirla en cada caso."""
    return [dict(order=i, name=n, block='básico', bw=False) for i, n in enumerate(nombres, 1)]


def una(token, ejercicio='Plancha lateral', ejercicios=None):
    """Parsea UNA línea de keep y devuelve sus filas."""
    keep = f"PLANI 2\nBLOQUE 3\nSEM2 - DIA1 - 2026-10-12\n{token}\n"
    lk = {(2, 3): {('2', '1'): plan(*(ejercicios or [ejercicio]))}}
    return ep.parse_keep(keep, lk).to_dict('records')


# --- el plan: qué pestaña es qué etapa ---------------------------------------
assert ep.route_tab('Build II S2') == (2, 3, '2')      # BLOQUE 3 en el keep de Hugo
assert ep.route_tab('Build S2') == (2, 2, '2')         # y la etapa anterior sigue en su sitio
assert ep.nombre_etapa(2, 3) == 'Build II'
assert ep.route_tab('Nutrición') is None

# --- el calentamiento no ocupa slot ------------------------------------------
# Hugo no lo apunta en el keep. Si se queda, los nombres se corren un puesto. El mismo
# ejercicio aparece DOS veces en la hoja: bajo su cabecera y suelto al final de accesorios.
cols = ['Sesión 1', 'Warm up', 'Tibial raises', 'Básicos', 'Sentadilla',
        'Accesorios', 'Plancha lateral', 'Tibial raises', 'RPE EN LA SESIÓN (0-10)']
lk = ep.extract_exercises([('Build II S2', cols)])
assert [e['name'] for e in lk[(2, 3)][('2', '1')]] == ['Sentadilla', 'Plancha lateral']

# --- 0x0 (no lo hizo) NO es lo mismo que 200x0 (lo intentó y falló) ----------
no_hecho = una('0x0')[0]
assert no_hecho['flag'] == 'no_hecho'
assert no_hecho['n_series'] is None and no_hecho['volumen'] is None   # 0 carga, no 30 puntos
fallo = una('200x0@10')[0]
assert fallo['flag'] == 'fallo' and fallo['n_series'] == 1 and fallo['rpe'] == 10.0
assert fallo['e1rm'] is None                                          # sin repe no hay marca

# --- series compuestas por tiempo --------------------------------------------
# El número de antes de la x son las SERIES; los tramos de 30" no son series sueltas.
comp = una('2x30"-30"@7')[0]
assert comp['n_series'] == 2 and comp['nota'] == '30"+30" = 60s'
comp4 = una('2x30"-30"-30"-20"@7')[0]
assert comp4['n_series'] == 2 and comp4['nota'] == '30"+30"+30"+20" = 110s'
assert una('3x30"@7')[0]['nota'] == '30"'          # los segundos ya no se pierden
assert una("2x1'@7")[0]['nota'] == '60"'           # 1' es un minuto
assert una('3x8x2"RIR0')[0]['reps'] == 8           # tempo: 2" por repe, 8 repes

# --- el espacio separa series; sin espacio es un rango -----------------------
# (con un ejercicio que SÍ lleva peso: en la plancha y demás `SIN_CARGA` los dos
# números son series y repes, nunca kg.)
dos = una('2x7x10RIR0 - 6x10RIR0', 'Curl femoral')
assert len(dos) == 2 and dos[0]['n_series'] == 2 and dos[1]['n_series'] == 1
uni = una('6x10-8RIR3', 'Curl femoral')            # unilateral: 10 de un lado, 8 del otro
assert len(uni) == 1 and uni[0]['kg'] == 6 and uni[0]['reps'] == 9

print("OK")
