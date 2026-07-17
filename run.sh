#!/usr/bin/env bash
#
# run.sh — actualiza los datos y levanta el dashboard Jarvis de un tirón.
# Portable: funciona en Linux/macOS y en Windows (Git Bash) — detecta solo
# la forma del venv (bin/ o Scripts/).
#
# Orden correcto: pipeline (lee todo lo nuevo y reescribe la hoja) -> backend
# (arranca DESPUÉS, así no sirve caché vieja) -> frontend.
#
# Uso:
#   ./run.sh                      # pipeline (últimos 120 días) + backend + frontend
#   ./run.sh --since 2026-06-01   # acota el rango del pipeline
#   ./run.sh --no-pipeline        # solo servir, sin tocar los datos

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8099
FRONTEND_DIR="$ROOT/dashboard/frontend"
BACKEND_DIR="$ROOT/dashboard/backend"

# --- flags -----------------------------------------------------------------
RUN_PIPELINE=1
PIPELINE_ARGS=()
if [[ "${1:-}" == "--no-pipeline" || "${1:-}" == "-n" ]]; then
  RUN_PIPELINE=0
  shift
fi
PIPELINE_ARGS=("$@")   # el resto (p.ej. --since 2026-06-01) va al pipeline

# --- venv (Linux/macOS: venv/bin — Windows: venv/Scripts) ------------------
# Usamos el python del venv por ruta explícita: equivale a activarlo, pero no
# depende del PATH de cada shell (Git Bash en Windows no lo resolvía bien).
if [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"
elif [[ -x "$ROOT/venv/Scripts/python.exe" ]]; then
  PY="$ROOT/venv/Scripts/python.exe"
else
  echo "✗ No encuentro el venv en $ROOT/venv. Créalo primero." >&2
  exit 1
fi

# --- 1) pipeline -----------------------------------------------------------
if [[ "$RUN_PIPELINE" -eq 1 ]]; then
  echo "▸ 1/3  Actualizando datos (status_pipeline.py)…"
  ( cd "$ROOT" && "$PY" status_pipeline.py "${PIPELINE_ARGS[@]}" )
else
  echo "▸ 1/3  (saltado: --no-pipeline)"
fi

# --- limpieza al salir -----------------------------------------------------
BACK_PID=""
cleanup() {
  echo ""
  echo "▸ Cerrando…"
  [[ -n "$BACK_PID" ]] && kill "$BACK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 2) backend ------------------------------------------------------------
echo "▸ 2/3  Backend en http://localhost:$BACKEND_PORT …"
( cd "$BACKEND_DIR" && exec "$PY" -m uvicorn main:app --port "$BACKEND_PORT" ) &
BACK_PID=$!

# espera a que /data responda (máx ~15s) para no arrancar el front antes de tiempo
for _ in $(seq 1 30); do
  if curl -sf -o /dev/null "http://localhost:$BACKEND_PORT/data"; then
    echo "  ✓ backend listo"
    break
  fi
  sleep 0.5
done

# --- 3) frontend -----------------------------------------------------------
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "▸ Instalando dependencias del frontend (primera vez)…"
  ( cd "$FRONTEND_DIR" && npm install )
fi

echo "▸ 3/3  Frontend en http://localhost:5173  (Ctrl-C para parar todo)"
# vite en primer plano: al hacer Ctrl-C, el trap mata también el backend
( cd "$FRONTEND_DIR" && exec npm run dev )