#!/usr/bin/env bash
# Despliega en la VM de GCP (jarvis). Existe para que el despliegue no dependa de
# recordar cómo se compila: el 2026-09-09 se subió dos veces un bundle compilado sin
# las variables de Vite y quedó con "localhost" dentro, así que desde el móvil la
# página cargaba y TODAS las peticiones fallaban con "Failed to fetch". Ahora la
# configuración vive en dashboard/frontend/.env.production y esto solo la usa.
#
# El `dist/` va por scp y no por git (está en .gitignore) porque `npm run build` se
# queda sin memoria en la e2-micro de 1 GB: se compila aquí y se sube ya hecho.
#
# Funciona en los DOS equipos. Desde el portátil hay que lanzarlo con el bash de Git
# ("C:\Program Files\Git\bin\bash.exe"), no con el `bash.exe` de system32, que es el de
# WSL: ahí dentro no está el gcloud autenticado.
set -euo pipefail

# NO tocar la conversión de rutas de MSYS (MSYS2_ARG_CONV_EXCL / MSYS_NO_PATHCONV) para
# arreglar nada aquí: en Git Bash el propio `gcloud` es un script que se pasa a sí mismo la
# ruta de gcloud.py, y desactivarla lo rompe con "can't open file C:\c\Users\...".
# Probado el 2026-09-12.

ZONA=us-central1-a
PROYECTO=health-boost-500507
CUENTA=hugogalvezu96@gmail.com   # La personal, no la otra cuenta de gcloud de la máquina
VM=jarvis
URL=https://jarvis.tailc3e57b.ts.net

gc() { gcloud "$@" --zone="$ZONA" --project="$PROYECTO" --account="$CUENTA" --quiet; }

echo "▸ 1/4  Comprobando que lo local está pusheado…"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "  (aviso) hay cambios sin commitear: la VM se quedará en el último commit de origin."
fi

echo "▸ 2/4  Compilando el frontend…"
( cd dashboard/frontend && npm run build >/dev/null )
# Red de seguridad: si por lo que sea el bundle sale con una URL absoluta, parar aquí
# en vez de desplegar algo que solo funciona desde el propio servidor.
if grep -rqo "http://localhost:80" dashboard/frontend/dist/assets/*.js; then
  echo "  ERROR: el bundle contiene localhost. ¿Falta dashboard/frontend/.env.production?" >&2
  exit 1
fi

echo "▸ 3/4  Subiendo…"
# Ruta relativa y dentro del repo, no /tmp: el /tmp de Git Bash no es el de Windows, así
# que una ruta absoluta POSIX es justo la que puede no sobrevivir al salto a gcloud.
# Relativa no necesita traducirse y vale igual en los dos equipos. El `trap` la borra
# aunque el scp falle a medias, para no dejarla asomando en `git status`.
TAR=dist.tgz
trap 'rm -f "$TAR"' EXIT
tar -czf "$TAR" -C dashboard/frontend dist
gc compute scp "$TAR" "$VM":dist.tgz >/dev/null

echo "▸ 4/4  Actualizando la VM…"
gc compute ssh "$VM" --command="
  set -e
  cd ~/health_booster
  git pull -q
  rm -rf dashboard/frontend/dist && tar -xzf ~/dist.tgz -C dashboard/frontend && rm ~/dist.tgz
  sudo systemctl restart jarvis jarvis-voz
  timeout 90 bash -c 'until curl -sf -o /dev/null http://127.0.0.1:8099/; do sleep 3; done'
  echo \"  commit desplegado: \$(git log --oneline -1)\"
"

echo "▸ Comprobando desde fuera…"
gc compute ssh "$VM" --command="
  for p in '/' '/data' '/formularios/estado' '/tts/salud'; do
    printf '   %-22s HTTP %s\n' \"\$p\" \"\$(curl -s -o /dev/null -w '%{http_code}' $URL\$p)\"
  done
"
echo "✓ Listo — $URL"
