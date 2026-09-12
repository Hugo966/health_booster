# Jarvis — Dashboard de bienestar · Handoff de contexto

> Resumen autocontenido para continuar el proyecto en una sesión nueva.
> Usuario: Hugo (powerlifter). Idioma de trabajo: español. Código y comentarios en español.

## 0. LO PRIMERO — pendientes del 2026-09-12 (leer antes de tocar nada)

Escrito en el portátil al cerrar la sesión. Cada punto lleva el porqué, porque el orden
importa y saltárselo tiene consecuencias.

### URGENTE si nadie lo ha hecho ya: una fila falsa en `wellness_pm`
Probando lo de la memoria de personas con el modelo real, Jarvis ejecutó `guardar_pm` de
verdad y dejó **una fila inventada del `2026-09-12`** (energía 7, sensación 6, RPE 8,
notas "Entrené con Cristina"). Se aisló la base de datos pero **no la hoja**.

No pisó nada de Hugo —esa fecha no existía; su último PM real era el del 11/09— así que
**borrar esa fila lo deja como estaba**. Importa porque el semáforo da el PM de hoy por
hecho cuando no lo está, y `rpd_sesion` es la señal de "ese día entrenó": en cuanto pase
el pipeline, contamina el sRPE. **El AM del 12/09 SÍ es suyo, ese no se toca.**
Detalle y cómo no repetirlo, en §15.

### Lo que se cerró el 2026-09-12 (no rehacerlo)
- **La voz funciona desde el móvil.** Android no se comporta como el Chrome de
  escritorio, y **ninguna de sus diferencias da error**: el micro es exclusivo (el VAD
  dejaba sordo al reconocedor), repite la frase entera en cada resultado (tres "hola"
  llegaban como veinticinco) y manda los números dictados como dígitos (un "cinco" se
  perdía en el filtro de ruido). **Todo el detalle en §14 — leerlo antes de tocar
  `voz.ts`.**
- **Hay traza de voz en pantalla** (`TrazaVoz.tsx`), que se enciende con **`?vozdebug=1`
  en la URL**. Se hizo porque en el móvil no hay consola, y cerró el diagnóstico en un
  minuto. **Si algo de voz falla en el teléfono, eso es lo primero, no lo último.**
- **El chat ya se alcanza en el móvil.** El gesto estaba atado a `wheel`, que en táctil no
  existe; el hilo no estaba escondido, **medía 0 px**.
- **Jarvis pregunta por la gente que no conoce** y distingue dos personas con el mismo
  nombre (§15).
- **`desplegar.sh` corre desde el portátil.** Hace falta el bash de Git
  (`C:\Program Files\Git\bin\bash.exe`), **no** el `bash.exe` de `system32`, que es el de
  WSL y no tiene dentro el gcloud autenticado. Y **no** tocar `MSYS_NO_PATHCONV` para
  arreglar nada ahí: rompe el propio lanzador de gcloud.
- **`claude_sesion.txt` no estaba ignorado**: el `.gitignore` lo tenía con las palabras al
  revés (`sesion_claude.txt`). Ahora están los dos nombres, porque cada equipo lo bautizó
  a su manera.

**PENDIENTE de comprobar en el móvil** (nada de esto se ha probado con Hugo delante, solo
con tests y un móvil simulado): que dudando no le corte, que las respuestas cortas
lleguen, que la muletilla tarde, y sobre todo **cortarle por voz**, que sigue sin
confirmarse — ver el final de §14, que dice qué número mirar en la traza.

### Segunda vuelta, también del 2026-09-12 (§16)
Hugo probó lo anterior desde el móvil y salieron tres fallos más, ya arreglados:
- **El chat seguía sin poder abrirse.** El botón de ampliar un panel solo aparece con
  `group-hover`, y **en táctil no hay hover**: invisible en TODOS los paneles. Van tres
  fallos del mismo tipo (el gesto de `wheel`, este botón, y el hover en general). **Si
  añades una interacción, pregúntate cómo se hace con un dedo.**
- **Dudar seguía cortándole**: `DUDA` solo valía si la vacilación venía sola, y en Android
  el final trae la frase entera. Ahora se mira también el final de lo acumulado.
- **Cortarle le borraba la pregunta del hilo.** Le preguntó a qué valor le cambiaba la
  energía, Hugo dijo "a 7" y contestó "7 qué, tío". No era el reconocedor, era la memoria:
  al cancelar no se guardaba NADA. Ahora se guarda lo emitido, marcado.
- Y **lee las notas de los formularios por su cuenta** para preguntar por lo que pone ahí.

**Pieza nueva: `rapido.py`**, un modelo de Groq que escribe la muletilla a medida en vez
de sacarla del bote de pregrabadas. **Ya está configurado y probado con la clave de Hugo**
(`GROQ_MODELO=groq/compound-mini`, ~1,5 s). Falta lo único que no se puede medir: si a él
le gusta más una coletilla a medida pero plana que una pregrabada con retintín pero
genérica. Si no le convence **se apaga vaciando `GROQ_MODELO`**, sin tocar código.
Ojo: la clave va en el `.env`, que NO viaja por git — **la VM necesita la suya**.
El porqué de cada decisión, al final de §16.

### Lo que se cerró el 2026-09-11 (no rehacerlo)
- **La VM ya es usable de verdad**: las claves de Anthropic y ElevenLabs están puestas,
  el chat responde con Sonnet y la voz sale por ElevenLabs. `/tts/salud` dice
  `"elevenlabs": true`. La memoria de la VM **empieza de cero a propósito** (decisión de
  Hugo): la del portátil no se migra, se va llenando con el uso. Comprobado que
  `recordar` dispara y guarda bien.
- **El personaje está partido en dos constantes** (`personalidad.py`): `PERSONAJE` (2.938
  car., solo carácter) y `OPERACION` (5.776 car., el manual de herramientas). Había
  crecido a nueve secciones de las que **solo tres iban del personaje**, y los formularios
  solos ocupaban más que el tono, la voz y el bajar el tono juntos; mezclados, tocar el
  carácter arriesgaba el manejo de herramientas y al revés. **Fue una reorganización pura,
  verificada línea a línea: 123 antes, 123 después, ninguna perdida ni añadida.** Para
  iterar el tono ahora se toca `PERSONAJE` y ya.
- **Lo que caduca sale de los datos, no del prompt** (principio de Hugo). `QUÉ SABES DE ÉL`
  decía "acaba de peaking y entra en offseason" desde julio, y Jarvis lo afirmaba tan
  tranquilo en septiembre estando en Build. Ahora el prompt solo lleva lo permanente y
  **la etapa la dice el parte de estado**. Para eso hicieron falta dos cosas:
  `PLAN_TAB_RULES` gana una 4ª columna con el NOMBRE de la etapa (Build, Peaking,
  Offseason, Volumen), y `entreno_sesion` gana la columna **`plani`**, que se había
  quedado fuera al agregar por sesión — sin ella "bloque 2" es ambiguo, porque Hugo
  reinicia la numeración con cada plan.
- **Otro `except` ancho tapando un `ImportError`**: `briefing.py` importaba
  `entreno_pipeline` confiando en que otro módulo hubiera metido la raíz en `sys.path`, y
  cuando fallaba el nombre de la etapa desaparecía en silencio. Ahora el `sys.path` se
  ajusta explícito y el import va arriba, sin `try`.
- **`anthropic` deja de estar comentado en `requirements.txt`.** El import sigue siendo
  perezoso, pero con Anthropic como proveedor por defecto en todas las máquinas, no
  tenerlo hace que el chat responda 500 en cuanto alguien escribe.

**Al tocar el prompt, reiniciar el servicio.** `sudo systemctl restart jarvis` — se quedó
sin reiniciar y se estuvo probando contra el Jarvis viejo un buen rato.

### Lo que se cerró el 2026-09-06 (no rehacerlo)
- **A Jarvis ya se le puede interrumpir** —con el botón y hablándole encima— y **espera a
  que Hugo termine** antes de contestar. Probado en vivo por él y dado por bueno.
- Por el camino salieron **cuatro fallos que no eran de voz**, los cuatro arreglados: la
  herramienta `dia` leyendo datos caducados, dos formas distintas de romper el guardado
  de formularios, y Jarvis quedándose mudo sin decir por qué.
- **Todo el detalle, y las perillas para reajustar la voz, en §13.** Leerlo antes de
  tocar `voz.ts` o `vad.ts`: casi todos esos números están donde están por una prueba
  concreta, no por gusto.
- **Queda una prueba sin hacer**, y la pidió Hugo: que **solo le calle SU voz**. Está
  comprobado que el eco de Jarvis no le corta y que la voz de Hugo sí, pero no la tele,
  otra persona hablando, el teclado ni una respiración fuerte. El fallo sería invisible
  —parecería que Jarvis "se corta solo"—, así que hay guion de prueba en §13.

### Lo que se cerró el 2026-09-04 (no rehacerlo)
- **Sincronización: hecha.** El commit suelto del que avisaba el handoff anterior ya está
  en `origin`. El punto de limpiar el histórico queda desbloqueado.
- **Los formularios por voz funcionan de verdad**, probados con el modelo real y no con
  `ProveedorFalso`: Jarvis escribió el PM del 04/09 (energía 7, sensación 6, cafeína 0,
  RPE 6) y el upsert corrigió la fila en vez de duplicarla.
- Salieron **tres fallos de esa prueba, los tres arreglados** (detalle en §12).

### 1. Volcar el keep y pasar el pipeline
`keep.txt` no tiene las sesiones del **02/09, 03/09 y 04/09** (el semáforo las canta en
rojo: hay RPE en el formulario pero no hay sesión). Y **el pipeline no pasa desde el
21/08**, así que `derived_diario` arrastra el HRV, el sueño y los pasos clavados en el
20/08, más el `sRPE_series` vacío de ese día. Volcar primero y pasar el pipeline después,
para que entre todo de una vez.

### 2. Máquina en GCP + Tailscale (es lo siguiente que quiere Hugo)
La idea: que **el dashboard deje de depender de que el portátil esté encendido**, y poder
entrar desde el móvil. Va antes que la app porque la app necesita justo esto.

Cabe en la **always-free** de GCP, pero solo la mitad ligera — y el corte cae donde el
proyecto ya está partido:

| Componente | ¿Cabe en la e2-micro (1 GB)? |
|---|---|
| Backend FastAPI | Sí — mide **121 MB** en marcha |
| Frontend ya compilado + pipelines por cron | Sí |
| Chat con `JARVIS_PROVEEDOR=anthropic` | Sí: el modelo corre en Anthropic, no en la VM |
| TTS (`dashboard/tts/`) | **No**: torch + Qwen3-TTS son ~4 GB de VRAM y no hay GPU |
| Ollama | **No**: `qwen2.5:7b` no entra en 1 GB |

El TTS se queda en el portátil y ya está previsto: sin servidor de voz, `voz.ts` cae a la
voz del navegador.

Trampas, por orden de probabilidad de comérselas:
1. **`npm run build` se queda sin memoria en 1 GB.** Compilar el frontend fuera y subir
   el `dist/`, o poner 2 GB de swap.
2. La always-free solo existe en **`us-west1` / `us-central1` / `us-east1`** (~100-130 ms
   desde España; se nota un poco en el chat, nada en el panel).
3. **1 GB de egress al mes.** El JSON y el bundle no lo rozan; audio sí lo fundiría, pero
   el audio no va a estar ahí.
4. **No quitarle la IP externa efímera**: sin ella la VM no llega a Sheets ni a Intervals,
   y Cloud NAT sí se cobra. Es gratis mientras la instancia está encendida.
5. **Alerta de presupuesto a 1 €**: la free tier pide tarjeta.

Tailscale encaja **mejor en la VM que en el portátil**: metiéndola en el tailnet no hace
falta abrir ni un puerto público. Receta en `docs/app_movil.md` (el login es interactivo,
lo tiene que hacer Hugo). Ojo: si el backend se va a la VM y el TTS se queda en el
portátil, el navegador llama al TTS por la IP de tailnet del portátil — hay que repasar a
dónde apunta `voz.ts`.

### 3. Investigar si Intervals se actualiza al toque
Sigue haciendo falta **entrar y pulsar refrescar**; no basta con abrir la app. El
2026-09-10 el HRV entró en el tercer intento del pipeline (t+156 s) y pareció que había
entrado solo — pero Hugo lo había refrescado a mano esa mañana, así que ese caso **no es
evidencia de nada**. Lo único demostrado sigue siendo que el bucle de reintentos aguanta
el rato que tarda la sincronización en aterrizar, no que la dispare.

**Para saberlo de verdad hace falta un día en que Hugo NO lo toque**, y comprobar si el
pipeline acaba viendo el HRV. Hasta entonces, no darlo por resuelto: es el cuello de
botella del cron, porque con la máquina sola no hay quien pulse ese botón.

Lo que ya se sabe (2026-08-21): Intervals **no guarda el HRV**, lo
busca al proveedor de forma perezosa y **solo cuando se refresca SU interfaz** (la app o
la web de Intervals.icu; la de Zepp se probó y no vale). Por la API no hay forma de
dispararlo. El campo `updated` distingue "no hay dato arriba" de "me sirven caché". Falta
confirmar si eso sigue igual y si hay forma de que no dependa de abrir la app a mano —
porque en la VM, con el pipeline por cron y nadie mirando, esto se vuelve el cuello de
botella de verdad.

### 4. Limpiar el histórico (ya desbloqueado)
Receta en **`docs/publicar_repo.md`**. Al hacer el repo público se publica **todo el
histórico**, no el estado final: el árbol ya está neutralizado, pero los commits viejos
conservan la redacción que identifica las máquinas.

Dos trampas: **borrar `docs/publicar_repo.md`** antes del force-push (cita literalmente
las cadenas que purga) y **volver a clonar en las dos máquinas** después, porque los
hashes cambian y un `pull` normal no sirve.

### 5. Y entonces sí, la app
Decisiones ya cerradas en `docs/app_movil.md` — no volver a plantearlas. El motor que va a
consumir (API de formularios, semáforo, herramientas de voz) está terminado y en `main`.

### Suelto, cuando toque
- Probar por voz que una zona desconocida se resuelve bien: decirle "me dolió el pie" y
  comprobar que ofrece **Tobillo** en vez de tragárselo (ver §12).
- El navegador arrastra en `localStorage` la sesión vieja `web-mrtkdqd6-l9noua`, así que
  no comparte hilo con el micro externo, que escribe en `hugo` (`chat.ts:58`).

---

## 0-bis. LA VM DE GCP (montada el 2026-09-09)

El dashboard **ya no depende de que el portátil esté encendido**. Corre en una e2-micro de
la capa gratuita de GCP y se entra por Tailscale, también desde el móvil.

**Dirección:** `https://jarvis.tailc3e57b.ts.net` — solo dentro del tailnet, no expuesta a
internet. El móvil de Hugo (`poco-f6-pro`) ya está en el tailnet: basta abrir la app.

| Dato | Valor |
|---|---|
| Proyecto | `health-boost-500507` (el mismo del service account) |
| Instancia | `jarvis`, e2-micro, `us-central1-a`, 30 GB pd-standard |
| Cuenta | `hugogalvezu96@gmail.com`, config de gcloud `jarvis-personal` |
| Código | `~/health_booster`, clonado con una **deploy key de solo lectura** |

**Cómo está montado, y por qué así:**
- **Un solo proceso sirve API y frontend.** `main.py` monta el `dist/` con `StaticFiles` al
  final del fichero (las rutas de la API se registran antes y ganan). Así todo va por
  `:8099` y en el MISMO origen: sin CORS, sin contenido mixto, y `tailscale serve` solo
  tiene que exponer un puerto. En desarrollo no existe `dist/` y no se monta nada, así que
  Vite sigue igual.
- **El frontend se compila FUERA y se sube.** `npm run build` se queda sin memoria en 1 GB.
  Se manda el `dist/` en un tar por `gcloud compute scp` (está en `.gitignore`).
- **2 GB de swap.** Con 969 MB de RAM, `pip install pandas` reventaba. En marcha se usan
  ~530 MB con los dos servicios.
- **El servicio de voz corre AQUÍ, no en el portátil.** Lo que ataba `servidor_voz.py` a la
  3060 era el respaldo XTTS, que se carga perezosamente; **ElevenLabs es una API en la nube
  y no necesita GPU**. Por eso la voz buena funciona en el móvil sin encender el portátil.
  Aquí XTTS nunca se cargará: si ElevenLabs falla, `voz.ts` cae a la voz del navegador.
  El aviso del handoff de que "el audio fundiría" el giga de egress gratis no se sostiene:
  MP3 a 128 kbps son ~16 KB/s, o sea ~145 MB/mes a 30 respuestas diarias, un 15%.
