"""Arnés de comparación de proveedores — la MISMA conversación contra cada uno.

El objetivo de la Fase 2 es poder decidir el proveedor con datos, no de memoria:
se lanza un guion fijo de mensajes (sacado de una conversación real del usuario, con
los puntos donde el 3B flojea: inventarse cosas en un "hola", saber qué día es,
comentar el sueño, resumir sin soltar un informe, recordar un libro entre turnos)
contra cada modelo, y se imprime cada respuesta turno a turno con su latencia. Al
final, un resumen con tiempo, tokens y coste estimado por modelo.

Dos cuidados para que la comparación sea limpia:

  - **Base de datos temporal.** `recordar` y el hilo escriben en SQLite; si usara
    `jarvis.db` real, una tanda de comparación ensuciaría los hechos y el
    histórico. Se apunta `memoria.DB` a un fichero temporal que se borra al final.
  - **Sesión propia por modelo.** Cada uno arranca con el hilo vacío, así que ven
    exactamente los mismos mensajes y no se contaminan entre sí.

El briefing sí lee la hoja real (datos de verdad, que es lo que se quiere juzgar),
así que hace falta el .env con las credenciales de Google, igual que el chat. Para
los modelos de Anthropic hace falta ANTHROPIC_API_KEY en el .env.

Uso:
    python comparar.py                  # 3b vs sonnet vs opus (default)
    python comparar.py 3b haiku         # los alias que quieras
    python comparar.py 3b               # solo el local (humo, sin API key)
"""
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import memoria

# Alias -> (cómo forzar el proveedor, id de modelo para el precio). El 3B es local
# (sin coste), así que su precio es None.
PRESETS = {
    "3b":     ("ollama:qwen2.5:3b", None),
    "sonnet": ("anthropic:claude-sonnet-5", "claude-sonnet-5"),
    "opus":   ("anthropic:claude-opus-4-8", "claude-opus-4-8"),
    "haiku":  ("anthropic:claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
}

# $ por millón de tokens (tarifas públicas aproximadas de Anthropic; si cambian,
# se editan aquí). El cache de lectura va a ~10% del precio de entrada y el de
# escritura a ~125%, que es como Anthropic factura el prompt caching.
PRECIOS = {
    "claude-opus-4-8": {"in": 15.0, "out": 75.0},
    "claude-sonnet-5": {"in": 3.0, "out": 15.0},
    "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0},
}

# El guion. Cada línea es un mensaje del usuario; se envían en orden y el hilo se
# acumula, así que los turnos posteriores ven los anteriores (memoria dentro de
# la sesión). Editable a gusto: es lo que se está midiendo.
GUION = [
    "hola",
    "¿qué día es hoy?",
    "¿cómo he dormido esta noche?",
    "estoy leyendo Dune, me está enganchando",
    "hazme un resumen rápido de cómo estoy hoy",
    "¿te acuerdas qué libro te dije que estaba leyendo?",
]


def _coste(uso: dict, modelo_id: str | None) -> float:
    """Coste en $ de un uso de tokens. 0 si es local (sin precio)."""
    if not modelo_id or modelo_id not in PRECIOS:
        return 0.0
    p = PRECIOS[modelo_id]
    return (
        uso.get("in", 0) * p["in"]
        + uso.get("cache_read", 0) * p["in"] * 0.10
        + uso.get("cache_write", 0) * p["in"] * 1.25
        + uso.get("out", 0) * p["out"]
    ) / 1_000_000


def _correr(forzar: str, guion: list[str]) -> tuple[list[dict], float, dict]:
    """Reproduce el guion contra un proveedor. Devuelve (turnos, seg_total, uso_total)."""
    import chat  # tardío: arrastra briefing/sheets, que solo hace falta al correr

    sesion = f"cmp-{forzar}"
    turnos, total = [], 0.0
    uso_total = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    for mensaje in guion:
        t0 = time.perf_counter()
        r = chat.responder(sesion, mensaje, forzar_proveedor=forzar)
        dt = time.perf_counter() - t0
        total += dt
        for k in uso_total:
            uso_total[k] += r.get("uso", {}).get(k, 0)
        turnos.append({"usuario": mensaje, "texto": r["texto"],
                       "acciones": r["acciones"], "seg": dt, "uso": r.get("uso", {})})
    return turnos, total, uso_total


def _imprimir(resultados: dict, guion: list[str]):
    """Turno a turno, cada modelo debajo del mensaje del usuario, y resumen final."""
    for i, mensaje in enumerate(guion):
        print(f"\n{'=' * 72}\n[{i + 1}] HUGO: {mensaje}\n{'=' * 72}")
        for alias, res in resultados.items():
            if "error" in res:
                continue
            t = res["turnos"][i]
            acc = ""
            if t["acciones"]:
                acc = "  ·acciones: " + ", ".join(
                    a.get("tipo", "?") + str({k: v for k, v in a.items() if k != "tipo"})
                    for a in t["acciones"]
                )
            print(f"\n  ── {alias.upper()} ({t['seg']:.1f}s){acc}")
            for linea in (t["texto"] or "(sin texto)").splitlines():
                print(f"     {linea}")

    print(f"\n{'=' * 72}\nRESUMEN  (tiempo · tokens · coste estimado)\n{'=' * 72}")
    for alias, res in resultados.items():
        if "error" in res:
            print(f"  {alias.upper():8} NO se pudo ejecutar — {res['error']}")
            continue
        n = len(res["turnos"])
        u = res["uso"]
        toks = f"{u['in'] + u['cache_read'] + u['cache_write']}in/{u['out']}out"
        coste = res["coste"]
        cadena_coste = "local (~0 $)" if coste == 0 else f"${coste:.4f} ({n} turnos)"
        print(f"  {alias.upper():8} {res['total']:5.1f}s total · "
              f"{res['total'] / n:4.1f}s/turno · {toks:>18} · {cadena_coste}")
    print("\n  (Precios aprox. de Anthropic por Mtok; el 3B es local. Extrapola el "
          "coste/turno a tu uso diario real.)")


def main():
    # La consola de Windows es cp1252 y las respuestas (y las cajas de abajo)
    # llevan tildes, ñ y caracteres Unicode: sin esto, el print peta al imprimir.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    alias_pedidos = sys.argv[1:] or ["3b", "sonnet", "opus"]

    # Redirigir la memoria a un fichero temporal ANTES de que chat/memoria la usen.
    tmp = NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    memoria.DB = Path(tmp.name)
    memoria.init()

    try:
        resultados: dict = {}
        for alias in alias_pedidos:
            forzar, modelo_id = PRESETS.get(alias, (alias, None))
            print(f"\n>>> {alias} ({forzar}) …", flush=True)
            try:
                turnos, total, uso_total = _correr(forzar, GUION)
                resultados[alias] = {
                    "turnos": turnos, "total": total, "uso": uso_total,
                    "coste": _coste(uso_total, modelo_id),
                }
            except Exception as e:
                # El fallo típico es Anthropic sin ANTHROPIC_API_KEY: se avisa claro
                # y se sigue con los demás, para no perder lo que sí corrió.
                resultados[alias] = {"error": f"{type(e).__name__}: {e}"}
                print(f"    (falló: {type(e).__name__}: {e})")
        _imprimir(resultados, GUION)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
