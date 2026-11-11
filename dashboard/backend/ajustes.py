"""Ajustes que pone el usuario desde la app, no el que la instala.

Clave/valor en una pestaña de la hoja, y no en el `.env`, por dos razones: el `.env` no
viaja en el despliegue —habría que entrar en la VM a mano cada vez— y sobre todo porque
esto son cosas que contesta QUIEN USA la app la primera vez que la abre, no quien la
monta. La hoja ya es el sitio donde las dos máquinas y la VM se ven.

Hoy solo vive aquí la ubicación para el tiempo. Es un clave/valor en vez de una pestaña
por ajuste porque es la forma más pequeña que admite el segundo.
"""
import os

import gspread

import formularios
import sheets

PESTANA = "ajustes"


def leer(clave: str, defecto=None):
    for f in sheets.fetch_all().get(PESTANA, []):
        if str(f.get("clave", "")).strip() == clave:
            valor = str(f.get("valor", "")).strip()
            return valor or defecto
    return defecto


def escribir(pares: dict) -> None:
    """Crea o pisa varias claves DE UNA VEZ.

    De una vez y no una por una porque cada escritura son tres peticiones a Google
    (metadatos, leer la columna, escribir) y la cuota de lectura por minuto se agota
    antes de lo que parece: guardar la ubicación son tres claves, o sea nueve peticiones
    hechas de la forma tonta.

    El `except` es SOLO de pestaña-no-existe. Siendo ancho, un 429 de cuota se disfrazaba
    de "no existe" e iba a crear una pestaña que ya estaba, y el error que salía por el
    log era el segundo, no el de verdad.
    """
    hoja = formularios.cliente().open_by_key(os.environ["SHEET_ID"])
    try:
        ws = hoja.worksheet(PESTANA)
    except gspread.WorksheetNotFound:
        ws = hoja.add_worksheet(title=PESTANA, rows=100, cols=2)
        ws.update([["clave", "valor"]], value_input_option="USER_ENTERED")

    columna = [str(v).strip() for v in ws.col_values(1)]
    cambios, nuevas = [], []
    for clave, valor in pares.items():
        if clave in columna[1:]:
            cambios.append({"range": f"B{columna.index(clave, 1) + 1}", "values": [[valor]]})
        else:
            nuevas.append([clave, valor])
    if cambios:
        ws.batch_update(cambios, value_input_option="RAW")
    if nuevas:
        ws.append_rows(nuevas, value_input_option="RAW")
    sheets.invalidar(PESTANA)