- **`tailscale serve` enruta por rutas**: `/` → `:8099` y `/tts` → `:8123`. El frontend se
  compila con `VITE_API_BASE=` y `VITE_TTS_URL=/tts`, ambos relativos al mismo origen.
- **Los dos servicios escuchan solo en `127.0.0.1`.** Lo único que los expone es el tailnet.
- `systemd`: `jarvis` (backend, cwd en `dashboard/backend` porque los imports son planos) y
  `jarvis-voz`. Ambos con `Restart=always`.
- **Cron a las 00:00 y cada hora de 6:00 a 23:00** (`0 0,6-23 * * *`, zona
  `Europe/Madrid`), log en `~/pipeline.log`. De 1:00 a 5:00 no se pasa: no hay
  formularios ni entrenos nuevos a esas horas y cada pase quemaría los 5 min completos de
  reintentos contra Intervals esperando un HRV que aún no existe. Coste medido por pase: ~2 llamadas a Intervals, 26
  lecturas de pestañas del plan en Drive y 12 de la hoja; la cuota de Sheets son 300
  peticiones **por minuto** y sin tope diario, así que sobra de largo.
- **Despliegue: `./desplegar.sh`.** Compila, sube el `dist`, hace `git pull` en la VM,
  reinicia y comprueba las cuatro rutas. Existe porque el 2026-09-09 se desplegó dos veces
  un bundle compilado a mano sin las variables de Vite: quedó con `http://localhost:8099`
  dentro y desde el móvil **la página cargaba pero todo fallaba con "Failed to fetch"**
  (localhost es el móvil). Ahora la configuración vive en
  `dashboard/frontend/.env.production`, que Vite lee sola en `npm run build`, y el script
  **aborta antes de subir** si detecta un localhost en el bundle.

**El keep vive ahora en Drive.** Documento de Google llamado **Entreno**
(`KEEP_DOC_ID=1IuHf7hcu00huaFd-SQQDAE1faQaEjBR7h4UQUPZzx0M`), compartido con el service
account y exportado como `text/plain` por `entreno_pipeline.leer_keep()`. Resuelve dos
cosas de golpe: la VM no tiene fichero local, y las dos máquinas de Hugo dejan de
desincronizarse. Si no hay `KEEP_DOC_ID`, se sigue leyendo `KEEP_TXT` del disco.

**Google Docs "corrige" al escribir y eso rompía el parser en silencio**: convierte el
guion de separar series en raya (`–`) y la comilla de los tempos (`2"`) en tipográfica,
y añade un BOM. `normalizar_texto()` lo deshace **al leer**, no en el parser, para que el
keep local siga comportándose igual. Es la trampa más probable si algún día el keep de
Drive deja de parsear.

### Pendientes que salieron del despliegue (2026-09-10)

**1. El readiness del día llega tarde, y el cron solo lo tapa.**
El readiness sale de `derived_diario`, que solo regenera el pipeline. Hugo rellena el
formulario AM cuando se levanta, a hora variable, así que hasta el siguiente pase de cron
sigue viendo el de AYER. Pasó el 2026-09-10: a las 7:37 el dashboard decía 62 (el del 09)
cuando con su formulario de esa mañana salía 73,3.

Parcheado subiendo el cron a **cada hora** (00:00 y 6:00-23:00), pero eso es tapar el síntoma:
sigue habiendo hasta una hora de desfase.

El arreglo de verdad es **calcular el readiness en vivo desde `wellness_am`/`wellness_pm`**,
el mismo patrón que ya usa `huecos.py` (leer las pestañas ORIGEN, no la tabla derivada).
Con eso sería correcto al instante y sin depender de ningún cron.
**El peligro es duplicar la fórmula**, y este proyecto ya se quemó con eso: el panel de
Carga calculaba el sRPE en TypeScript mientras la hoja guardaba otra fórmula con el mismo
nombre, y Jarvis contradecía a la pantalla. Así que **no reescribirla**: hay que extraer
`readiness()` de dentro de `consolidate()` (`status_pipeline.py`) a una función que usen
los dos, y que siga habiendo una sola definición.

**2. `write_tab` vacía la pestaña antes de escribirla.**
Hace `ws.clear()` y luego `update()`, con ~1 s de pestaña vacía entre medias. Si el hilo
`_mantener_datos_calientes` del backend refresca justo en esa ventana, **cachea el vacío y
el dashboard sale en blanco hasta 4 minutos**. Con dos pases al día era despreciable; con
18 son 90 ventanas diarias. Se arregla escribiendo desde A1 sin `clear()` y limpiando solo
el sobrante.

### Lo que falta en la VM
- **`ANTHROPIC_API_KEY` y `ELEVENLABS_API_KEY`.** Solo existen en el `.env` del portátil
  (los proveedores no las vuelven a mostrar), así que hay que llevarlas desde allí:
  ```bash
  grep -E '^(ANTHROPIC_API_KEY|ELEVENLABS_API_KEY|ELEVENLABS_VOICE_ID|ELEVENLABS_MODELO)=' .env > /tmp/claves.env
  gcloud compute scp /tmp/claves.env jarvis:~/ --zone=us-central1-a --project=health-boost-500507
  gcloud compute ssh jarvis --zone=us-central1-a --project=health-boost-500507 \
    --command="cat ~/claves.env >> ~/health_booster/.env && rm ~/claves.env && sudo systemctl restart jarvis jarvis-voz"
  rm /tmp/claves.env
  ```
  Correcto cuando `/tts/salud` diga `"elevenlabs": true`. Sin ellas el chat no responde y
  la voz cae a la del navegador; el resto del dashboard funciona entero.
- **`GROQ_API_KEY` y `GROQ_MODELO`** (las muletillas a medida, §16), por lo mismo: el
  `.env` no viaja por git. Misma receta, cambiando el `grep`:
  ```bash
  # Desde el PORTÁTIL hay que lanzarlo con el bash de Git, no con el de system32 (WSL).
  # Nombre de fichero RELATIVO, no /tmp: el /tmp de Git Bash no es el de Windows.
  grep -E '^GROQ_' .env > claves_groq.env
  gcloud compute scp claves_groq.env jarvis:claves_groq.env \
    --zone=us-central1-a --project=health-boost-500507 --account=hugogalvezu96@gmail.com --quiet
  gcloud compute ssh jarvis --zone=us-central1-a --project=health-boost-500507 \
    --account=hugogalvezu96@gmail.com --quiet \
    --command="cat ~/claves_groq.env >> ~/health_booster/.env && rm ~/claves_groq.env && sudo systemctl restart jarvis"
  rm claves_groq.env
  ```
  Sin ellas NO falla nada: `rapido.disponible()` da False y se usan las muletillas
  pregrabadas de siempre. El síntoma sería "no noto ninguna diferencia".
- **Alerta de presupuesto**: la capa gratuita pide tarjeta. Conviene una alerta a 1 €.
- **Probar el chat por el tailnet**: va por SSE (`/chat/stream`). El código manda
  `X-Accel-Buffering: no`, pero quien tiene que no bufferizar ahora es `tailscale serve`.
  Si el texto llega de golpe en vez de fluido, es eso.
- **No quitarle la IP externa efímera**: sin ella la VM no llega a Sheets ni a Intervals, y
  Cloud NAT sí se cobra. Es gratis mientras la instancia está encendida.

### Actualizar la VM
```bash
gcloud compute ssh jarvis --zone=us-central1-a --project=health-boost-500507 \
  --command="cd ~/health_booster && git pull && sudo systemctl restart jarvis jarvis-voz"
```
Si cambió el frontend, además hay que compilar fuera y subir el `dist/`.

---

## 1. Objetivo del proyecto
Dashboard personal de bienestar ("Jarvis") que consolida datos de salud y entreno
de Hugo para leer de un vistazo su estado (readiness, HRV, sueño, carga de entreno,
progresión de fuerza, peso corporal y correlaciones). Foco principal del usuario:
**deporte + descanso**. Sin IA en Fase 1. Hoja de cálculo de Google como "hub" de datos.

Roadmap (ver `roadmap.md`):
- **Fase 1 — Dashboard core (EN CURSO)**: 7 gráficos fijos, tema oscuro, lectura de la hoja hub. Sin IA.
- **Fase 2 — Chat "Jarvis"**: caja de texto en lenguaje natural → Claude devuelve gráfico ad-hoc o respuesta. (Incluye "v1 con voz").
- **Fase 3 — Automatizar el pipeline** (cron / GitHub Actions / Cloud Run).
- **Fase 4 — Insights proactivos** (alertas por bajón de HRV, etc.).
- Principio: cada fase se planifica cuando la anterior lleva ≥2 semanas usada.

## 2. Arquitectura y flujo
```
Fuentes de datos                Pipelines Python            Hub                 Backend            Frontend
─────────────────               ─────────────────           ───────────         ─────────          ─────────
Intervals.icu API   ─┐
Google Forms (AM/PM) ─┼─> status_pipeline.py ──> Google Sheet ──> FastAPI /data ──> React SPA
Excel plan (Drive)   ─┤        (consolida)        "Health_booster_data"   (gspread RO,      (Vite, Recharts)
keep.txt (log)       ─┴─> entreno_pipeline.py ─┘  pestañas:               cache 5 min)
                               (parsea log)        derived_diario,
                                                   entreno_sesion,
                                                   entreno_sets, rm1, peso
```
Flujo: los pipelines LEEN las fuentes y REESCRIBEN la hoja → el backend arranca
DESPUÉS (para no servir caché viejo) y expone `/data` (JSON de las pestañas) →
el frontend lee `/data` una vez y renderiza todo en cliente.

`run.sh` orquesta todo: 1) `status_pipeline.py` (últimos 120 días por defecto)
→ 2) backend uvicorn en :8099 (espera a que `/data` responda) → 3) frontend Vite en :5173.

## 3. Estado actual del desarrollo (Fase 1, casi completa)
Paneles y su estado:
| Panel | Estado |
|---|---|
| Readiness (hero) | ✅ Terminado: cajas de umbral 40/65, bandas de color, X-axis regular, gradiente por banda |
| HRV | ✅ Terminado: color por zona, racha dinámica, tooltip con día de semana y "tu rango normal" |
| Sueño | ✅ Terminado: objetivo 7.5h (línea gruesa sobre las barras + caja de valor), minutos en dormirse (medio y peor) |
| Carga | ✅ Terminado: sRPE como métrica principal; detalle de fatiga en 3 tabs (básicos/accesorios/combinado) |
| Fuerza | ✅ Terminado: PESO como métrica principal; accesorios agrupados por grupo muscular con drill-down (chip o clic en línea); estrellas ★ de PR (récord histórico) en peso/e1RM |
| Peso | ✅ Terminado: compacto = última pesada + cambio vs anterior; ampliado = ritmo kg/sem en 3 ventanas (4/6/12); 3 medias móviles (4 principal + 6/12 tenues); puntos coloreados vs tendencia según dirección; tooltip con día y desviación. Dominio Y con holgura ±1 kg a propósito |
| Correlaciones | ✅ Terminado: Tonelaje→sRPE (4 celdas: sRPE día + sRPE 7d, × readiness y × molestias); agrupadas en 2 bloques (Estilo de vida / Entreno); etiqueta de fuerza por celda (insignificante→muy fuerte); reflexión determinista por bloque (plantilla, sin IA). sRPE día aún "n insuf"; sRPE_7d ya da número |

Infra: tema oscuro Jarvis, animaciones que respetan `prefers-reduced-motion`,
zoom FLIP al ampliar panel, hash-routing (`/#fuerza` compartible y persistente).

## 4. Decisiones técnicas (qué y por qué)
- **sRPE en vez de tonelaje para Carga**: el tonelaje premia el volumen (sube en
  sesiones ligeras de muchas series). sRPE = RPE de sesión × nº de series → métrica
  validada en ciencia del deporte. El RPE de sesión lo rellena Hugo en el formulario
  PM y lo seguirá rellenando (los vacíos son de antes de existir el forms PM). El
  tonelaje se mantiene como métrica secundaria, no la principal.
- **"Series duras" como métrica de volumen exercise-agnostic**: series con RIR≤2 /
  RPE≥8 (landmark de hipertrofia). Es la métrica por defecto en los grupos musculares
  de accesorios porque, cambiando de ejercicios, el tonelaje no permite progresión medible.
- **PESO (kg del top set) como métrica principal de Fuerza, NO e1RM**: Hugo quiere ver
  lo que sube cada semana, no la proyección al 1RM. El e1RM va a otra vista/página.
- **Combinado de fatiga** = (max RPE de básicos + media RPE de accesorios) / 2.
- **Variantes NUNCA se fusionan con su básico**: Banca comp ≠ Banca 3ct ≠ Banca mid grip
  (son estímulos distintos). Ver `lib/exercises.ts` COMPETICION.
- **Sueño: cama ≠ dormido**: el reloj (Intervals) mide horas DORMIDAS; el formulario AM
  da el TIEMPO EN CAMA. Su diferencia = minutos en dormirse (latencia; incluye
  microdespertares breves e inconscientes que Hugo no recuerda). Rellenar dormido con
  tiempo en cama inflaría el sueño → noches sin medir por el reloj salen solo como barra difusa.
- **Bandas/percentiles siempre sobre TODO el histórico**, el rango solo recorta lo que se
  dibuja (si no, "alto para Hugo" cambiaría al cambiar de 90D a 30D). Igual con la paleta
  de colores por ejercicio (una variante no debe cambiar de color al mover el rango).
- **Recharts**: `ReferenceArea` para bandas de valor exacto (mapea al eje; un gradiente
  de fill se comprime al bbox de la línea, no al eje); `ReferenceLine` con SVG label
  custom para cajas de valor; hover highlight vía `activeDot.onMouseEnter`; drill-down por
  clic en línea enganchado al hover activo (el `onClick` de línea de Recharts es poco fiable).
- **Animaciones**: Recharts anima con JS (clip-path), no basta la @media CSS → se apaga
  desde `lib/theme.ts` (`anim.on`). Zoom FLIP con Web Animations API + cleanup que cancela
  (StrictMode duplica los efectos de montaje).

## 5. Archivos importantes
### Raíz `/home/hugo/Documents/health_booster/`
- `status_pipeline.py` — pipeline principal. Lee Intervals.icu (HRV, sueño dormido,
  despertares) + formularios AM/PM de la hoja; consolida en `derived_diario`
  (readiness 0-100, sRPE, lags, tiempo_en_cama_h, eficiencia_sueno, latencia_min…).
  Reintentos de Intervals si falta el HRV de AYER (`INTERVALS_REINTENTOS`, `INTERVALS_ESPERA_S`).
  `informe_frescura()` avisa de retraso por fuente. ESCRIBE: objetivo, entreno_sets,
  entreno_sesion, rm1, derived_diario.
- `entreno_pipeline.py` — parsea `keep.txt` (log de entreno) cruzándolo con el plan (Excel).
  Salida por fila-serie: bloque, semana, dia, fecha, slot, ejercicio, tipo(básico/accesorio),
  especial, token, n_series, kg, reps, rpe, rir, e1rm, volumen, nota, flag, dolor_sesion.
  **Parser fail-proof** (ver §10).
- `keep.txt` — log de entreno que escribe Hugo a mano.
- `run.sh` — orquestador (pipeline → backend → frontend). Flags: `--no-pipeline`/`-n`,
  `--since YYYY-MM-DD`.
- `.env` — secretos (ver §7). `health-boost-500507-*.json` — Service Account de Google.
- `roadmap.md`, `dashboard_spec_fase1.md` — documentación de intención.

### Backend `dashboard/backend/`
- `main.py` — FastAPI, un endpoint `GET /data` → `fetch_all()`. CORS abierto.
- `sheets.py` — cliente gspread cacheado (TTL 300s), SOLO lectura.
  TABS = `["derived_diario","entreno_sesion","rm1","peso","entreno_sets"]`.
  Lee `.env` de la raíz. Pestaña que falle → lista vacía (no rompe).
- `rapido.py` — modelo rápido de **Groq** que escribe la muletilla a medida (§16). Habla
  API de OpenAI (la que expone Groq), sin SDK, y **apagado mientras falte `GROQ_MODELO` o
  `GROQ_API_KEY` en el `.env`**. Cualquier fallo devuelve `None` y se usan las
  pregrabadas: nunca puede dejar a Jarvis callado ni retrasarle.

### Frontend `dashboard/frontend/src/`
- `App.tsx` — raíz. Carga `/data`, construye las series por panel, RangeSelector global,
  hash-routing (`useWidgetEnHash`), overlay `Expanded` con origen para el zoom FLIP.
  Widgets: readiness, hrv, sueno, carga, fuerza, peso, correlaciones.
- `components/Readiness.tsx` — hero + `ReadinessExpanded`. Cajas umbral, bandas, gradiente por banda.
- `components/HrvTrend.tsx` — color por zona, racha (`RACHA_AVISO=3`), tooltip con día y rango normal.
- `components/SleepPanel.tsx` — barras apiladas (dormido sólido + "en dormirte" difuso +
  "en cama sin medir"), línea objetivo 7.5h encima, minutos en dormirse medio/peor.
