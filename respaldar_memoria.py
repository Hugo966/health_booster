#!/usr/bin/env python3
"""Sube la memoria de Jarvis (jarvis.db) a una carpeta de Drive.

Es lo ÚNICO del proyecto sin copia en ningún sitio: los datos de salud viven en la hoja,
el keep en un documento de Drive, el código en git y las claves están en las dos máquinas
del usuario. Esto son sus conversaciones y los hechos que Jarvis ha ido aprendiendo — si la VM
desaparece, olvida quién es su entrenador.

Lo ejecuta la VM, no las máquinas del usuario, y eso es a propósito: la VM está siempre
encendida, así que no depende de que él encienda un equipo ni de montar un programador
distinto en Linux y en Windows. Antes esto tiraba desde el PC con un timer de systemd, que
no existe en el portátil.

Va a Cloud Storage y NO a Drive, aunque el keep sí viva en Drive: un service account no
puede ser propietario de ficheros en Drive ni con una carpeta compartida —no tiene cuota—,
y la salida que propone Google son las unidades compartidas, que piden Workspace. En GCP
no hay ese problema, y el bucket es independiente de la VM: borrarla no lo toca.

SIEMPRE ESCRIBE EL MISMO OBJETO en vez de uno por día. El bucket tiene versionado, así que
el histórico lo guarda él y la rotación y el borrado de copias viejas salen gratis.

El bucket va en JARVIS_BUCKET del .env; sin esa variable, esto no hace nada y no molesta.
"""
import os
import sqlite3
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

DB = RAIZ / "jarvis.db"
BUCKET = os.getenv("JARVIS_BUCKET", "").strip()
NOMBRE = "jarvis.db"


def _sesion():
    cr = Credentials.from_service_account_file(
        os.environ["GOOGLE_SA_JSON"],
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
    cr.refresh(Request())
    return {"Authorization": f"Bearer {cr.token}"}


def main() -> int:
    if not BUCKET:
        print("(aviso) sin JARVIS_BUCKET en el .env; no se sube nada.")
        return 0
    if not DB.exists():
        print(f"(aviso) no encuentro {DB}")
        return 0

    # Comprobar la base ANTES de subirla: subir un fichero corrupto encima del bueno sería
    # peor que no tener respaldo, porque parecería que sí lo hay.
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM conversaciones").fetchone()[0]
    h = con.execute("SELECT COUNT(*) FROM hechos").fetchone()[0]
    con.close()

    datos = DB.read_bytes()
    r = requests.post(
        f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o",
        params={"uploadType": "media", "name": NOMBRE},
        headers={**_sesion(), "Content-Type": "application/octet-stream"},
        data=datos, timeout=120)
    r.raise_for_status()
    print(f"respaldo subido: {n} mensajes, {h} hechos, {len(datos)} bytes "
          f"(generación {r.json().get('generation')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
