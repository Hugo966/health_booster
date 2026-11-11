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

# Jarvis vive en la VM del screener desde el 2026-10-02: la capa gratuita de GCP da 720h
# de e2-micro y 30 GB de disco EN TOTAL por cuenta de facturación, no por proyecto, así
# que dos VMs agotaban las horas hacia el día 20 y a partir de ahí se cobraban las dos.
ZONA=us-central1-a
PROYECTO=stock-screener-506508
CUENTA=hugogalvezu96@gmail.com   # La personal, no la otra cuenta de gcloud configurada en la máquina
VM=swing-screener
RUTA=/opt/health_booster
# Puerto 8443 y no 443: el 443 de esta máquina lo ocupa el panel de Streamlit del
# screener. El frontend de Jarvis pide rutas absolutas (/data, /tts), así que colgarlo de
# un subdirectorio lo rompería; cambiar de puerto lo deja en la raíz.
URL=https://swing-screener.tailc3e57b.ts.net:8443

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
# TODO lo que toca $RUTA va como `hugo`. `gcloud compute ssh` entra con el usuario
# derivado de la cuenta de Google (hugogalvezu96_gmail_com), y desde la migración el
# repo y los ficheros son de `hugo`. Sin esto:
#   - `git pull` muere con "detected dubious ownership" (git se niega a operar sobre un
#     repo de otro usuario), y como hay `set -e` se lleva por delante el resto del
#     bloque: ni se extrae el dist ni se reinicia el servicio. Pasó el 2026-10-03 y el
#     despliegue parecía haber ido bien salvo por una línea de error.
#   - y el `rm -rf dist` tampoco podría: /opt/health_booster no es suyo.
# El .tgz pasa por /tmp porque el home del usuario con el que entras no tiene por qué
# ser legible para `hugo`.
gc compute ssh "$VM" --command="
  set -e
  sudo mv ~/dist.tgz /tmp/dist.tgz
  sudo chmod 644 /tmp/dist.tgz
  # -H pone HOME=/home/hugo. Sin eso sudo conserva el HOME de quien llama y git buscaría
  # ~/.ssh/config —donde vive el alias 'github-hb' con el que se clonó— en el home
  # equivocado, fallando con 'Permission denied (publickey)'.
  sudo -u hugo -H bash -c '
    set -e
    cd $RUTA
    git pull -q
    rm -rf dashboard/frontend/dist
    tar -xzf /tmp/dist.tgz -C dashboard/frontend
  '
  sudo rm -f /tmp/dist.tgz
  sudo systemctl restart jarvis jarvis-voz
  timeout 90 bash -c 'until curl -sf -o /dev/null http://127.0.0.1:8099/; do sleep 3; done'
  echo \"  commit desplegado: \$(sudo -u hugo -H git -C $RUTA log --oneline -1)\"
"

# El `.env` NO viaja en el despliegue (ni por git ni por el tar), así que una variable
# nueva se queda sin poner en la VM y no da error: simplemente el backend arranca con su
# valor por defecto. Aquí se avisa de la única que cambia lo que Jarvis DICE.
echo "▸ Comprobando la configuración de la VM…"
gc compute ssh "$VM" --command="
  if sudo grep -qE '^JARVIS_USUARIO=.' $RUTA/.env 2>/dev/null; then
    echo '   ✓ JARVIS_USUARIO puesto'
  else
    echo '   ⚠ FALTA JARVIS_USUARIO en $RUTA/.env — Jarvis llamará \"el usuario\" a quien le hable.'
    echo '     Arréglalo con:  echo JARVIS_USUARIO=TuNombre | sudo tee -a $RUTA/.env && sudo systemctl restart jarvis'
  fi
"

echo "▸ Comprobando desde fuera…"
gc compute ssh "$VM" --command="
  for p in '/' '/data' '/formularios/estado' '/tts/salud'; do
    printf '   %-22s HTTP %s\n' \"\$p\" \"\$(curl -s -o /dev/null -w '%{http_code}' $URL\$p)\"
  done
"
echo "✓ Listo — $URL"