- `components/LoadPanel.tsx` — sRPE principal, bandas percentil sobre histórico,
  `DetalleFatiga` con 3 tabs (basicos/accesorios/combinado). `rpeEff` clamp 0-10.
- `components/StrengthTrend.tsx` — PESO principal. `aggEjercicios` (top set por max kg
  por ejercicio×semana; `pat` opcional filtra grupo), `aggGrupos` (por patrón muscular,
  volumen/series/duras). Accesorios agrupados por grupo muscular con drill-down: entrar
  por chip O por clic en la línea (`onClave`). Métricas: básicos [peso, e1RM, volumen];
  grupos [series duras (def.), volumen]. Compact = básicos peso (altura fija 229 px, ver §9).
  **PRs ★**: `prsDe(aggFull)` marca las semanas de nuevo máximo histórico (sobre `todos`, no el
  rango; la 1ª semana no cuenta). El `dot` del `Grafico` (`hazDot`) pinta ★ amarilla (#ffdd59, no el
  color de la línea, para que destaque) en esos puntos. Solo en **básicos** (`cat === "basico"`) y
  en métricas donde "más = mejor" (peso/e1RM); variantes, accesorios, grupos y volumen/duras no llevan.
- `components/WeightTrend.tsx` — peso corporal + objetivo editable (persiste en localStorage
  vía `lib/goal.ts`). Puntos de pesada coloreados por posición vs tendencia (`DotPeso` +
  `colorDelta`): al **subir**, encima de la media móvil = verde y debajo = rojo; al **bajar**,
  invertido; justo en la línea (±0.05 kg) = amarillo. Tres medias móviles: **MA4 principal**
  (`tendencia`, con glow) + MA6 y MA12 tenues detrás (`tendencia6`/`tendencia12`, strokeOpacity
  0.38/0.2) para el rumbo a mes y medio / 3 meses. Resúmenes (lo que Hugo pidió ver):
  **compacto** (`Delta`) = última pesada + cambio vs la penúltima ("81.2 kg ▲ 0.3 kg vs anterior");
  **ampliado** = maqueta HUD: hero `PesoActual` (peso grande + Δ vs anterior) + `TablaRitmos`
  (fila de `TileRitmo`, un tile por ventana con barra de color superior) con el ritmo kg/sem en
  4 ventanas: 4/6/12 pesadas + **histórica** (`RITMOS` con `ritmoVentana`; n=null → todo el historial).
  **Callout `Estimacion`** (solo con meta, caja cian con ◎): proyecta la fecha de llegada a la meta
  con `ritmoPonderado` = media ponderada de los 4 ritmos (pesos 4/3/2/1, más a lo reciente, la
  histórica ancla). Color de estado (verde/rojo/ámbar por dirección) siempre con flecha, no solo color. Todos los números
  de resumen usan `todo` (historial completo, prop nueva pasada desde App), NO el rango — el rango
  solo recorta lo que dibuja el gráfico. Se quitó el ETA único y "actual=tendencia" (confundían: un
  ritmo único sobre 90D daba ~0.12 kg/sem aunque la última pesada saltara +0.3). Tooltip custom (`TooltipPeso`) con día
  de semana + desviación de la pesada vs tendencia. Dominio Y con holgura ±1 kg (`floor(lo-1)`/
  `ceil(hi+1)`): se probó apretarlo pero a Hugo le lee mejor la tendencia con aire, no pegada a los datos.
- `components/CorrelationHeatmap.tsx` — heatmap de correlaciones (Spearman, `MIN_N=14`). `PARES`
  (objetos con `bloque` e `interp`) incluye 4 pares de carga en **sRPE** (`sRPE` diario y `sRPE_7d`
  acumulado, × readiness y × molestias); se retiró el tonelaje. Celdas agrupadas en 2 bloques
  (`BLOQUES`: "vida"/"entreno"). **Compacto**: las 2 más representativas de cada bloque
  (`representativas()` = mayor |r| con dato) → 2×2 (columna por bloque), a la altura de Fuerza/Peso.
  **Ampliado**: los 8 pares en 2×2 por bloque (`grid-cols-2`) con encabezado `Titulo` + reflexión.
  Cada celda muestra etiqueta de **fuerza** (`fuerza()`: insignificante→muy fuerte por |r|) con
  color en escala rojo→verde (`fuerzaColor`/`FUERZA_COLOR`) + punto con glow (la "lucecita").
  `<Reflexion>` genera por bloque una frase **determinista** (plantilla, sin IA) nombrando las
  correlaciones representativas (n≥MIN_N y |r|≥`R_SIGNIF`=0.2) y su lectura vía `interp(r)`,
  coloreada por `bueno(r)` → verde (buena) / rojo (mala) / ámbar (ambigua, p.ej. reverse-causation).
  La IA de Fase 2 podrá sustituirla. Celda con `n<14` → "n insuf".
- `components/Panel.tsx` — tarjeta compacta. **OJO: alturas de panel en px fijos** (ver §8).
  Excepción razonada: el panel del chat es mínimo en estrecho, porque no lleva gráfico y
  con 263 px clavados el orbe tapaba el campo de escribir en el móvil (§14).
- `components/Expanded.tsx` — overlay ampliado + zoom FLIP (Web Animations API).
- `components/TrazaVoz.tsx` — **el visor de la traza de voz**, en pantalla y por portal a
  `document.body`. Se enciende con `?vozdebug=1` en la URL (o el `localStorage`
  `jarvis.voz.debug`) y trae botón de copiar. Existe porque **en el móvil no hay consola**,
  y es lo primero que hay que mirar si la escucha falla ahí (§14).
- `components/RangeSelector.tsx` — 7D/14D/30D/90D; `inRange`, `rangeStart`, tipo `Range`.
  No se le pasa a formularios ni al chat: ninguno de los dos es una serie temporal, y en
  360 px se salía 103 px por la derecha.
- `lib/api.ts` — `fetchData()`, `num()`, tipo `SheetData`.
- `lib/exercises.ts` — clasificación: `COMPETICION=["Sentadilla LB","Banca comp","Sumo dl"]`,
  `categoria()` (basico/variante/accesorio), `patron()` (grupos musculares por regex EN ORDEN),
  `bloqueSemana`/`bsOrden`.
- `lib/theme.ts` — paleta Jarvis, PALETTE (12 colores), panelStyle, tooltipStyle,
  `anim` (respeta reduced-motion), bandas readiness.
- `lib/stats.ts` — `mean`, percentiles, etc. `lib/goal.ts` — objetivo de peso en localStorage.

## 6. Cambios de esta sesión

### Sesión 2026-09-12 (que la voz funcione desde el móvil, y que pregunte quién es Daniel)
Primera sesión usando el dashboard **desde el teléfono** de verdad, y ahí se cayó todo lo
que en el portátil iba bien: Jarvis hablaba pero no oía, el chat no se podía ni abrir, y
las respuestas cortas se perdían. **Ninguno de esos fallos daba error**; es la moraleja de
la sesión, y por eso lo primero que se construyó fue la traza en pantalla y no el arreglo.
Tres diferencias de Android contra el Chrome de escritorio, todas silenciosas: micro
exclusivo, la frase repetida entera en cada resultado, y los números dictados como
dígitos. **Detalle en §14.**

Aparte, Jarvis ya **pregunta por la gente que no conoce** y distingue dos personas con el
mismo nombre; lo que no era obvio es que la mitad del trabajo estaba en la memoria, no en
el prompt: rotando los hechos, acababa repreguntando quién es Daniel. **§15.**

Tocado: `voz.ts` (mucho), `TrazaVoz.tsx` (nuevo), `ChatPanel.tsx`, `App.tsx`,
`memoria.py`, `personalidad.py`, `chat.py`, `desplegar.sh`, `.gitignore`.
Commits `5be4c79` y `83da6d3`.

### Sesión 2026-09-06 (interrumpir a Jarvis por voz, y que espere a que termines)
Hugo pidió tres cosas de conversación: poder cortarle, que no conteste antes de que él
acabe, y que el orbe signifique "he terminado" en vez de "apágate". Las tres están.
Salieron además cuatro fallos que no tenían nada que ver con la voz. **Todo en §13.**

### Sesión 2026-09-04 (probar los formularios con el modelo real, y arreglar lo que salió)
Sesión de verificación, no de features: se estrenó con el modelo de verdad el camino de
escritura que el 24/08 solo se había probado con `ProveedorFalso`. **Funciona** —Jarvis
rellenó el PM del 04/09 hablando y el upsert corrigió la fila sin duplicarla— pero por el
camino salieron tres fallos, los tres arreglados. **El detalle está en §12**, que conviene
leer entero antes de tocar `formularios.py` o `sheets.py`.

En corto: una zona de dolor que no está en el vocabulario (`pie`) se guardaba como celda
vacía y encima borraba lo que hubiera; un fallo de lectura de la hoja se cacheaba 5 minutos
como "no hay datos" y dejaba el panel en blanco, como si se hubieran perdido meses de
registros; y nada de eso llegaba a ningún log. Tocados: `formularios.py`, `sheets.py`,
`personalidad.py`, `run.sh` y `.gitignore`.

### Sesión 2026-08-24 (formularios propios: API de escritura, semáforo y relleno por voz)
Primer camino de ESCRITURA del proyecto. Hasta ahora los datos diarios solo entraban por
Google Forms: si a Hugo se le olvidaba un día nadie se lo decía, y el dato se perdía.
Ahora se pueden rellenar **y corregir** desde la app, hablando con Jarvis, y hay un
semáforo de lo que falta. Los Google Forms siguen vivos y siguen siendo la vía principal.

1. **`dashboard/backend/formularios.py` (nuevo)** — `ESQUEMA` declara los tres formularios
   con sus campos y rangos, y es la **fuente única**: la UI (`/formularios/esquema`), la
   validación y las descripciones de las herramientas salen de ahí. `guardar()` hace
   **upsert por fecha**, actualizando solo las celdas de los campos recibidos, para que
   una corrección parcial por voz no borre lo que ya había. NO usa `write_tab` del
   pipeline (es clear+reescritura: sobre `wellness_am` sería destructivo).
2. **Dos cosas de la hoja que costó descubrir y condicionan la escritura**: las columnas de
   fecha y hora guardan **valores numéricos**, no texto → `USER_ENTERED`; y el texto libre
   necesita `RAW` o un `=` inicial se vuelve fórmula. Van en dos llamadas separadas.
   Además **ya había fechas duplicadas** en la hoja, así que el upsert edita la ÚLTIMA
   coincidencia (la que gana en `consolidate()`) y lo dice en `avisos`.
3. **`dashboard/backend/huecos.py` (nuevo)** — el semáforo, contra un calendario y leyendo
   las pestañas ORIGEN. Vigila form AM, form PM, peso (10 días de tolerancia: es semanal),
   RPE de sesión y frescura del keep. Tres estados: `ok` / `pendiente` / `falta`, porque
   con dos estaría en rojo todas las mañanas.
