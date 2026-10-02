# Reconstruir la VM desde cero

Hugo descartó pagar 0,25 €/mes por un snapshot del disco: prefiere volver a montarla a mano
las pocas veces que haga falta. **Esto es viable porque los datos NO viven en la VM**: están
en dos buckets de Cloud Storage, en la hoja de Google y en Drive, y todos sobreviven a
borrar la máquina. Lo único que se pierde al perderla es el tiempo de montarla — eso es lo
que ahorra este documento.

Los comandos de aquí son los que se ejecutaron de verdad el 2026-10-02 al migrar Jarvis a
esta máquina, no una receta escrita de memoria.

**La VM es compartida por DOS proyectos**: el screener (`/opt/swing-screener`, repo
`Hugo966/swing-screener`) y Jarvis (`/opt/health_booster`). Si solo se cae uno, saltar a su
parte; si hay que rehacer la máquina entera, de arriba abajo.

## 0. Lo que hay que saber antes

| | |
|---|---|
| Proyecto | `stock-screener-506508` |
| Cuenta | `hugogalvezu96@gmail.com` (NO la otra cuenta de gcloud de la máquina de Hugo) |
| SO | Ubuntu 24.04 LTS, Python 3.12 |
| Usuario | `hugo` |
| Buckets con los datos | `gs://swing-screener-respaldos` · `gs://jarvis-respaldos-health-boost` |

**Una e2-micro y 30 GB de disco: ni una más.** La capa gratuita de GCP da 720 h de e2-micro
y 30 GB **en total por cuenta de facturación, no por proyecto**. Tener dos VMs agotaba las
horas hacia el día 20 y a partir de ahí se cobraban las dos (4,35 € en septiembre de 2026).
Por eso Jarvis vive aquí y no en su propia máquina.

## 1. Crear la instancia

```bash
gcloud compute instances create swing-screener \
  --project=stock-screener-506508 --account=hugogalvezu96@gmail.com \
  --zone=us-central1-a --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard
```

`us-central1` no es opcional: la capa gratuita solo existe en `us-west1`, `us-central1` y
`us-east1`. Y **no quitarle la IP externa efímera**: sin ella la VM no llega a Sheets,
Intervals ni Anthropic, y Cloud NAT sí se cobra.

## 2. Base del sistema

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap -q /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip git cron
sudo timedatectl set-timezone UTC   # el crontab mezcla UTC y Madrid con CRON_TZ, ver §6
```

**El swap no es opcional**: con 969 MB de RAM, `pip install pandas` se queda sin memoria. En
marcha se usan ~510 MB con las dos cargas, y la tanda larga del screener pagina ~100 MB.

## 3. Acceso a los repos (privados)

Cada repo necesita **su propia** clave: GitHub no deja reutilizar una deploy key entre
repos. Por cada uno:

```bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/deploy_hb -q    # y ~/.ssh/deploy para el screener
cat >> ~/.ssh/config <<'EOF'
Host github-hb
  HostName github.com
  User git
  IdentityFile ~/.ssh/deploy_hb
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
```

Y desde la máquina de Hugo, con `gh` autenticado:
```bash
gh repo deploy-key add clave.pub --repo Hugo966/health_booster --title "swing-screener"
```

## 4. Jarvis

```bash
sudo mkdir -p /opt/health_booster && sudo chown hugo:hugo /opt/health_booster
cd /opt/health_booster
git clone -q github-hb:Hugo966/health_booster.git .
python3 -m venv venv && ./venv/bin/pip install -q -r dashboard/backend/requirements.txt

# Datos y secretos: del bucket, no de ninguna máquina
export CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE=  # si aún no hay clave, traerla a mano
gcloud storage cp gs://jarvis-respaldos-health-boost/jarvis.db .
```

El `.env` y el JSON del service account **no están en ningún bucket a propósito** (son las
credenciales que dan acceso a todo): los trae Hugo de su PC. Al copiarlos hay que corregir
dos rutas, que apuntan al home del usuario de donde vengan:

```
GOOGLE_SA_JSON=/opt/health_booster/health-boost-500507-54d3ae43862c.json
JARVIS_MULETILLAS=/opt/health_booster/muletillas
```

Las muletillas (52 MP3, 2 MB) se regeneran solas al arrancar el servicio de voz, pero
cuestan créditos de ElevenLabs: mejor copiarlas si se tienen.

### Units

```ini
# /etc/systemd/system/jarvis.service
[Unit]
Description=Jarvis — dashboard de bienestar (backend + frontend)
After=network-online.target
Wants=network-online.target
[Service]
User=hugo
# El cwd TIENE que ser dashboard/backend: los módulos se importan planos
# (import chat, import memoria) y uvicorn no los encuentra desde otro sitio.
WorkingDirectory=/opt/health_booster/dashboard/backend
ExecStart=/opt/health_booster/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8099
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

