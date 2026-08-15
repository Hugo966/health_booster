"""Memoria persistente de Jarvis — SQLite local.

Son DOS memorias con propósitos distintos:

  - `conversaciones`: el hilo. Lo que dijimos hace cinco minutos, para que la
    charla tenga continuidad dentro de una sesión.
  - `hechos`: lo que hace que parezca un amigo y no un chatbot. Cosas de la vida
    de Hugo que debe recordar meses después ("está leyendo Shogun"), no números
    del dashboard — esos ya vienen del briefing y cambian solos.

El fichero .db NO va al repo (ver .gitignore): son conversaciones personales.

Se abre una conexión por operación en vez de mantener una global: FastAPI atiende
en varios hilos y sqlite3 no comparte conexiones entre ellos sin más. Al volumen
de una conversación humana el coste de abrir es irrelevante.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Junto al .env, en la raíz: dashboard/backend/memoria.py -> ../../jarvis.db
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "jarvis.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS conversaciones (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  sesion TEXT NOT NULL,
  ts     TEXT NOT NULL,
  rol    TEXT NOT NULL,
  texto  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_sesion ON conversaciones(sesion, id);

CREATE TABLE IF NOT EXISTS hechos (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  tema            TEXT NOT NULL,
  texto           TEXT NOT NULL,
  fecha_alta      TEXT NOT NULL,
  ultima_mencion  TEXT NOT NULL,
  veces           INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_hechos_tema ON hechos(tema);
"""


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    """Crea las tablas si no existen. Idempotente: se puede llamar en cada arranque."""
    with _conn() as con:
        con.executescript(ESQUEMA)


# --- el hilo de la conversación ---------------------------------------------

def guardar_mensaje(sesion: str, rol: str, texto: str):
    """`rol` es 'usuario' o 'jarvis'."""
    with _conn() as con:
        con.execute(
            "INSERT INTO conversaciones (sesion, ts, rol, texto) VALUES (?,?,?,?)",
            (sesion, _ahora(), rol, texto),
        )


def hilo_reciente(sesion: str, n: int = 20) -> list[dict]:
    """Últimos n mensajes de la sesión, en orden cronológico."""
    with _conn() as con:
        filas = con.execute(
            "SELECT rol, texto FROM conversaciones WHERE sesion = ? "
            "ORDER BY id DESC LIMIT ?",
            (sesion, n),
        ).fetchall()
    return [dict(f) for f in reversed(filas)]


def hilo_con_id(sesion: str, n: int = 40) -> list[dict]:
    """Como `hilo_reciente` pero con `id` y `ts`. Lo usa la UI para enterarse de lo que
    se habla por el micro (dashboard/escucha), que entra por el backend sin pasar por el
    navegador: sin esto, esas burbujas no aparecían nunca en pantalla."""
    with _conn() as con:
        filas = con.execute(
            "SELECT id, ts, rol, texto FROM conversaciones WHERE sesion = ? "
            "ORDER BY id DESC LIMIT ?",
            (sesion, n),
        ).fetchall()
    return [dict(f) for f in reversed(filas)]


# --- lo que sabe de Hugo -----------------------------------------------------

def recordar(tema: str, texto: str) -> int:
    """Guarda un hecho. Si ya existe idéntico en el mismo tema, lo refresca.

    La deduplicación es por texto exacto, así que "lee Shogun" y "lee Shogun, va
    por la mitad" conviven como dos hechos. Es a propósito: preferimos duplicar
    de vez en cuando a perder un matiz. `olvidar()` limpia lo que sobre.
    """
    tema, texto = tema.strip(), texto.strip()
    with _conn() as con:
        fila = con.execute(
            "SELECT id FROM hechos WHERE tema = ? AND texto = ?", (tema, texto)
        ).fetchone()
        if fila:
            con.execute(
                "UPDATE hechos SET veces = veces + 1, ultima_mencion = ? WHERE id = ?",
                (_ahora(), fila["id"]),
            )
            return fila["id"]
        cur = con.execute(
            "INSERT INTO hechos (tema, texto, fecha_alta, ultima_mencion) VALUES (?,?,?,?)",
            (tema, texto, _ahora(), _ahora()),
        )
        return cur.lastrowid


def hechos_relevantes(limite: int = 30) -> list[dict]:
    """Los hechos que van al prompt.

    Mientras quepan todos, van todos. Cuando no quepan, se mezclan los más
    recientes con los que llevan más tiempo sin mencionarse: los primeros dan
    contexto de lo que pasa ahora, los segundos son los que permiten que Jarvis
    saque un tema que Hugo daba por olvidado, que es justo la gracia.
    """
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) c FROM hechos").fetchone()["c"]
        if total <= limite:
            filas = con.execute(
                "SELECT * FROM hechos ORDER BY fecha_alta DESC"
            ).fetchall()
            return [dict(f) for f in filas]

        mitad = limite // 2
        recientes = con.execute(
            "SELECT * FROM hechos ORDER BY fecha_alta DESC LIMIT ?", (mitad,)
        ).fetchall()
        vistos = {f["id"] for f in recientes}
        olvidados = con.execute(
            "SELECT * FROM hechos ORDER BY ultima_mencion ASC LIMIT ?", (limite,)
        ).fetchall()

    salida = [dict(f) for f in recientes]
    for f in olvidados:
        if len(salida) >= limite:
            break
        if f["id"] not in vistos:
            salida.append(dict(f))
    return salida


def marcar_mencionado(id_hecho: int):
    """Jarvis acaba de sacar este tema: que no vuelva a salir el primero mañana."""
    with _conn() as con:
        con.execute(
            "UPDATE hechos SET ultima_mencion = ? WHERE id = ?", (_ahora(), id_hecho)
        )


def olvidar(id_hecho: int):
    with _conn() as con:
        con.execute("DELETE FROM hechos WHERE id = ?", (id_hecho,))