4. **`briefing.py` reclamaba RPEs ya rellenados.** Miraba `derived_diario.sRPE_series`, que
   solo se rellena cuando corre el pipeline; un RPE puesto después se veía como ausente.
   Comprobado en vivo: el 2026-08-20 tenía `rpd_sesion`=7 en `wellness_pm` y `sRPE_series`
   vacío. Ahora ese aviso lo da `huecos`. **También decía mal las escalas** ("Molestias
   1-10" cuando son 0-9).
5. **Jarvis rellena formularios hablando** — `guardar_am`, `guardar_pm`, `guardar_peso` y
   `estado_formularios` (10 herramientas en total, `HERRAMIENTAS_ESCRITURA` es lista
   aparte porque tocan los datos de Hugo). El modo es híbrido: extrae lo que pueda de una
   parrafada, guarda, y la propia escritura **devuelve qué campos faltan**, así preguntar
   no gasta otra vuelta de `MAX_VUELTAS`. `personalidad.py` le obliga a leer de vuelta lo
   apuntado con los números: es el mecanismo de seguridad contra que alucine un valor.
6. **Panel Formularios** (`FormulariosPanel.tsx` + `lib/formularios.ts`): semáforo por
   fuente, tira de los últimos 14 días (AM arriba, PM abajo, punto en los días con
   entreno) y editor precargado con lo que ya hay. Las escalas se pintan como fila de
   botones 1-9 con el 5 marcado como "normal". Chips de zona con `data-no-expand`.
7. **Dos bugs de fuera del alcance, arreglados de paso**: el hilo que mantiene caliente la
   caché dormía 240s pero pedía con el TTL de 300s, así que daba acierto de caché y el
   refresco real caía cada ~480s; y el CORS estaba en `*` con endpoints que ahora
   escriben, así que se limitó a localhost y LAN privada.

**QUÉ FALTA (en el portátil):** la app móvil Expo. Plan, decisiones ya tomadas y pasos
previos —incluido el montaje de Tailscale— en **`docs/app_movil.md`**. Toda la API de esta
sesión es lo que va a consumir.

### Sesión 2026-08-18 (una sesión mala, legible: parser + señales a Jarvis)
Salió de una pregunta de Hugo: "¿pillaría Jarvis una sesión de mierda?". No la pillaba, y
buscándolo aparecieron 8 bugs, 5 de ellos corrompiendo datos en silencio.

1. **`@?` y `RIR?` significan "no pude valorar el esfuerzo"** (dolor, lesión, contra el
   reloj), NO son errores de tecleo. Llevan flag propio **`sin_intensidad`**, separado de
   `int_no_parseable` (esa sí es basura: `RIRmario`, un `RIR` sin número): mezclarlos deja
   los dos inservibles como señal. Esas series **suman volumen pero no generan e1RM**, así
   que no pueden optar a un PR — un récord no puede salir de una serie marcada justo porque
   algo iba mal.
   Además el `@?` **perdía datos**: el borrado de RPE era `@[\d.]+` y no casaba `@?`, así que
   `115x1@?` dejaba el token `1@?` fuera del núcleo numérico y la serie se guardaba como
   **115 REPES sin peso** (kg, volumen y e1RM perdidos).
2. **Cuatro bugs más de parseo**, todos la misma forma —un número leído como otra magnitud—,
   encontrados auditando el keep entero en busca de valores imposibles:
   - Farmer walk sin nº de series (`32.5x20m`) leía el **peso como 32,5 SERIES**: una sesión
     con 120 series en vez de 26, inflando el sRPE de esa semana entera.
   - Peso sin repes (`77.5@8`) se guardaba como 77,5 repes. Ahora se resuelve contra los kg
     de las series hermanas de la misma línea (±5 kg) **y** con techo de repes plausibles
     (`REPS_MAX_PLAUSIBLE = 20`, medido: p99 = 16): sin ese techo, en un accesorio de 2 kg la
     ventana de 5 kg convertiría 6 repes en 6 kg.
   - **Ejercicios que nunca llevan carga** escriben series × repes, no peso × repes. No se
     puede decidir por los números ni por "es peso corporal" —una dominada también lo es y
     ahí `5x3` sí son 5 kg lastrados—, así que va por **nombre de ejercicio**:
     `entreno_pipeline.SIN_CARGA`. Hoy: rueda abdominal, planchas, step down lateral,
     W slides. **El `0x0` queda fuera de la regla**: es la marca de serie fallada, y leerlo
     como "0 series" la borraría de la carga.
   - Tempo con tres números (`2x4x12x2"`) descartaba el tercero. La comilla ya identifica
     cuál es el número de segundos, así que los que quedan siguen la convención normal.
3. **El sRPE se calcula UNA sola vez**, en `status_pipeline` → `derived_diario.sRPE_series` +
   `sRPE_series_7d` (ventana de 7 días naturales). Antes `LoadPanel.tsx` lo recalculaba en
   TypeScript mientras la hoja guardaba otra fórmula con el mismo nombre (`sRPE` = rpd ×
   duración), así que **Jarvis podía contradecir la pantalla**. El panel ahora **consume** la
   columna; el `FACTOR_FALLO = 3` que queda en el TSX es solo para el texto explicativo.
   **No reintroducir la fórmula en el frontend.**
4. **Jarvis ya ve cómo fue la sesión**, no solo cuándo: la línea del último entreno lleva
   fallos y series sin valorar (`n_fallos_total`, `n_sin_intensidad_total`), y el bloque de
   notas incluye el dolor. Ojo con el dolor: está **duplicado a propósito** y no se pasan las
   dos fuentes a la vez (ver §11).
5. **`drive_lookups` fallaba en silencio.** Su `except: continue` no distinguía "pestaña de
   gráfico sin columna A" de "la API ha fallado". Medido: **2 de cada 7 lecturas devolvían el
   plan con semanas enteras ausentes**, y esas sesiones se habrían escrito en la hoja sin
   nombre de ejercicio, sin `tipo` y fuera de `vol_basicos`/`rm1`. Ahora reintenta 5 veces con
   espera creciente (3-6-12-24 s) y **aborta en voz alta** si lo perdido es una pestaña de
   plan, en vez de escribir datos degradados.
6. **`rm1` ya lleva `plani` en la clave** del groupby: Hugo reinicia la numeración de bloques
   con cada plan, así que el bloque 3 de PLANI 2 se habría fusionado con el de PLANI 1. Nota:
   **hoy `rm1` no lo consume nadie** (el panel de Fuerza calcula desde `entreno_sets`).
7. **Columnas nuevas en la hoja**: `derived_diario` gana `sRPE_series`, `sRPE_series_7d` y
   `n_sin_intensidad_total`; `entreno_sesion` gana `n_sin_intensidad_total`. `write_tab`
   escribe el df tal cual, así que entran solas.

### Sesión 2026-08-15 (voz + bugs de conversación)
1. **Voz resuelta con ElevenLabs v3** (ver §9.4 para el detalle completo): nuevo servicio
   `dashboard/tts/servidor_voz.py` con respaldo XTTS perezoso. Qwen3-TTS descartado por
   lento (113 s vs 1,4 s en la misma frase).
2. **Etiquetas de intención** (`[sarcastic]`…): Jarvis las escribe (`personalidad.py`), se
   mandan al TTS y se filtran al pintar el chat y en los motores que no las entienden.
3. **Máquina de estados de la voz rediseñada** (`voz.ts`) a petición de Hugo: `activo`
   (escucha TODO sin decir "Jarvis" y **sigue escuchando tras responder**) ↔ `reposo` (el
   micro sigue vivo pero solo reacciona a "Jarvis"). El orbe alterna entre esos dos y ya no
   vuelve a `off`; el reposo NECESITA el micro abierto para oír la palabra clave.
   El orbe pinta `activo`→radar y `reposo`→esfera tenue.
4. **BUG: Jarvis abría el panel y se quedaba mudo.** `chat.py` cortaba el bucle
   (`if not lecturas: break`) cuando la única salida era una acción de UI, y el modelo suele
   emitir `abrir_panel` **sin texto** → `texto:""` → ni burbuja ni voz. Ahora se le devuelve
   el turno para que comente lo que abrió, con **deduplicado de acciones** (en esa vuelta
   extra a veces repetía la llamada y el panel se abría dos veces). Cuesta una llamada más
   al modelo en esos casos.
5. **BUG: dentro de un panel no sonaba la respuesta hasta salir.** El servicio devolvía
   200 OK, así que no era generación: se creaba un `new Audio()` **por frase** y Chrome
   bloquea elementos nuevos sin gesto reciente del usuario; al pulsar para salir, ese clic
   lo desbloqueaba y soltaba lo pendiente. Ahora hay **un único elemento de audio**,
   estrenado con un WAV mudo dentro del clic que enciende el orbe.
6. **Troceo por frases** en `voz.ts` (`partir`): se genera y reproduce frase a frase, con
   la siguiente generándose mientras suena la actual. Nació para esquivar el precipicio de
   Qwen; con ElevenLabs sigue siendo útil (baja el tiempo hasta la primera palabra).

### Sesión 2026-08-15, 2ª parte (latencia, escuchador local y datos)

7. **Streaming de la respuesta (SSE).** Nuevo `POST /chat/stream`: el backend suelta el
   texto según Sonnet lo escribe y el navegador manda cada frase COMPLETA al TTS, así
   Jarvis empieza a hablar sin esperar a que termine de redactar. `proveedor.responder_stream`
   + `chat.responder(al_texto=…)`; el turno corre en un hilo y se comunica por cola porque
   el SDK es síncrono. La caché de prompt ya funcionaba (4007 tokens leídos de caché): lo
   que marca la latencia es **cuánto escribe**, no el prompt.
8. **Routing de consultas** (`chat.enrutar`, Haiku). Va PRIMERO y solo, antes de tocar a
   Sonnet, por dos motivos medidos: un "hola" no necesita a Sonnet ni el parte de estado
   (lo despacha Haiku), y lanzado EN PARALELO con Sonnet la llamada pasaba de 0,7 s a
   2,9 s (se pisan en el mismo proceso). Devuelve o la respuesta corta ya escrita
   (`responder_rapido`, que guarda el intercambio en el hilo) o qué pool de muletillas toca.
9. **Muletillas** ("déjame que mire eso…") para tapar el silencio mientras se cocina la
   respuesta. Idea de Hugo. Van **pregrabadas y generadas con v3** (~20 por pool, en
   `E:/jarvis_tts/muletillas`, nombradas por hash del texto → cambiar una frase la
   regenera sola). Se probó a escribirlas a medida con Haiku: quedaban más pegadas al
   contexto pero había que sintetizarlas en Flash para llegar a tiempo y **salían planas,
   desentonando con la ironía del resto**. Pools: `consulta` / `neutra` / `segunda` (cortas,
   de continuación). Si al acabar la primera aún no hay respuesta, se encadena una de
   `segunda` tras **2,5 s de pausa** (pegadas sonaban a atropello).
10. **Escuchador local** — `dashboard/escucha/escucha.py`, venv `E:/jarvis_tts/venv`.
    Saca el micro del navegador porque **Chrome suspende la Web Speech API al minimizar**
    la pestaña. Micro → webrtcvad (recorta voz de silencio) → faster-whisper `small` en GPU
    (~1,2 s/frase) → wake word → `/chat/stream` → `/voz`. NO habla con ElevenLabs ni con el
    modelo por su cuenta: reusa el backend, así el personaje, la memoria y el enrutado son
    los mismos. **No usarlo a la vez que el orbe escuchando** (mandarían el comando dos veces).
11. **Sesión ÚNICA `hugo`** para navegador y micro (antes: `web-<aleatorio>` vs `voz-local`).
    Lo hablado por voz iba a otro hilo y Jarvis no lo recordaba al escribir después.
12. **`GET /hilo`** + sincronización en `chat.ts` (cada 3 s, al recuperar foco, parada si
    la pestaña está oculta o se está enviando). El escuchador habla directo con el backend,
    así que sin esto sus mensajes no aparecían nunca en pantalla. Compara el último `id`.
13. **BUG: el pipeline llevaba desde el 05/08 sin escribir.** `write_tab` imprimía un `✓`
    y la consola de Windows (cp1252) lanzaba `UnicodeEncodeError` **en la primera pestaña**,
    así que las 4 siguientes —`derived_diario` incluida— no se escribían. Fallaba en
    silencio salvo por un traceback al final. Arreglado con `sys.stdout.reconfigure`.
    **Era la causa de que "hubiera que ejecutarlo dos veces".**
14. **Reintentos de Intervals reescritos.** Su sincronización con el proveedor (Zepp) es
    PEREZOSA: la petición dispara el refresco pero devuelve lo viejo, y no hay endpoint
    público para forzarla (foro: `t/hrv-not-available-from-the-api-without-ui-refresh/128220`).
    Antes: 3 intentos × 8 s = 24 s, nunca llegaba. Ahora: primera espera de **60 s** y
    creciente hasta un tope de 5 min, imprimiendo en cada intento hasta dónde llega el HRV
    y el `updated` de la API — que es lo único que distingue "el reloj no ha subido" de
    "nos han dado caché".
15. **BUG: el peso del parte iba desfasado.** El respaldo a la tabla `peso` solo saltaba si
    `derived_diario` no tenía NADA, no si estaba viejo. Ahora se coge la fuente **más
    reciente** de las dos.
16. **UI del chat ampliado**: el orbe preside FUERA del recuadro azul (`Expanded` acepta
    `sinCaja`), ocupando la vista al entrar; al bajar cede hasta ~1/3 y el hilo sube. Las
    dos zonas se REPARTEN el alto (nada de `sticky`, que superponía). El orbe solo pinta
    "hablando" cuando de verdad sale audio (`voz.sonando`), no al abrir el turno.
    Recargar ya no te mete en el chat: `#chat` es la excepción del deep-link.

### Sesión anterior (paneles y parser)
1. **Carga**: reescrito a sRPE (antes tonelaje). `DetalleFatiga` en 3 tabs con línea de
   referencia del RPE de sesión. Quitados ejemplos concretos ("170×1", label "secundario").
   Aclarado que el nº sRPE del panel = suma de sRPE de los últimos 7 días.
2. **Fuerza**: reescritura completa de `StrengthTrend.tsx`. PESO como métrica principal
   (e1RM secundaria). Hover resalta solo el ejercicio mirado (nombre enfatizado, resto a
   opacidad 0.15). Tooltip con series×reps×@. Accesorios agrupados por grupo muscular con
   drill-down (chip o **clic en la línea**). Variantes tratadas como básicos.
3. **HRV**: color por zona, racha dinámica, tooltip con día de semana + "tu rango normal";
   quitada la aclaración "un día suelto no dice mucho"; explicados `lower`/`band`.
4. **Sueño**: objetivo 7.5h con línea gruesa (sobre las barras) + caja de valor; métrica
   pasó de eficiencia % a **minutos en dormirse** (medio y peor).
5. **Readiness**: cajas umbral 40/65, bandas de color por `ReferenceArea`, X-axis con paso
   de día constante, gradiente de stroke por banda.
6. **Parser (`entreno_pipeline.py`)** hecho fail-proof (ver §10) y pipeline re-ejecutado
   (378→405 sets; 0 RPE fuera de 0-10).
7. **`status_pipeline.py`**: reintentos de Intervals; `informe_frescura`; columnas de sueño
   (tiempo_en_cama_h, eficiencia_sueno, latencia_min).

## 7. Configuración
- **Puertos**: backend `8099`, frontend `5173` (Vite), **servicio de voz `8123`**.
- **`.env` (raíz)** — claves: `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`, `GOOGLE_SA_JSON`,
  `SHEET_ID`, `KEEP_TXT`, `DRIVE_EXCEL_ID`. Opcionales del pipeline:
  `INTERVALS_REINTENTOS` (def. 3), `INTERVALS_ESPERA_S` (def. 8).
  Chat: `JARVIS_PROVEEDOR`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODELO`, `OLLAMA_MODELO`.
  **Voz**: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, y opcionales `ELEVENLABS_MODELO`
  (def. `eleven_v3`; `eleven_flash_v2_5` = mitad de precio pero plano),
  `ELEVENLABS_STABILITY` (def. 0.0 = *Creative*), `ELEVENLABS_SPEED` (solo v2/Flash).
- **Python**: `venv/` en la raíz. `requirements.txt`: pandas>=2.0, openpyxl>=3.1,
  requests>=2.31, gspread>=6.0, google-auth>=2.30, python-dotenv>=1.0.
- **Frontend deps**: react 18.3, recharts 2.12.7, vite 5, tailwind 3.4, typescript 5.5.
  Scripts: `dev` (vite), `build` (`tsc -b && vite build`), `preview`.
- **Comandos habituales**:
  - Todo de un tirón: `./run.sh` (o `./run.sh --since 2026-06-01`, `./run.sh --no-pipeline`).
  - Solo build/check frontend: en `dashboard/frontend/`: `npm run build` (corre tsc + vite).
  - Pipeline entreno suelto: `python entreno_pipeline.py keep.txt` (escribe `entreno_join.csv`).
- **Docker**: no hay.

## 8. Problemas conocidos / limitaciones
- **Alturas de panel en px fijos (NO tocar a %)**: `ResponsiveContainer height="100%"`
  dentro de `flex-1` sin altura definida provoca un bucle de ResizeObserver → los paneles
  crecen sin fin en el eje Y. Los paneles compactos usan `style={{height: 190}}` etc. a propósito.
- **RPE de sesión histórico incompleto**: las fechas anteriores al forms PM no tienen RPE de
  sesión (los sRPE de esas fechas salen vacíos). Es esperado; fiable de aquí en adelante.
- **`latencia_min`** aún no existe en el formulario AM; la columna se arrastra por si algún día
  aparece. Mientras, la latencia se estima como (tiempo en cama − dormido).
- **Datos corruptos de RPE**: había un caso (rpe=39.75) por un token mal separado; corregido en
  el parser. Vigilar tokens raros nuevos en `keep.txt`.
- **El briefing y el panel de Carga dan cifras de sRPE distintas, y las dos son correctas.**
  La fórmula es la misma columna; lo que cambia es la fecha de referencia: el briefing ancla
  la ventana de 7 días a **hoy** (la carga aguda decae con el descanso, que es lo correcto) y
  el panel a la **última sesión**. Tras unos días de descanso difieren mucho. **No igualarlos**
  — se decidió el 2026-08-18. Lo que engañaba de verdad ya tiene aviso: ver el punto siguiente.
- **Sin formulario PM no hay carga.** El sRPE necesita `rpd_sesion`, que sale del forms PM, y
  Hugo tarda días en rellenarlo. Mientras falta, una sesión reciente y dura **no entra en la
  ventana** y el parte diría "carga baja" el día después de ella. `briefing.py` avisa
  explícitamente de los entrenos de los últimos 7 días sin RPE de sesión para que Jarvis no
  concluya lo contrario de lo que pasa.
- **12 filas de PLANI 1 sin cruzar con el plan** (`SEM2 - DIA4(3)`): Hugo escribió día 4
  anotando entre paréntesis que era el 3, y el parser no entiende esa notación. Decidido
  dejarlo como histórico (2026-08-18).

## 9. Tareas pendientes (priorizadas)
_Fase 1 completa: los 7 paneles revisados y sin pendientes conocidos._

### Fase 2 EN CURSO — plan aprobado en `docs/fase2_plan.md` (leerlo antes de seguir)

Jarvis no es un buscador de datos: es un **asistente conversacional con memoria** que
además **maneja el dashboard**. Bromea y usa sarcasmo por iniciativa propia, recuerda la
vida de Hugo entre sesiones, abre paneles cuando se lo pides y hace un tour comentado.
La voz va **después**, como capa aparte.

**Hecho y verificado (2026-07-20):**
- `dashboard/backend/memoria.py` — SQLite (`jarvis.db`, ignorado por git). Dos memorias:
  hilo de conversación y hechos de su vida. Verificado que persiste entre procesos.
- `dashboard/backend/briefing.py` — parte de estado desde la hoja. **Cada métrica lleva su
  antigüedad** y los umbrales replican `readinessBand` del frontend. Obsolescencia por
  métrica (peso 10 días, el resto 2): Hugo se pesa semanalmente.
- `dashboard/backend/personalidad.py` — el personaje. ~834 tokens con memoria y briefing.
- `dashboard/backend/proveedor.py` — Ollama, Anthropic y **`ProveedorFalso`** tras una
  interfaz común; se cambia con `JARVIS_PROVEEDOR` (`ollama|anthropic|falso`) o con el
  campo `proveedor` del propio POST. Normalización probada; Ollama **sin probar de verdad**.
- `dashboard/backend/chat.py` + `POST /chat` → `{texto, acciones}`. Herramientas de lectura
  (`dia`, `ejercicio`, `recordar`) ejecutadas en el backend, y de UI (`abrir_panel`,
  `cerrar_panel`, `resaltar`) devueltas al navegador. Verificado por HTTP con el proveedor
  falso: acciones, lectura sobre datos reales y memoria escrita desde la herramienta.
  Los resultados de herramienta se inyectan como **texto plano** en el hilo, no como
  bloques `tool_result`: Ollama y Anthropic los formatean distinto y esa era la parte
  más frágil del proveedor.

**Frontend del chat — hecho y verificado (2026-07-20):**
- `lib/chat.ts` — cliente `POST /chat` + hook `useChat(onAcciones?)`. Historial en
  localStorage (`jarvis.chat.historial`) e id de sesión estable (`jarvis.chat.sesion`):
  el backend agrupa el hilo por sesión, así que si cambiara en cada arranque se perdería
  la continuidad. El proveedor se puede forzar con `VITE_JARVIS_PROVEEDOR=falso` para
  desarrollar sin modelo; sin definir, manda el backend. `API_BASE` ahora se exporta desde
  `lib/api.ts`. Las `acciones` que devuelve el backend se pasan hacia arriba por un *seam*
  (`onAcciones`) **que aún no ejecuta nada**: eso es `lib/acciones.ts` (paso siguiente).
- `components/ChatPanel.tsx` — `ChatPanel` (compacto, tarjeta a lo ancho bajo las dos filas
  del grid, altura fija 263 px como el resto, §8) y `ChatExpanded` (overlay). Burbujas
  usuario/Jarvis, autoscroll, "Jarvis está pensando…", entrada `<textarea>` (Enter envía,
  Mayús+Enter salto) con `data-no-expand` (trampa 1). `ChatExpanded` usa **`h-[72vh]`**,
  no `h-full`: dentro del `flex-1` de `Expanded` un `height:100%` no resuelve y la entrada
  se pegaba arriba (trampa 2). El estado del chat vive en `App` (`useChat`), compartido por
  compacto y ampliado.
- `App.tsx` — 4 puntos de contacto enganchados (`Widget` "chat", `TITULOS`, render, caso en
  `<Expanded>`). Verificado por CDP con `"proveedor":"falso"`: mensaje enviado, respuesta
  pintada, deep-link `/#chat` abre el ampliado. Build (`npm run build`) limpio.

**Modelo local y latencia — investigado y resuelto (2026-07-20):**
Ollama ya probado de verdad en el portátil. Hallazgos (medidos con el desglose de
`/api/chat` y `nvidia-smi`):
- **La RTX 3060 Laptop tiene 6 GB, pero Windows ya usa ~2 GB** → solo ~4 GB libres.
  **qwen2.5:7b (5.1 GB) NO cabe**: Ollama deja el ~18% en CPU y la latencia baila entre
  5 y 25s, inestable. **qwen2.5:3b (2.2 GB) cabe al 100% en GPU → ~2.7-3s por mensaje,
  estable** (medido por HTTP: hola 2.7s, peso 2.8s, sueño 3.0s con dato correcto). Por eso
  el default pasó a **`OLLAMA_MODELO=qwen2.5:3b`** (.env y .env.example). El 3b es más tonto
  (a veces yerra números), pero cumple la latencia.
- **Dos fuentes de latencia arregladas, valen para cualquier proveedor:** (1) recarga del
  modelo en frío (~40s tras 5 min idle) → `keep_alive:"30m"` + `proveedor.precalentar()` en
  el `startup` de `main.py`; (2) **Google Sheets en frío tarda ~6s** y el chat lee la hoja en
  cada mensaje (briefing) → hilo `_mantener_datos_calientes()` refresca la caché cada 240s
  (por debajo del TTL de 300s), así nunca se enfría.
- **Bug arreglado — llamadas coladas como texto:** qwen a veces escribe `abrir_panel({...})`
  DENTRO del texto en vez de por el canal de tools; se veía crudo y, al guardarse en el hilo,
  se reforzaba. `proveedor._rescatar_llamadas_texto()` las saca, las ejecuta y las quita del
  texto. Se borró de `jarvis.db` un hecho envenenado ("El arte de la guerra", inventado) y 4
  mensajes con sintaxis colada. Prompt reforzado: nunca inventar hechos de su vida; 1-3 frases.
- **Tope de generación:** `num_predict:128` (a ~14 tok/s del 3b, evita respuestas que se
  disparen). `anthropic>=0.40` instalado y en requirements (import perezoso).

**Proveedor decidido — comparación hecha (2026-07-25):**
Mismo guion contra 3B local, Sonnet 5 y Opus 4.8 con `dashboard/backend/comparar.py` (reproduce
un guion fijo contra cada modelo con BD temporal aislada y reporta tiempo, tokens y coste).
- **El 3B NO guarda hechos** (no llama a `recordar`): la memoria de largo plazo —el hito de la
  fase— no funciona con él. Sonnet y Opus sí. Verificado contando filas en `hechos` tras "estoy
  leyendo Dune": 3B=0, Sonnet=1. Además el 3B tira al informe y al dato inventado.
- Tono: Opus > Sonnet >> 3B, pero Sonnet muy cerca de Opus y en la prueba hasta más correcto
  (Opus se inventó continuidad). Tiempo: Sonnet ~3.6s, Opus ~3.4s, 3B ~7s (con arranque frío).
  Coste aprox: Sonnet ~$0.007/turno (~$6/mes a 30 msg/día), Opus ~$0.021/turno (~$19/mes), 3B 0.
- **Decisión: Anthropic `claude-sonnet-5` por defecto** (`JARVIS_PROVEEDOR=anthropic` en `.env`).
  Ventaja extra: Anthropic corre en las DOS máquinas (el 3B solo en el portátil). Coste real de
  ir a la nube: las conversaciones de salud salen de casa (riesgo #5 asumido). El 3B sigue
  disponible por `.env` si algún día manda la privacidad.

**Hecho también (2026-07-25):**
- **Fecha en el prompt** (`personalidad.py`): se inyecta "hoy es <día en lenguaje natural>" arriba
  del sistema. El 3B entraba en bucle preguntando qué día era (no anclaba la fecha ISO enterrada en
  el briefing) y confundía el aviso de "reloj sin sincronizar" (que es solo para datos de salud
  viejos) con no saber la fecha. Verificado en vivo con los 3 modelos.
- **Uso de tokens por llamada** (`proveedor.py`, `chat.py`) para medir coste; `obtener()` admite
  `"proveedor:modelo"` para forzar un modelo suelto (lo usan el arnés y el selector).
- **Selector de modelo en la UI** (`lib/chat.ts`, `ChatPanel.tsx`): tres niveles ascendentes con
  barras y color — Estándar (Sonnet, verde, default) < Turbo (Opus, naranja) < Máxima potencia
  (Fable, rojo). Se recuerda en localStorage y se manda por mensaje. El 3B ya no aparece.

**CAPA DE VOZ — arrancada (2026-07-29), SIN COMMITEAR. GIRO a voz-first.**
Cambio de visión con Hugo: **nada de botón de micro ni de caja de chat como interfaz.**
Jarvis **siempre escuchando** su nombre; lo llamas ("Jarvis…") y "sale": te habla y te
mueve los paneles. Una **"presencia"** (orbe) sustituye al chat; **el chat de texto se
queda de respaldo** (probar sin micro / plan B) hasta que la voz esté pulida.
- `components/Presencia.tsx` (nuevo) — orbe en **Canvas 2D** (sin librerías) con 4 formas
  por estado que **morfean** suave: esfera (dormido/off) · radar (escuchando) · giroscopio
  (pensando) · barras de ecualizador (hablando). Respeta `prefers-reduced-motion`.
  **La potencia del modelo (0 Estándar / 1 Turbo / 2 Máxima, prop `potencia` desde
  `ChatPanel.potenciaDe(chat.proveedor)`) NO cambia el color** —eso lo marca el estado, por
  consistencia— sino que se expresa como energía (más rápido/glow/partículas), un
  aro-medidor tenue en el color del nivel, y un glow de fondo que brilla más con la potencia.
  Barras de "hablando" con amplitud comprimida (no chillan en Máxima). Look y ajustes
  aprobados por Hugo en maqueta.
- `lib/voz.ts` (nuevo) — motor de voz. **v1 con Web Speech** (gratis, Chrome, sin claves):
  wake-word con **abanico de variantes** (`/\b(?:ll|j|y|h)?ar[vb]i[sz]?\b/i` →
  jarvis/yarvis/llarvis/jarvi/jarbis…, porque en `es-ES` la J suena "y"/"ll"), STT del
  comando, TTS `speechSynthesis`. Máquina de estados off→dormido→escuchando→hablando con
  **anti-eco** (silencia el mic mientras habla). Expone `useVoz({onComando})`.
- `lib/acciones.ts` (nuevo, MÍNIMO) — reproductor: `abrir_panel`/`cerrar_panel` vía el hash.
  `resaltar`/gráficos/tours aún no (no-op). Sirve también al chat escrito. Enganchado al
  *seam* `onAcciones` en `App.tsx` (antes se descartaban).
- `lib/chat.ts` (editado) — nuevo callback `onRespuesta(texto)` para que la voz lea solo las
  respuestas nuevas. `ChatPanel.tsx`/`App.tsx`/`index.css` editados: el orbe preside el panel
  y es el control de voz (clic = on/off; si habla, corta).
- **Verificado aquí (sobremesa):** `npm run build` limpio; captura del dashboard y del panel
  con el orbe OK; `/chat` con `"proveedor":"falso"` devuelve `abrir_panel(sueno)`. El micro
  NO se pudo probar (headless sin micro): lo prueba Hugo en el portátil.

**Siguiente, por orden (en el PORTÁTIL — necesita micro, GPU y la key):**
1. **Probar la voz de verdad** en Chrome del portátil con `VITE_JARVIS_PROVEEDOR=falso`:
   activar el orbe, dar permiso de micro, decir "Jarvis, muéstrame el sueño" → estados del
   orbe + abre panel + TTS. Validar que el abanico engancha "yarvis"/"llarvis".
2. **Wake-word Porcupine** (decidido): detección on-device de "Jarvis" (Web Speech continuo es
   flaky y manda audio a Google sin parar). Necesita `VITE_PICOVOICE_KEY` (gratis). OJO: el
   keyword de fábrica es inglés; quizá entrenar uno con la pronunciación española de Hugo.
   Detector encapsulado en `voz.ts` → swap acotado.
3. **Cerebro Claude real:** poner `ANTHROPIC_API_KEY` en el `.env` del portátil (no viaja por
   git; Hugo la trae a mano) y probar la conversación de verdad (Sonnet 5 por defecto).
4. **✅ VOZ RESUELTA (2026-08-15): ElevenLabs v3 en la nube + XTTS local de respaldo.**
   Tras medir tres motores, **Qwen3-TTS quedó descartado** y la voz funciona a gusto de Hugo.
   Lo de abajo (Qwen) se conserva solo como historial de por qué se descartó.
   - **Cadena de voz:** `voz.ts` → `:8123` → **ElevenLabs** → *si falla* **XTTS local** →
     *si falla* voz del navegador. Servicio: **`dashboard/tts/servidor_voz.py`** (es el bueno;
     `servidor.py` (Qwen) y `servidor_xtts.py` quedan como piezas sueltas).
     Arranque: `HF_HOME=E:/jarvis_tts/hf_cache COQUI_TOS_AGREED=1
     E:/jarvis_tts/venv_xtts/Scripts/python.exe -m uvicorn servidor_voz:app --port 8123`.
   - **Por qué la nube:** en la 3060 de 6 GB, la misma respuesta larga tardaba **113 s**
     (Qwen 1.7B) / **30 s** (Qwen 0.6B) / **6,3 s** (XTTS) / **1,4 s** (ElevenLabs). Hugo pedía
     ≤4-5 s y **cero huecos** entre frases; solo la nube lo cumple. El precipicio de Qwen era
     desbordar la VRAM con textos largos (caché de atención → derrame a RAM, 12x).
   - **Modelo `eleven_v3`, NO Flash v2.5.** Flash es más rápido y barato pero **plano**: la
     ironía de Jarvis se perdía. v3 es expresivo y entiende **etiquetas inline**.
   - **Etiquetas de intención (la clave del tono):** Jarvis escribe `[sarcastic]`,
     `[mischievously]`, `[laughs]`, `[sighs]`, `[curious]`, `[excited]` en su respuesta
     (instruido en `personalidad.py`, máx. 1 por respuesta y nunca al bajar el tono). Se
     **mandan al TTS** pero **se filtran al pintar** el chat (`sinEtiquetas` en `ChatPanel.tsx`)
     y antes de XTTS/Flash (`_sin_etiquetas` en `servidor_voz.py`), que las leerían en alto.
     Hugo: *"gana muchísimo con sarcastic, es una locura, justo lo que quiero"*.
   - **Voz:** creada con **Voice Design** (describir la voz en texto), NO clonada. Se evitó
     clonar el doblaje de Iron Man: la referencia eran 28 s con ruido (piden 1-2 min limpios)
     y el checkbox de consentimiento de ElevenLabs no aplica a la voz de un actor real.
     `ELEVENLABS_VOICE_ID` en el `.env`.
   - **Coste:** PAYG (sin suscripción), saldo prepago de $5 que caduca a 12 meses.
     v3 = $0,10/1k caracteres ≈ **2 céntimos por respuesta** ≈ $6-12/mes a su ritmo. El
     prepago ES el tope de gasto: sin auto-recarga, el riesgo máximo es lo cargado.
     Volver a Flash (mitad de precio, sin expresividad) = `ELEVENLABS_MODELO` en el `.env`.
   - **Ajustes:** `stability=0.0` (preset *Creative*, el que responde a la intención;
     *Robust* suena estable pero monótono). `speed` solo lo aceptan v2/Flash — v3 da 422.
   - **XTTS de respaldo:** se carga **perezosamente**, solo la primera vez que la nube falla,
     para no ocupar 2,2 GB de VRAM en balde. venv propio `E:/jarvis_tts/venv_xtts`
     (coqui-tts + **transformers 4.57.x**: con 5.x rompe y con <4.57 también).
     Modelo en `E:/jarvis_tts/models/xtts-v2`.
   - **QUÉ FALTA:** el timbre "quizás grave de más" (Hugo lo aparcó para más adelante).

   <details><summary>Historial: por qué se descartó Qwen3-TTS (2026-08-09)</summary>

   **Voz "Jarvis" de verdad — TTS local con Qwen3-TTS clonado.**
   Se descartó XTTS: se usa **Qwen3-TTS** (open, Apache-2.0). Todo lo pesado vive en
   `E:\jarvis_tts\` (venv, modelos, caché) porque **C: se quedó sin espacio**; el código va
   en `dashboard/tts/` (repo). **Solo portátil** (GPU): el otro equipo cae a la voz del navegador.
   - **Modelos** (a E:, ~4 GB c/u): `Qwen3-TTS-12Hz-1.7B-CustomVoice` (9 voces de catálogo,
     `generate_custom_voice`) y `Qwen3-TTS-12Hz-1.7B-Base` (el que CLONA, `generate_voice_clone`).
     El Base se bajó con `snapshot_download(local_dir=...)` a `E:\jarvis_tts\models\qwen3-base`
     para esquivar el **WinError 1314** (symlinks de HF fallan en Windows sin modo desarrollador).
   - **Voz elegida: Jarvis del doblaje español de Iron Man, CLONADO.** Las 9 de catálogo no
     daban el acento (Hugo las descartó). Pipeline montado en `dashboard/tts/`:
     `prueba.py` (audición catálogo), `clonar.py` (clonación). La referencia se sacó de un
     vídeo de YouTube (yt-dlp), se **aisló la voz con Demucs** (quita música/fondo) y se
     recortó a ~28 s limpios (`E:\jarvis_tts\ref\jarvis_ref.wav`).
   - **Ajustes que funcionaron:** modo **con transcripción** (`x_vector_only_mode=False`,
     `ref_text` transcrito con faster-whisper) para que NO suene robótico; **gravedad −1
     semitono con rubberband de ffmpeg** (`formant=preserved`) — librosa metía un "enlatado"
     metálico, rubberband no. Aprobado por Hugo: timbre y gravedad OK.
   - **Latencia:** ~1.6–1.9× tiempo real (varía; el primer gen tras cargar se dispara a ~4×).
     Para uso en vivo hay que atacarla: respuestas cortas, **streaming**, o el Base de **0.6B**.
   - **INTEGRACIÓN HECHA (2026-08-09):** `dashboard/tts/servidor.py` (FastAPI, puerto **8123**)
     carga el modelo + prompt al arrancar y expone `POST /voz {texto}` → WAV (con la gravedad
     -1 rubberband ya aplicada). `voz.ts` `decir()` reescrito: pide el audio a `TTS_URL`
     (`VITE_TTS_URL`, default `http://localhost:8123`), lo reproduce con un `<audio>`, y **cae a
     `speechSynthesis`** si el servicio no responde (otro equipo / apagado). `parar()` corta también
     ese audio (barge-in). Bucle ya cerrado en `App.tsx` (chat.onRespuesta → voz.decir).
     Arrancar el servicio: `HF_HOME=E:/jarvis_tts/hf_cache
     E:/jarvis_tts/venv/Scripts/python.exe -m uvicorn servidor:app --port 8123` (desde
     `dashboard/tts/`, sandbox off).
   - **Probado en vivo por Hugo (2026-08-09):** la voz clonada suena por el chat ("bien,
     mejorable"). **BUG arreglado:** ffmpeg escribía el WAV a tubería (`pipe:1`) y dejaba el
     tamaño RIFF en `0xFFFFFFFF`; el navegador tardaba **>1 min** en reproducir (buffering).
     Ahora ffmpeg escribe a fichero temporal (cabecera correcta) → reproduce al instante.
   - **QUÉ FALTA / MEJORAR (por prioridad):**
     1. **Latencia de generación** (lo gordo): ~5 s frase corta, ~10 s media (en caliente; el
        1er gen tras cargar ~17 s). Para uso en vivo hay que **streaming** (Qwen3-TTS lo
        soporta; empezar a sonar con el primer trozo) o el Base **0.6B**. Sin esto, Jarvis
        tarda ~5-10 s en empezar a hablar tras responder.
     2. **Calidad de voz** "mejorable" (Hugo) — afinar (¿más referencia?, ¿otros ajustes?).
     3. Re-verificar en el navegador que con el fix del WAV ya suena rápido (quedó a medias al
        irse Hugo; el fix está aplicado pero el servicio corría con la versión vieja).
   - **Seseo (latino) irresoluble en Qwen:** no tiene parámetro de dialecto y el truco
     ortográfico no funciona; solo fine-tune/LoRA. Fue una de las razones de irse a la nube
     (ElevenLabs da castellano nativo).

   </details>

**Pendientes tras la sesión del 2026-08-15 (por prioridad):**
- **Rodar el escuchador local**: falsos positivos del wake word (Whisper puede oír "Jarvis"
  en la tele; la regex viene de `voz.ts` y quizá sea generosa de más aquí), si el VAD corta
  a mitad de frase (subir `SILENCIO_FIN_MS`) o se dispara con ruido (subir `VAD_AGRESIVIDAD`
  a 3), y si se oye a sí mismo por altavoces (subir `GRACIA_S`).
- **El orbe no refleja el micro externo**: sigue en reposo aunque el escuchador trabaje. El
  estado vive en el navegador y el escuchador va por libre; haría falta publicarlo.
- **Abrir un panel tarda ~12 s**: gasta dos vueltas de modelo pese a la instrucción de
  `personalidad.py` de hablar en el mismo turno que la acción.
- **~2 s de sobrecoste sin explicar** en `enrutar` dentro del servidor (aislado 0,7 s,
  servido 2,8 s). No es el prompt ni Sonnet compitiendo (pasa también en el camino trivial).
- **`keep.txt` lleva 30 días sin entrenos** (último 16/07) aunque las notas de dolor hablan
  de sentadillas en agosto. Hasta que Hugo vuelque sus notas, Jarvis cree que no entrena.
- **El timbre "quizás grave de más"** (Hugo, al estrenar la voz de ElevenLabs). Sin revisar.
- **Historial huérfano**: al pasar a la sesión `hugo`, el hilo viejo del navegador quedó en
  `jarvis.db` bajo su `web-<aleatorio>`. No se ha borrado; migrarlo es una consulta SQL.

**Otros pendientes (no de voz):**
- **Memoria en Markdown** (pedido de Hugo): mover los `hechos` de SQLite a un `.md` editable a
  mano. El hilo se queda en SQLite; los hechos pasan a Markdown. Acotado a `memoria.py`.
- Resaltado (`data-jarvis="..."` + glow) y `GraficoAdHoc` (el reproductor completo/tour).
- Iterar el personaje (emojis, brevedad) ahora que el proveedor por defecto es Sonnet.

**Probar el chat sin modelo** (útil en cualquier máquina):
```bash
curl -s -X POST http://localhost:8099/chat -H 'Content-Type: application/json' \
  -d '{"sesion":"t","mensaje":"enseñame el sueño","proveedor":"falso"}'
```

Ideas del backlog post-v1 en la memoria [[backlog-post-v1]].

Resueltas en esta tanda:
- ✅ **Hueco bajo Fuerza/Peso**: la fila inferior se estira a la tarjeta más alta; se subieron las
  alturas fijas del gráfico compacto (Fuerza 214→229, Peso 158→203) para que el contenido de los
  tres (Fuerza/Peso/Correlaciones) mida ~263 px y la fila quede pareja, sin `ResponsiveContainer`
  a 100% en flex-1 (evita el bucle del §8). Medido por CDP: `getBoundingClientRect`.
- ✅ **Estrellas ★ de PR en Fuerza** (repuestas, ver §5).
5. **Backlog post-v1 (SOLO tras terminar la v1 completa con voz / Fase 2)**:
   - Añadir `avgSleepingHR` (FC durmiendo, de Intervals) al dashboard.
   - Añadir al formulario AM: nº de despertares y latencia (minutos en dormirse) explícitos.

### Deuda técnica abierta (revisada 2026-08-18)
- **Correlaciones y ACWR siguen sobre el sRPE por DURACIÓN** (`derived_diario.sRPE` = rpd ×
  duracion_min), que depende de Intervals y es frágil (la duración falta o llega a 0 desde
  Zepp; de ahí `DURACION_DEFECTO_MIN`). Lo que bloqueaba el cambio **ya está hecho**: el sRPE
  por series existe como columna (`sRPE_series`, `sRPE_series_7d`). Solo falta apuntar el panel
  de Correlaciones y el ACWR a la columna buena.
- **Detección de anomalías de sesión**: ver §11.

## 10. Convenciones y patrones
- **Idioma**: todo en español — nombres de variables, comentarios, UI. Comentarios explican
  el *porqué*, no el *qué*, con tono cercano.
- **Parser de `keep.txt` (fail-proof)**, reglas clave:
  - Separador de series = guion con espacio en ≥1 lado: `re.split(r'\s+-\s*|\s*-\s+', line)`.
    Un guion entre dígitos SIN espacios (`8-10`, `@7-8`, `RIR8-10`) NO separa: es un rango.
  - RPE: `@([\d.]+)(?:-([\d.]+))?` (rango con guion sin espacio) + clamp `if not (0<=rpe<=10): rpe=None`. Igual para RIR.
  - Rangos de reps unilaterales (`1x50x8-10RIR3` → 9 reps): se promedian con
    `re.sub(r'(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)', ...)` DESPUÉS de quitar @/RIR.
- **Bandas/percentiles y paleta de colores** siempre sobre histórico completo; el rango solo
  recorta lo dibujado.
- **Recharts**: bandas de valor con `ReferenceArea`; cajas de valor con `ReferenceLine` + SVG
  label custom; highlight por hover con `activeDot.onMouseEnter` (opacidad 0.15 a los no activos);
  drill-down por clic enganchado al hover activo, no al `onClick` de línea.
- **Pruebas de hover/clic con CDP** (Chrome DevTools Protocol vía WebSocket nativo de Node 24):
  los selectores DEBEN acotarse al overlay `.fixed` (`.fixed .recharts-line circle`), porque el
  panel compacto de fondo dibuja los mismos puntos del mismo color y ensucia la prueba.
  Capturas con `--force-prefers-reduced-motion`.
- **e1RM** solo en su vista aparte, nunca como métrica principal de progresión.

## 11. Contexto caro de redescubrir
- El bug de "paneles que se estiran infinito" = ResizeObserver con altura %. Mantener px fijos.
- El zoom de apertura no disparaba (solo el de cierre) por StrictMode duplicando efectos de
  montaje → resuelto con Web Animations API + cleanup que cancela.
- El sRPE del panel = suma de últimos 7 días (se decidió NO dividir entre 7; se comparó y se
  dejó suma).
- Intervals no iba "desactualizado" por bug de `run.sh`: la hoja estaba vieja; los datos existían.
- El clic-en-línea para drill-down se verificó funcionando SOLO tras acotar el selector CDP al
  overlay `.fixed` (antes cogía los círculos del panel compacto de fondo).
- **El dolor de una sesión está DUPLICADO a propósito, y no se pasan las dos fuentes a la vez.**
  Hugo escribe `Dolores sesión: ...` en el keep al acabar de entrenar y **más tarde copia ese
  mismo texto** al campo "dolor de entreno" del formulario PM. De ahí salen dos columnas con el
  mismo párrafo: `dolor_sesion_keep` (keep, vía `parse_keep`) y `dolor_sesion_nota` (forms PM).
  **La buena es la del formulario**; la del keep solo cubre la ventana entre entrenar y
  rellenarlo. Si se le pasan las dos a Jarvis, ve el dolor duplicado y lo lee como dos
  episodios distintos. `briefing.py` incluye el `_keep` **solo si ese día falta el del form**;
  cualquier consumidor nuevo (panel, herramienta de chat, detección de anomalías) debe hacer lo
  mismo.
- **La notación del keep no es uniforme y el parser depende del ejercicio.** Dos números pueden
  ser peso × repes (lo normal, y en dominadas lastradas `5x3` son 5 kg) o series × repes (en los
  que nunca llevan carga). Al añadir un ejercicio nuevo de ese tipo, meterlo en
  `entreno_pipeline.SIN_CARGA` o sus series se guardarán como kilos. Ojo: hay abdominales que
  SÍ llevan peso (el crunch en polea son 55 kg reales), así que la regla no puede ir por
  categoría.
- **La detección de anomalías de sesión sigue SIN hacer.** Los flags (`fallo`,
  `sin_intensidad`) ya llegan al briefing, pero nadie compara una sesión contra la línea base
  de Hugo. Era la idea original del 2026-08-18 y quedó pendiente de decidir el umbral (se
  propuso: volumen o series >40% por debajo de la mediana de 4 semanas, o cualquier flag).
- Memoria persistente del proyecto (en `~/.claude/.../memory/`): variantes distintas, estado
  Fase 1, plan de entreno en Drive ("Peaking SN" = bloque 4), sueño cama≠dormido, backlog post-v1,
  pendientes técnicos (Correlaciones y ACWR aún con el sRPE por duración).

## 12. La prueba de formularios del 2026-09-04 (tres fallos y cómo quedaron)

Los tres salieron del **mismo sitio**: un `except` que se traga el motivo y deja al que
llama creyendo que todo va bien. Merece la pena tenerlo presente antes de añadir el
siguiente, porque nos costó la sesión entera diagnosticarlo.

### 1. Una zona de dolor desconocida se guardaba como celda vacía
Hugo dictó "dolor en el pie". **`Pie` no existe en `ZONE_KEYWORDS`** (está `Tobillo`), así
que `normalizar_zonas()` devolvía `""`, `validar()` lo daba por bueno y `guardar()`
escribía el hueco en la hoja: la zona se perdía **y además borraba lo que hubiera**, sin
error y sin rastro en el log. Le venía pasando a todas las menciones al pie, que es su
dolor crónico.

Peor todavía: la herramienta le devolvía a Jarvis un `asi_queda` con la zona vacía y un
`faltan` que seguía pidiéndola, o sea **contradiciendo lo que él acababa de mandar**. Con
eso Jarvis concluyó que había reventado el sistema y le dijo a Hugo "se ha atragantado el
sistema, error raro de fondo" — cuando en realidad se había guardado todo lo demás.

**Cómo quedó:** una zona no reconocida ya no entra en los valores limpios (la celda no se
toca) y sale por `avisos` con la lista de zonas válidas. Es **aviso y no error** a
propósito: una palabra rara no puede tirar abajo la energía y el RPE dictados en la misma
frase. Regla nueva en `personalidad.py` para que Jarvis diga qué ha fallado y **proponga**
la zona equivalente ("'pie' no está, la más parecida es Tobillo, ¿te la marco?").

**Decisión de Hugo: NO se añade `Pie` al vocabulario.** Para eso está la IA. Además
añadirlo tocaría el parseo histórico del keep, y `'pie'` es subcadena de `'pierna'`: con el
matching actual (`k in low`, sin límite de palabra) etiquetaría como Pie cualquier
mención a la pierna.

### 2. Un fallo de lectura de la hoja se cacheaba como "no hay datos"
Al guardar, `invalidar()` forzaba releer **las 7 pestañas de golpe**; esa ráfaga se pasó de
la cuota de la API de Google; `sheets.fetch_all()` convertía cada fallo en lista vacía —
y la cacheaba 5 minutos. Resultado: el panel en blanco y el semáforo en rojo diciendo que
faltaban 8 días de formularios. **Parecía una pérdida de datos y no lo era**: la hoja
estuvo intacta todo el rato. Solo se arreglaba reiniciando el backend.

**Cómo quedó:** si una pestaña falla se conserva lo último que se leyó bien de ella, no se
renueva el TTL y se reintenta a los 30 s (`ESPERA_TRAS_FALLO_S`) — reintentar en cada
petición, con la cuota agotada, solo echaría más leña. Y ahora lo escribe en el log.
`invalidar(tab)` refresca **una sola** pestaña: 1 petición por guardado en vez de 7, que
era lo que nos ponía contra la cuota. Al probarlo apareció un cuarto agujero:
**`open_by_key()` estaba fuera del `try`**, así que si lo que fallaba era abrir la hoja
—el caso más típico con la cuota agotada— la petición se iba en 500 entera.

### 3. No había forma de ver nada de esto desde el servidor
Los fallos de herramienta mueren en `chat.py` convertidos en JSON para el modelo, y los de
lectura morían en `sheets.py`. Ninguno llegaba a ninguna parte.

**Cómo quedó:** `sheets.py` avisa por `logging`, y `run.sh` manda la salida del backend a
**`logs/backend.log`** además de a pantalla (rota a los 5 MB, cabecera con fecha en cada
arranque, `logs/` ignorado en git). En la VM esto no es opcional: allí no hay terminal
donde mirar.

Nota para el que siga: `run.sh` lanza el backend con **sustitución de proceso**
(`> >(tee -a "$LOG")`) y no con `| tee`. Con la tubería, `$!` sería el PID de `tee` y el
`trap cleanup` dejaría uvicorn vivo al salir.

---

## 13. La voz conversacional del 2026-09-06 (interrumpir, esperar, y cuatro sorpresas)

> **Leer también la §14 antes de tocar `voz.ts` o `vad.ts`.** Todo lo de aquí se escribió
> probando en el portátil, y en el móvil (Android) varias piezas se comportan distinto —
> incluido el momento en que el VAD abre el micro, que aquí se describe como "toda la
> sesión" y **ya no es así**. Las perillas de la tabla de abajo están actualizadas.

Lo que pidió Hugo, literal: poder **cortarle** cuando Jarvis oye mal y arranca a hablar;
que **no conteste antes de que él termine**, pero sin que se note lento; y que tocar el
orbe mientras escucha signifique **"he terminado, contéstame"**, no "apágate".

### Por qué interrumpir no funcionaba: eran CUATRO eslabones, no uno
Lo que más despistaba es que no funcionaba **ni haciendo clic**. El clic sí callaba el
audio, pero la aclaración de Hugo moría después:

1. `voz.ts` — el reconocedor descartaba todo mientras el estado era `"hablando"`
   (anti-eco deliberado). Interrumpir hablando era imposible por diseño.
2. `chat.ts` — `if (!limpio || enviando) return` **tiraba en silencio** cualquier comando
   que llegara con una petición en vuelo. Éste es el que hacía inútil el clic.
3. `chat.ts` — el `fetch` no llevaba `AbortController`: la respuesta seguía llegando.
4. `main.py` — el turno corre en un hilo daemon que ignora la desconexión: seguía hasta
   el final, **ejecutaba las escrituras en la hoja** y guardaba en `jarvis.db` la
   respuesta entera, no la que Hugo llegó a oír.

### Cómo quedó
- **Cortar por voz**: `dashboard/frontend/src/lib/vad.ts` (nuevo). Mide la energía del
  micro por frame y avisa cuando hay voz sostenida. No vale el reconocedor de Chrome:
  tarda de 300 ms a 1 s en soltar el primer parcial, y para entonces ya te ha soltado
  media parrafada encima.
- **Cortar a mano**: el clic del orbe es contextual (hablando -> cállate; escuchando con
  algo dicho -> he terminado; escuchando sin nada -> reposo) y hay botón de micro
  tachado. **Es la red de seguridad**: si el corte por voz falla, esto funciona siempre.
- **Esperar a que termine**: se acumula lo que dice y se manda tras un silencio, en vez
  de despachar con el primer `isFinal` de Chrome, que corta pronto.
- **Backend cancelable**: `POST /chat/cancelar` + un registro de turnos por sesión en
  `main.py`. La cancelación viaja como excepción `Cancelado` lanzada desde `al_texto`,
  que sale del `with` del stream de Anthropic (deja de generar) **antes** de las
  herramientas y del guardado. Verificado en vivo: corte a los 14,9 s, stream cerrado en
  100 ms, y en `jarvis.db` solo el mensaje de Hugo.
  - **No fiarlo a `GeneratorExit`**: `eventos()` es un generador síncrono que suele estar
    bloqueado en `cola.get()`, no en un `yield`. Queda como red secundaria.
  - `enrutar` y la ruta corta `responder_rapido` **no son cancelables**. Son turnos de
    una frase; asumido.

### Las perillas, y por qué están donde están
Casi todos estos números se movieron con Hugo delante. **No tocarlos a ciegas.**

| Dónde | Constante | Hoy | Historia |
|---|---|---|---|
| `voz.ts` | `FIN_TURNO_MS` | 1500 | 1100 cortaba · 1800 se hacía incómodo · 1200 iba bien en el portátil pero le cortaba en el móvil · 1500 es el punto medio, **no subirlo sin que lo pida él** |
| `voz.ts` | `FIN_TURNO_COLGADO_MS` | 2800 | Frase acabada en "…y", una duda suelta, **o una duda al final de lo acumulado** (`DUDA_FINAL`, §16) |
| `voz.ts` | `MAX_SILENCIO_MUERTO_MS` | 15000 | Red por si el reconocedor se atasca. Cuenta desde LO ÚLTIMO OÍDO, no desde el principio del turno: contado mal cortaba las frases largas a los 12 s |
| `voz.ts` | `MIN_CARACTERES` | 3 | Un golpe o una respiración generan un "final" de una o dos letras. **Con la excepción de `CORTA_VALIDA`** |
| `voz.ts` | `ESPERA_MULETILLA_MS` | 4500 | Lo pidió él: el orbe en "pensando" 4-5 s. De rebote, si la respuesta real llega antes, la muletilla ya no se dice. **Y es lo que da tiempo al modelo rápido de §16** |
| `.env` | `GROQ_TIMEOUT_MS` | 3000 | Plazo duro de la muletilla a medida. Pasado, se tira de las pregrabadas: una muletilla tarde es el silencio MÁS la muletilla |
| `voz.ts` | `GRACIA_MS` | 300 | Era 700; ahora el trabajo lo hace el `abort()` |
| `vad.ts` | `SOSTENIDO_MS` | 220 | 300 le daba tiempo a acabar la frase |
| `vad.ts` | `MINIMO_HABLANDO` | 0.038 | **LA perilla del caso altavoces.** Si se autocorta, SUBIRLA. En el MÓVIL puede sobrar: su voz medía 0,0365-0,0755, o sea que una de las dos medidas queda POR DEBAJO del umbral. Sin confirmar |

Para afinar con números y no de oído: `localStorage.setItem("jarvis.voz.debug","1")` y
recargar. Traza cada parcial, cada final, cuánto silencio espera, qué manda, y el nivel
del VAD contra su umbral mientras Jarvis habla.

Hay una prueba de la lógica del VAD en `scratchpad/test_vad.cjs` (no va al repo): seis
casos —silencio, golpe, respiración, Hugo hablando, eco de Jarvis, Hugo interrumpiéndole
por encima— con un micro simulado. Fue la que destapó que el eco se autocortaba. Si se
tocan los umbrales, vale la pena rehacerla: `npx esbuild src/lib/vad.ts --format=cjs
--platform=node --outfile=vad.cjs`. Ojo: en Node, `navigator` y `performance` son globales
nativos y **asignarlos no toma efecto** — hay que usar `Object.defineProperty`, o el VAD
ni arranca y los "ok" son falsos.

### Trampas que costaron sangre (no re-descubrirlas)
- **`\b` de JavaScript no considera letra la `ñ`.** La regex de "frase colgada" abría
  frontera dentro de la palabra y **"muéstrame el sueño" contaba como acabado en la
  conjunción "o"**. Con "sueño" en medio de casi todo lo que dicta, habría esperado de
  más justo en las frases más comunes. Se usa `(?:^|\s)`, no `\b`.
- **La ventana de gracia por tiempo NO evita el eco.** Bloquea lo que *llega* en ese
  rato, pero Chrome tarda más de un segundo en dar una frase por final, así que la cola
  de la voz de Jarvis aterrizaba después y entraba como si la hubiera dicho Hugo (su
  "…rellena el keep, anda" volvió como "rellena el Panda" y se contestó a sí mismo). Lo
  que funciona es **`rec.abort()`** al acabar de hablar: descarta el audio sin emitirlo.
  `stop()` haría lo contrario, finalizarlo.
- **El filtro anti-eco por contenido se descartó a propósito.** El caso de uso de Hugo es
  cortarle **para citarle** ("no te he dicho el peso, te he dicho el sueño"): un filtro
  de similitud se comería justo esas frases.
- **`autoGainControl` va a `false`** en el `getUserMedia` del VAD: el AGC sube la
  ganancia en los silencios y destroza la escala sobre la que se mide.
- **El suelo de ruido se congela mientras Jarvis habla.** Si no, aprende su eco, el
  umbral sube con él y el corte por voz **deja de funcionar poco a poco y sin síntoma**.
- **El orbe parpadeaba** hablando/pensando en cada frase, con su transición de 0,75 s,
  porque `sonando` caía a false en el hueco entre frases. Ahora solo se apaga al acabar
  el turno.
- **`hablar()` no tenía respaldo a la voz del navegador** (solo `decir()`, que ya no se
  usa). Con el 8123 apagado, Jarvis era **mudo del todo** y parecía que la conversación
  estaba rota. Ya cae al navegador, con temporizador de seguridad: si `speechSynthesis`
  no avisa de que ha terminado, el micro se reabre igual en vez de quedarse colgado en
  "hablando" para siempre.

### Los cuatro fallos que no eran de voz
1. **`dia` leía solo `derived_diario`**, que únicamente regenera el pipeline. Como no
   pasa desde el 21/08, juraba "no hay datos del 5" con el PM del 5 guardado, y Jarvis se
   contradijo delante de Hugo. Ahora lee también las pestañas ORIGEN. **Es exactamente la
   trampa que ya estaba documentada para `huecos.py`**, en otro consumidor: si añades una
   herramienta que mire días recientes, no la cuelgues de `derived_diario`.
   - Ojo al añadir campos ahí: **`dolor_sesion_keep` no se incluye nunca** junto al del
     formulario, o Jarvis lee el mismo dolor como dos episodios.
2. **El modelo anida los argumentos** de vez en cuando: mandó `guardar_pm({valores:{…}})`
   y el guardado moría con "'valores' no es un campo". `chat._aplanar` los sube. Se
   corrige en vez de rechazarse porque el coste es asimétrico: aceptarlo no rompe nada
   (los nombres se validan igual justo después) y rechazarlo le cuesta a Hugo dictar el
   parte entero otra vez.
3. **`_tool_guardar` pedía `res["valores"]`**, pero `formularios.guardar` devuelve
   `guardado`. `KeyError` **después** de escribir en la hoja: el dato estaba guardado y
   Jarvis le dijo a Hugo que no sabía si se había perdido. Arreglado, y además: **una vez
   escrita la hoja esa herramienta ya no puede devolver un error**; si falla montando el
   resumen, dice "guardado" y avisa aparte. Un fallo de formato no puede hacer que Hugo
   dicte encima de un dato que ya está bien.
   - Este solo salió a la luz al arreglar el 2: antes el guardado moría antes de llegar a
     esa línea. Los dos hablaban de "valores" y eran fallos distintos.
4. **Un fallo de herramienta era invisible**: el error solo viajaba al modelo, sin dejar
   rastro. Ahora se registra con los argumentos, que es lo que hace falta para
   reproducirlo.

### Vocabulario en `personalidad.py`
Hugo dice "el PM", "el forms", "el keep", "volcar", "el parte", y Jarvis no sabía a qué
se refería. Hay un glosario, y una regla: **no afirmar "no tienes nada del día X" con una
sola herramienta vacía** sin cruzarlo con `estado_formularios`.

### PENDIENTE DE COMPROBAR: que solo le calle la voz de Hugo
Lo que está probado es que **su propio eco** no le corta y que **la voz de Hugo sí**. Lo
que NO se ha probado todavía, y lo pidió él expresamente, es todo lo demás que suena en
una habitación real:

- la tele o música de fondo (lo peor: es voz, sostenida, y el VAD no distingue de quién),
- alguien más hablando en la habitación o una llamada,
- teclear, la silla, una puerta, el ventilador, ladridos,
- respirar fuerte o carraspear cerca del micro.

**Por qué importa más de lo que parece:** el fallo no se ve. Jarvis se calla a media
frase y desde fuera parece que "se ha cortado solo" o que va lento — que es justo la
queja con la que empezó todo esto. Y como el VAD mide ENERGÍA, no timbre, no tiene forma
de saber que esa voz no es la de Hugo.

**Cómo comprobarlo, que si no es a ojo:** encender la traza
(`localStorage.setItem("jarvis.voz.debug","1")` y recargar), pedirle algo largo, y
mientras habla ir metiendo cada ruido de la lista **sin decir nada**. La traza da el
nivel contra el umbral cada segundo: se ve cuánto mide cada cosa y cuánto margen queda.
Un `=> CORTADO por tu voz` con Hugo callado es un falso positivo.

**Si falla:** subir `MINIMO_HABLANDO` en `vad.ts` (hoy 0.038) hasta que el ruido deje de
llegar, y comprobar después que Hugo sigue pudiendo cortarle sin gritar. Si el problema
es la tele, el umbral de energía **no lo va a resolver del todo** y habría que atacarlo
por otro lado (limitar la banda a 200-1000 Hz ayuda con el teclado y el ventilador, no
con una voz). En ese caso, lo honesto es dejar el corte por voz más sordo y apoyarse en
el botón, que nunca falla.

### Qué queda suelto por aquí
- **`escucha.py` no se tocó.** Sigue con los dos mismos fallos (`SILENCIO_FIN_MS` fijo y
  `mudo_hasta` bloqueando todo mientras habla). Hugo usa el orbe del navegador; si algún
  día vuelve al micro externo, hay que portar esto.
- **Para la VM de GCP**: `getUserMedia` y la Web Speech API **exigen contexto seguro**.
  Por el `http://100.x.y.z` de Tailscale la voz no arranca; hará falta HTTPS
  (`tailscale cert` / `tailscale serve`). `vite.config.ts` sirve en claro.
- **"No he tomado cafeína" no se guarda como 0**: el modelo omite el campo en vez de
  mandar 0. No es el mismo fallo y no se tocó; sería una línea en `personalidad.py`.

---

## 14. La voz en el MÓVIL (2026-09-12) — por qué Android no es Chrome

Contexto: desde que el dashboard vive en la VM, Hugo entra desde el teléfono
(`poco-f6-pro`, Android + Chrome). La voz de SALIDA funcionaba; la de ENTRADA no. El orbe
se quedaba escuchando eternamente y nunca pasaba a pensar.

**La lección general, si hay que quedarse con una: el reconocedor de Android NO se
comporta como el de escritorio, y las diferencias no dan error.** Fallan en silencio y
parecen otra cosa.

### Lo primero fue el instrumento, no la teoría
Nada de esto se diagnostica de oído, y en el móvil **no hay consola donde mirar**. Antes
de tocar la voz se añadió:
- Los eventos de ciclo de vida del reconocedor a la traza (`onstart`, `onaudiostart`,
  `onsoundstart`, `onspeechstart`, `onend`). La cadena sana es
  `arrancado → capturando → ALGO → VOZ → final`, y **dónde se para dice qué pasa**.
- **Todos** los errores, no solo el de permiso. Antes un `audio-capture` (micro ocupado)
  era indistinguible de no oír nada: el error solo se tragaba.
- `TrazaVoz.tsx`, un visor en pantalla con botón de copiar, porque el móvil no tiene
  consola. Se enciende con **`?vozdebug=1` en la URL** (no solo con `localStorage`, que
  ahí tampoco se puede escribir) y se pliega, porque tapaba el chat.

La primera traza cerró el caso en un minuto: `arrancado → capturando → (nada) → cerrada`,
en bucle cada 5 s, sin un solo error, **mientras el VAD medía la voz de Hugo
perfectamente**. Micro abierto, reconocedor sordo.

### Fallo 1 — en Android el micro es EXCLUSIVO
El reconocimiento de voz de Android **lo sirve el sistema**, no el navegador, y quiere el
micro para él solo. El detector de barge-in (`vad.ts`, de la §13) abría su propio
`getUserMedia` en `encender()` y lo tenía ocupado **toda la sesión**, así que al
reconocedor le llegaba silencio. En el portátil los dos conviven; por eso solo se veía en
el teléfono.

Arreglo: **el VAD solo abre el micro mientras Jarvis habla**, que es lo único para lo que
sirve (`alHablar` ya se desentendía salvo que estuviera sonando su voz).

> **EL RELEVO DEL MICRO HAY QUE ESPERARLO, NO SOLO ORDENARLO.** Esto costó dos rondas más
> (2026-09-12, tarde). No basta con "primero suelto uno y luego abro el otro": las dos
> operaciones son **asíncronas** y hacerlas seguidas deja al segundo arrancando sobre un
> micro que todavía está cogido. Y no da error — arranca sordo.
> - `vad.parar()` **devuelve una promesa**: `track.stop()` sí es síncrono, pero
>   `ctx.close()` no, y hasta que no resuelve el contexto sigue enganchado.
>   `finHabla` espera a esa promesa antes de reabrir el reconocedor.
> - `soltarReconocedor()` espera al **`onend`** del reconocedor (con un plazo de 300 ms de
>   red, por si ya estaba parado y `onend` no llega). `empezarAHablar` lo espera antes de
>   abrir el VAD.
>
> Los dos síntomas parecían cosas distintas y no tenían nada que ver con lo que parecían:
> - Reabrir el reconocedor demasiado pronto → **se come el principio de la frase** al
>   cortarle ("no pilla el principio cuando le interrumpo").
> - Abrir el VAD demasiado pronto → mide **ceros**, y el corte por voz no va. Ese
>   `nivel 0.0000` llevaba dos días en las trazas **pareciendo una buena noticia** sobre la
>   cancelación de eco.

Detalle que parece un problema y no lo es: el VAD arranca de cero en cada turno con el
suelo de ruido por defecto. No pasa nada porque `hablandoJarvis()` sigue siendo falso
mientras se genera el TTS (segundos), y en ese hueco aprende la sala.

### Fallo 2 — Android repite la frase ENTERA en cada resultado
El estándar dice que cada hueco de `ev.results` es un segmento distinto. Eso hace el
escritorio. **Android mete la frase entera desde el principio en cada resultado nuevo**:

```
final está
final está escuchando
final está escuchando varias
final está escuchando varias veces lo que digo
```

Pegar el último trozo (lo de siempre) multiplicaba: tres "hola" le llegaron a Jarvis
**como veinticinco**, y "qué tal estás tío" como "qué qué tal qué tal estás tío". Sumar la
lista entera —el arreglo "obvio"— **falla igual**, y se probó y se descartó.

Lo que vale es `reconstruir()` (exportada en `voz.ts`): mira si uno es **prefijo** del
otro. Si lo es, es la misma frase más completa y sustituye; si no, es material nuevo y
concatena. Correcto en los dos navegadores **sin preguntar cuál es** — nada de
`if (esAndroid)`, que es una trampa para dentro de seis meses.

Además, Android **cierra la sesión de escucha cada ~5 s**. Como al reabrir `ev.results`
viene vacío, hace falta `arrastreRef`: lo dicho hasta ahí se guarda, o una frase larga
partida por ese cierre pierde su primera mitad.

### Fallo 3 — los números dictados llegan como DÍGITOS
Jarvis le pide el RPE, Hugo dice "cinco", y **Android manda `"5"`**. Un carácter. El
filtro de ruido (`MIN_CARACTERES = 3`, que existe para tirar los fragmentos de un golpe o
una respiración) se lo comía en silencio. Lo mismo con "sí" y "no", que son justo las
respuestas a lo que Jarvis pregunta rellenando un formulario. De ahí el síntoma que
describió Hugo: *"no se activa el micro cuando el mensaje es corto"*.

Excepción `CORTA_VALIDA`: dígitos (con decimal, por "81,8") y un puñado de palabras
cortas de verdad. **El filtro tiene que seguir existiendo, pero no puede comerse un dato
correcto.**

### Fallo 4 — dudar en voz alta le hacía cortar
Petición literal: *"si digo 'eeee…' como pensando, que no se ponga a pensar"*. Una duda
suelta caía en el filtro de ruido, que hace `return` **sin rearmar el reloj de silencio**
— o sea que justo cuando dudaba era cuando más le cortaba.

Ahora hay `DUDA`: no entra en el mensaje (no vamos a mandarle "eh" a Jarvis) pero rearma
con la espera larga. **Las vocales piden dos letras o una "h" detrás** (`ee`, `eh`, `mm`,
`hmm`): una "a" o una "e" sueltas son casi siempre un golpe, y tomarlas por duda alargaría
la espera con cada crujido. Lo destapó el test, no el oído.

### Cómo se prueba esto sin un móvil delante
- **`scratchpad/test_voz.cjs`** (62 casos): `reconstruir`, `clasificar` y `esperaDe`,
  contra las funciones **reales** sacadas con esbuild. Incluye las secuencias literales de
  la traza del móvil. Un calco pasa los tests y deja el fallo en producción, así que se
  bundlea el fichero de verdad:
  `esbuild src/lib/voz.ts --bundle --format=cjs --platform=node "--define:import.meta.env={}"`.
  Sin ese `--define`, `import.meta.env` es `undefined` y el módulo revienta al importarse.
- **`scratchpad/test_movil.cjs`**: un móvil simulado por **CDP** (no hay puppeteer en el
  proyecto; son 80 líneas con el `WebSocket` nativo de Node). Emula métricas, táctil y
  `Input.dispatchTouchEvent`, así que **el arrastre con el dedo se prueba de verdad**.
- **`scratchpad/test_escritorio.cjs`**: la regresión del PC. Obligatorio: estos arreglos
  tocan código que Hugo ya había dado por bueno en el portátil.

### El chat era INALCANZABLE en el móvil (y no era culpa de la voz)
`ChatExpanded` despliega el hilo con un progreso `p`, y ese progreso lo movía **un único
listener de `wheel`** — rueda de ratón, que en táctil **no se dispara jamás**. Con `p` en
0, la zona del orbe se queda el 100 % y la caja del hilo mide **0 px con opacidad 0**. No
es que estuviera más abajo: no existía. Por eso arrastrar el dedo "no hacía nada".

Ahora hay `touchstart`/`touchmove` **y** un botón visible ("▼ Ver conversación"), a
propósito redundantes: el gesto era **indescubrible incluso con ratón**. Mismo criterio
que el botón de "Cállate" de la §13 — si el gesto falla, el botón funciona siempre.

Dos desbordes más en 360 px, del mismo síntoma: el panel compacto tenía `height: 263`
fijo y el orbe `size={150}` cableado, así que el canvas **tapaba el campo de escribir**
(ahora es mínimo hasta `sm`, y el orbe 116 en estrecho); y el selector de rango se salía
103 px en el chat ampliado — un control que una conversación no usa, así que se le quita
igual que ya se le quitaba a formularios.

> **Sobre la §8 ("alturas de panel en px fijos, nunca en %")**: esa regla existe por el
> bucle de ResizeObserver del `ResponsiveContainer` de Recharts. El panel del chat **no
> lleva gráfico**, así que ahí no aplica. Está anotado en el propio código para que nadie
> lo "arregle" de vuelta.

### PENDIENTE: cortarle por voz desde el móvil
**Sin confirmar.** En la traza, mientras Jarvis habla el VAD marca `0.0000` clavado — que
es buena señal (su eco no se cuela, la cancelación del móvil funciona), pero **no
demuestra que oiga a Hugo por encima**. Los únicos números de su voz que hay son 0,0365 y
0,0755 contra un umbral de 0,038: **uno de los dos queda por debajo**. Puede que tenga que
alzar la voz, o que no funcione.

Si falla, la perilla es `MINIMO_HABLANDO` (`vad.ts`), y **con la traza se ajusta con
números en vez de a ojo**: sale `VAD mientras habla: nivel X / umbral 0.0380`. El botón de
"Cállate" no depende del micro y sigue funcionando siempre.

---

## 15. Que Jarvis pregunte por la gente que no conoce (2026-09-12)

Lo pidió Hugo con un ejemplo y pidiendo que se generalizara: escribe en la nota del PM
"ayer me lo pasé muy bien con Daniel" y Jarvis asiente como si supiera quién es. Que
pregunte. Y que si aparece otro Daniel que no encaja, pregunte si es otro, **porque puede
haber dos Danieles en su vida**.

### Lo que ya estaba (no reconstruirlo)
Las notas libres de los formularios **ya llegan al prompt** (`briefing.py`, "Notas
recientes de Hugo", las 8 últimas), y `recordar(tema, texto)` ya escribe en la tabla
`hechos`. Faltaba pedirle que preguntara — y, sobre todo, **que no preguntara dos veces**.

### La parte que NO es prompt, y es la que importa
`hechos_relevantes(limite=30)` rota en cuanto hay más de 30 hechos: mezcla los más
recientes con los que llevan más sin mencionarse. Eso está muy bien para "está leyendo
Shogun" y es **pésimo para "Daniel es su primo"**: el día que no le toque, Jarvis no sabe
quién es Daniel y **vuelve a preguntarlo**. Que te interroguen cada semana por lo mismo
es exactamente lo que haría que Hugo apagara esto.

Convenio: la gente va con tema **`persona:<nombre en minúsculas>`**, y esos hechos
**entran SIEMPRE y no cuentan contra `limite`** (tope propio `MAX_PERSONAS = 40`, por si
algún día son muchas). Son pocos y valen mucho por carácter.

### La regla, en `OPERACION` (no en `PERSONAJE`)
La separación del 2026-09-11 se hizo para poder tocar el tono sin arriesgar el manejo de
herramientas; esto es manejo de herramientas. Lo que dice, resumido:
- Preguntar por quien no esté en lo que sabe de su vida. Una frase, con interés de amigo.
- Vale también para lo que escribe en las **notas**, no solo para lo que dice hablando.
- **Dos personas con el mismo nombre**: si no encaja con el que conoce, preguntar si es el
  mismo y guardar el segundo **distinguido**, sin pisar al primero.
- **Preguntar UNA vez.** Si no contesta, apuntar "lo mencionó el <fecha>, aún no sé quién
  es" y dejarlo estar. Sin esto se convierte en un incordio.
- No preguntar en medio de un formulario, ni cuando toque bajar el tono. Esa regla de
  `PERSONAJE` manda siempre.

### Comprobado con el modelo real (14 turnos), no solo con la regex
Contra una base **temporal** — su `jarvis.db` son conversaciones privadas y no se ensucia
con Danieles inventados. Lo que salió:
- *"¿Ese Daniel es el del gimnasio o hay otro Daniel soriano que no me habías
  presentado?"* → y luego guardó los dos por separado, sin pisar al del gimnasio.
- Ignorándole la pregunta sobre alguien nuevo: apuntó *"Mencionada el 2026-09-12… Aún no
  sé quién es"* y **no volvió a preguntar** en los turnos siguientes.
- Con una lesión de por medio, ni mencionó al nombre nuevo.
- 12 tests más (`scratchpad/test_memoria.py`) cubren la rotación, que es la parte que se
  degrada en silencio.

### AVISO para quien pruebe esto: la hoja NO está aislada
Redirigir `memoria.DB` aísla la base de datos, **pero no la hoja de cálculo**. Si en la
prueba Jarvis decide llamar a `guardar_pm`, **escribe en la hoja real de Hugo**. Pasó el
2026-09-12: quedó una fila inventada del 2026-09-12 en `wellness_pm` (energía 7, sensación
6, RPE 8, "Entrené con Cristina") que hubo que borrar a mano. No pisó nada suyo —esa fecha
no existía— pero el semáforo daba el PM por hecho y `rpd_sesion` habría contaminado el
sRPE al pasar el pipeline.

Para la próxima: o no meter datos de formulario en los guiones de prueba, o redirigir
también `formularios`/`sheets`.

---

## 16. Segunda vuelta del móvil (2026-09-12) — y el modelo rápido de muletillas

Hugo probó lo de la §14 desde el teléfono y volvió con cuatro cosas. Tres eran fallos
nuevos; la interesante es que **dos de ellas son el mismo error de fondo que ya había
salido dos veces: una interacción que solo existe con ratón.**

### El chat seguía siendo inalcanzable, y no era el arreglo de la §14
"No hay ni flecha ni nada." El gesto táctil de la §14 funcionaba — pero **no se llegaba a
la pantalla donde vive**. El botón de ampliar un panel es `opacity-0` y solo aparece con
`group-hover`, y **en táctil no hay hover**: era invisible en TODOS los paneles del móvil.
Y como la otra forma de ampliar es tocar el fondo de la tarjeta, en el chat —donde casi
todo lleva `data-no-expand`— no había ninguna.

Arreglado con `[@media(hover:none)]:opacity-100`, que lo enciende solo donde no hay ratón:
en el escritorio sigue apareciendo al pasar por encima, que es como a Hugo le gusta.
**Estaba DUPLICADO**: `Panel.tsx` y `Readiness.tsx` llevan cada uno su copia del botón, y
arreglar solo el primero dejaba Readiness fuera. Lo cazó el test, no la vista.

> Van tres: el gesto de `wheel`, el botón de ampliar y (antes) el hover. **Si añades una
> interacción, pregúntate cómo se hace con un dedo.**

### La duda solo contaba si venía sola
`DUDA` miraba si el final ERA una vacilación. Pero en Android cada final trae la frase
entera, así que en cuanto Hugo había dicho algo antes, "pues no sé, eeee" llegaba como un
único final y no casaba: seguía cortándole. Ahora hay `DUDA_FINAL`, que mira **el final de
lo acumulado**, y `esperaDe` la consulta junto a `COLGADA`.

Ojo al conjunto: **solo los sonidos** (`eeee`, `mmm`, `eh`, `o sea`, `a ver`) valen al
final de una frase. Las palabras de verdad (`esto`, `bueno`, `pues`) solo cuentan si vienen
solas — al final de una frase son normales ("¿qué es esto?", "está bueno") y meterlas ahí
haría esperar de más constantemente.

### Cortarle le borraba la pregunta del hilo (el peor de los tres)
Le preguntó a qué valor le cambiaba la energía, Hugo contestó "a 7", y Jarvis respondió
"7 qué, tío". **No era el reconocedor: era la memoria.**

En la §13 se decidió que al cancelar no se guardara NADA, razonando que media respuesta es
peor que ninguna porque el modelo la leería como dicha. **El razonamiento daba por hecho
que si Hugo corta es porque la respuesta iba mal**, y el caso normal resultó ser el
contrario: **le contesta a media frase**, que es justo lo que busca el modo conversación.
Al borrar el turno, la pregunta de Jarvis desaparecía y el siguiente se quedaba sin pie.

Ahora se guarda **lo que de verdad se emitió**, con la marca `[…Hugo te cortó aquí]`. Para
eso `chat.responder` envuelve `al_texto` en `_emitir`, que va copiando los trozos: es el
único sitio donde se sabe qué llegó a salir. Ni se pierde el contexto ni el modelo cree
que lo dijo entero. Si no había emitido nada, no se guarda un mensaje vacío.

### Que lea las notas por su cuenta
Preguntaba por alguien solo si Hugo lo mencionaba hablando. Lo que quería es que **lea las
notas de los formularios y pregunte por lo que pone ahí**, sin que él saque el tema. Es un
cambio de prompt (las notas ya llegaban en el parte), con dos frenos: interesarse por lo
que cuenta la nota y no solo por el nombre, y **una sola cosa por conversación** — las
notas traen varios días y repasarlas en fila es un interrogatorio.

Comprobado con el modelo real: con un "buenas" como único mensaje, sacó *"en tu nota de
ayer decías que te lo pasaste muy bien con Berto… ¿quién es Berto?"*.

---

## El modelo rápido para las muletillas (`rapido.py`)

Lo pidió Hugo. Contexto de por qué antes se dijo que no: las muletillas son audio
**pregrabado** (latencia cero, generado una vez con el modelo caro, con retintín), y
escribirlas a medida obliga a sintetizarlas en el momento, en modo rápido, donde salen
planas. Eso sigue siendo verdad. **Lo que ha cambiado es que ahora hay tiempo**: la primera
muletilla ya no se suelta al segundo, sino a los 4,5 s (§14), así que cabe generar texto y
sintetizarlo antes de que haga falta.

**Decisiones, y por qué:**
- **Se usa Groq**, y las variables se llaman `GROQ_*` igual que las de Anthropic y Ollama.
  La elección salió de MEDIR, no de leer (tabla abajo): aquí no importa que el modelo sea
  listo —es una frase de diez palabras— sino que conteste rápido, y eso lo pone el
  hardware de quien lo sirve.
- **Habla API de OpenAI, que es la que expone Groq**, con `requests` y sin SDK. Efecto
  lateral útil: cambiando `GROQ_URL` sirve cualquier otro proveedor compatible sin tocar
  código. Un SDK más solo sería otra cosa que actualizar.
- **NINGÚN nombre de modelo cableado.** `GROQ_MODELO` viene vacío a propósito: los
  catálogos cambian (Groq retiró varios en agosto de 2026) y un identificador quemado se
  pudre en silencio. Sin él, la función sencillamente no se activa.
- **Falla hacia el lado bueno.** Sin clave, con error, con la URL mal o pasado
  `GROQ_TIMEOUT_MS` (3000 ms por defecto), devuelve `None` y **se tiran las pregrabadas
  de siempre**. Una muletilla que llega tarde es el silencio MÁS la muletilla: peor que no
  tenerla. El plazo es duro y está probado que corta de verdad.
- Recorta lo que devuelven los modelos pequeños cuando se emocionan (comillas, varias
  líneas, párrafos). Se recorta en vez de descartarse: una frase de más no molesta y
  quedarse sin muletilla sí deja el silencio que esto viene a tapar.

**Por dónde va**: `main.eventos()` pregunta a `rapido.muletilla(mensaje)` cuando el
enrutado ya ha decidido que toca coletilla. Si sale texto, el evento SSE lleva
`escrita: true` y el navegador lo sintetiza con `rapido: true`; si no, viaja el nombre del
pool y todo sigue como antes.

**Qué falta por saber, y solo se sabe usándolo**: si una muletilla a medida y plana suena
mejor o peor que una pregrabada con retintín pero genérica. **Es una cuestión de gusto de
Hugo, no técnica.** Si no le convence, se apaga vaciando `GROQ_MODELO` en el `.env`, sin
tocar código.

### Qué modelo, y por qué NO se elige leyendo
`scratchpad/elegir_modelo.py` pregunta al proveedor qué modelos deja usar esa clave y los
cronometra con el caso real. Medido el 2026-09-12 en Groq, y **nada de esto sale en un
benchmark**:

| Modelo | Mediana | Qué pasa |
|---|---|---|
| `qwen/qwen3.8-27b` | 281 ms | El más rápido, y **descartado por Hugo**: "lamentable, nada que ver con el tono". Soltaba "no se te escapa el pinto" y, a un "estoy hecho polvo", "pareces un desastre" |
| `allam-2-7b` | 367 ms | Rápido pero escribe mal ("el largo dormimiento") |
| `openai/gpt-oss-20b` / `120b` | 407 / 422 ms | **Devuelven texto VACÍO**: razonan, y con `max_tokens: 40` no queda nada para la respuesta |
| `qwen/qwen3.6-27b` | 430 ms | Escupe su razonamiento (`<think>…`) dentro del contenido, en inglés |
| `groq/compound-mini` | ~1,5 s | **El elegido.** Es el que escribe como Jarvis. Lento solo en apariencia: hay 4,5 s de margen |

**La velocidad NO es el criterio.** El primer elegido fue el más rápido y Hugo lo tiró a
la basura al oírlo. Lo que hace que suene a Jarvis no es el modelo: son los **ejemplos**
del prompt, que ahora son las muletillas pregrabadas que escribió él a mano. Describir un
tono con adjetivos ("con retintín") no le sirve a un modelo pequeño — se lo inventa.
Si algún día se retoca el personaje, esos ejemplos hay que retocarlos con él.

De ahí salen **tres defensas en `rapido.py` que no son paranoia, son cosas que pasaron**:
1. Se quita el bloque `<think>…</think>` antes de nada.
2. **Las etiquetas de intención se filtran Y se normalizan.** Se inventó `[dar un respiro]`,
   `[browsing]` y un `[miejamencioso]` que ni es una palabra; y devolvió `[ sighs ]` con
   espacios dentro, que el motor de voz no reconoce. Una etiqueta desconocida **se lee en
   alto**: la diferencia entre una coletilla y Jarvis diciendo "corchete browsing".
3. Si tras filtrar no queda ni una palabra (devolvió solo `[sarcastic]`), se descarta.

### El límite de Groq es de TOKENS, no de peticiones
HTTP 429: `input tokens per minute (ITPM): Limit 7000` en el plan gratis. O sea que **lo
que gasta cuota es el prompt de sistema**, que viaja entero en cada llamada: con ~500
tokens por llamada, 14 seguidas agotan el minuto. Por eso `_SISTEMA` está escrito corto a
propósito — si alguien lo alarga "para que quede mejor", reduce cuántas caben.

En uso normal (una por turno de conversación) no se roza. Y cuando se roce, cae solo a las
pregrabadas: comprobado que 8 de 14 llamadas en ráfaga devolvían `None` sin romper nada.

### Se pide EN PARALELO, por la misma cola que el texto
Importante y fácil de estropear: `rapido.muletilla` NO se llama antes de emitir. Se lanza
en su propio hilo y su resultado entra por `cola`, como un evento más.

Pedirla en línea retrasaba el primer trozo de respuesta **en pantalla** lo que tardara
(~400 ms de mediana, picos medidos de 1,1 s), y encima por una frase que puede acabar sin
usarse: si la respuesta real llega antes de los 4,5 s, el navegador la descarta. Y esperar
dentro del generador tampoco vale — es secuencial, así que bloquearía el texto igual.

Medido de extremo a extremo: muletilla a 1,06 s y primer texto a 16,4 s en una pregunta
con herramientas. Ahí se ve para qué sirve.

Probado en `scratchpad/test_rapido.py` (19 casos) contra un servidor que imita la API de
OpenAI: el cableado, el recorte, y sobre todo los cuatro caminos de fallo.

### AISLAR LA HOJA al probar con el modelo real
Repetido aquí porque ya costó una fila falsa (§15): redirigir `memoria.DB` **no** aísla
Google Sheets. En `scratchpad/test_notas.py` está la forma correcta — sustituir
`formularios.guardar` por un espía y **comprobar al final que la lista de escrituras está
vacía**. Sin eso, cualquier guion de prueba que roce un formulario escribe en los datos de
salud de Hugo.