La de voz es igual con `WorkingDirectory=/opt/health_booster/dashboard/tts`,
`servidor_voz:app` y `--port 8123`.

**Los dos escuchan solo en `127.0.0.1`**: lo único que los expone es Tailscale.

### El frontend

No va por git (`dist/` está en `.gitignore`) porque `npm run build` se queda sin memoria en
1 GB. Se compila fuera y se sube: `./desplegar.sh` desde la máquina de Hugo lo hace entero.

## 5. Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sudo sh
sudo tailscale up --hostname=swing-screener   # IMPRIME UNA URL: la tiene que abrir Hugo
sudo tailscale serve --bg 8501                      # panel del screener, puerto 443
sudo tailscale serve --bg --https=8443 8099         # Jarvis
sudo tailscale serve --bg --https=8443 --set-path=/tts 8123
```

**El login es interactivo**: imprime una URL y hay que abrirla con la cuenta de Hugo. No se
puede automatizar sin una auth key.

**Jarvis va en el 8443 y no en el 443** porque el 443 lo ocupa el panel del screener. Su
frontend pide rutas absolutas (`/data`, `/tts`), así que colgarlo de un subdirectorio lo
rompería; cambiar de puerto lo deja en la raíz.

La config de `serve` se guarda en el estado de tailscaled y sobrevive a los reinicios.

## 6. El crontab, que es compartido

**El orden importa**: `CRON_TZ` aplica a las líneas que vienen DESPUÉS. El screener va en
UTC (sus tandas están atadas a cierres de mercado) y Jarvis en hora de Madrid.

```cron
45  6 * * 1-5  /opt/swing-screener/run.sh korea
50 16 * * 1-5  /opt/swing-screener/run.sh europe_dev
CRON_TZ=Europe/Madrid
30 0 * * 2-6  /opt/swing-screener/run.sh us; /opt/swing-screener/run.sh emerging
CRON_TZ=Europe/Madrid
0 0,6-23 * * * cd /opt/health_booster && ./venv/bin/python status_pipeline.py >> /opt/health_booster/pipeline.log 2>&1
30 3 * * * cd /opt/health_booster && ./venv/bin/python respaldar_memoria.py >> /opt/health_booster/respaldo.log 2>&1
35 3 * * * /opt/swing-screener/respaldar.sh >> /opt/swing-screener/respaldo.log 2>&1
```

**El `2-6` de la tanda larga no es un error.** Se movió de las 21:15 UTC a las 00:30 de
Madrid porque Hugo habla con Jarvis antes de medianoche. Al cruzar medianoche el cierre del
VIERNES cae en SÁBADO: con `1-5` se perdería sin que nadie se entere.

**Jarvis no tiene ningún cron entre las 00:00 y las 06:00**, que es justo donde cae la tanda
pesada del screener (puede durar 2h24). No es casualidad.

## 7. Los respaldos

Los dos buckets ya existen y sobreviven a la VM; solo hay que volver a poner los crons.

| Bucket | Qué | Cuándo |
|---|---|---|
| `gs://jarvis-respaldos-health-boost` | `jarvis.db` (conversaciones y hechos) | 03:30 |
| `gs://swing-screener-respaldos` | `state.sqlite`, `out/`, `.env` | 03:35 |

**La VM tiene scope `devstorage.read_only`**, así que no puede escribir en Storage por sí
misma y el IAM no lo arregla: los scopes de la instancia mandan por encima. Cambiarlos
obliga a pararla, así que los dos respaldos usan la clave del service account:

```bash
export CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE=/opt/health_booster/health-boost-...json
```

**Y verifican el resultado, que no es paranoia**: con los scopes mal, `gcloud storage cp`
imprimía el error y **salía con código 0**. Un cron a secas habría fallado cada noche en
silencio y el respaldo no habría existido el día que hiciera falta. Por eso
`respaldar.sh` comprueba que el fichero está en el bucket y tiene menos de 2 horas.

## 8. Comprobar que está bien

```bash
systemctl is-active jarvis jarvis-voz swing-panel
for p in / /data /formularios/estado /tts/salud; do
  curl -s -o /dev/null -w "$p %{http_code}\n" https://swing-screener.tailc3e57b.ts.net:8443$p
done
curl -s https://swing-screener.tailc3e57b.ts.net:8443/tts/salud   # elevenlabs debe ser true
/opt/swing-screener/respaldar.sh                                  # debe decir "ok: N bytes"
free -m                                                           # ~510 MB de 955 en reposo
```

Y la prueba que de verdad cierra el asunto: preguntarle a Jarvis algo que solo sepa por su
memoria (`¿quién es Daniel?`). Si contesta, `jarvis.db` se restauró bien.
