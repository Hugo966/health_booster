# Jarvis — Dashboard de bienestar · Handoff de contexto

> Resumen autocontenido para continuar el proyecto en una sesión nueva.
> Usuario: Hugo (powerlifter). Idioma de trabajo: español. Código y comentarios en español.

## 0. LO PRIMERO — pendientes del 2026-09-12 (leer antes de tocar nada)

Escrito en el portátil al cerrar la sesión. Cada punto lleva el porqué, porque el orden
importa y saltárselo tiene consecuencias.

> **Antes de desplegar nada, lee §0-bis: Jarvis cambió de máquina el 2026-10-02.** Otra
> VM, otro proyecto de GCP, otra URL y otro puerto. Esta sección §0 es anterior a esa
> mudanza.

### Resuelto: la fila falsa de `wellness_pm` — la borró Hugo el 2026-09-12
Queda aquí solo como aviso, porque la causa sigue viva: **redirigir `memoria.DB` aísla la
base de datos pero NO la hoja**. Probando con el modelo real, Jarvis llamó a `guardar_pm`
de verdad y escribió una fila inventada en los datos de salud de Hugo. La forma correcta
de probar algo que roce un formulario está en §15: sustituir `formularios.guardar` por un
espía y comprobar al final que no se escribió nada.

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
(`GROQ_MODELO=openai/gpt-oss-120b`, ~720 ms). Falta lo único que no se puede medir: si a él
le gusta más una coletilla a medida pero plana que una pregrabada con retintín pero
genérica. Si no le convence **se apaga vaciando `GROQ_MODELO`**, sin tocar código.
Ojo: la clave va en el `.env`, que NO viaja por git — **la VM necesita la suya**.
El porqué de cada decisión, al final de §16.

### LO SIGUIENTE: la voz del móvil sigue perdiendo palabras (§17)
**No está resuelto y hay una pista nueva que cambia el diagnóstico.** Hugo dice que suena
"turum, turum" todo el rato: es el pitido de Android al abrir y cerrar su reconocedor, o
sea que **se reinicia sin parar**. `continuous = true` NO se respeta ahí, así que "el
reconocedor escucha siempre" —la premisa del modo cascos— es falsa, y cada reinicio deja
un hueco sordo. Ése, y no el relevo del micro, es el que se come las primeras palabras.

**Empezar por MEDIRLO con la traza** (cuántos reinicios por minuto y de cuánto es el
hueco) antes de tocar nada; ya se ha fallado dos veces adivinando la causa. La salida que
probablemente valga —grabar el audio nosotros y transcribir con Whisper en Groq, que ya
está pagado— se lleva por delante de una vez TODOS los problemas de Android de §14 y §16.
Con sus pegas, todo en **§17**.

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

## 0-bis. LA VM (migrada el 2026-10-02 — leer antes de desplegar)

Jarvis ya **no** tiene VM propia. Vive en la del otro proyecto de Hugo, la del screener.

**Dirección: `https://swing-screener.tailc3e57b.ts.net:8443`** — solo dentro del tailnet.

**Por qué se movió.** Había dos e2-micro y eso cuesta dinero: la capa gratuita de GCP da
**720 h de e2-micro y 30 GB de disco EN TOTAL por cuenta de facturación, no por proyecto**.
Con dos VMs las horas se agotaban hacia el día 20 y a partir de ahí se cobraban las dos
(4,35 € en septiembre).

| Dato | Valor |
|---|---|
| Proyecto | `stock-screener-506508` (¡no `health-boost-500507`!) |
| Instancia | `swing-screener`, e2-micro, `us-central1-a` |
| Ruta | `/opt/health_booster` (antes `~/health_booster`) |
| Usuario | `hugo` (antes `hugogalvezu96_gmail_com`) |
| Python | 3.12 (antes 3.11) |
| Desplegar | `./desplegar.sh`, ya apunta ahí |

**Los ficheros son de `hugo`, pero tú entras como otro.** `gcloud compute ssh` inicia
sesión con el usuario derivado de la cuenta de Google (`hugogalvezu96_gmail_com`), no con
`hugo`, así que **todo lo de `/opt/health_booster` necesita `sudo`** — incluso LEER el
`.env`, que es `600 hugo:hugo`.

> Esto hizo perder una hora el 2026-10-03 y merece la pena entender por qué: un
> `grep '^GROQ_' .env || echo "no hay nada"` **no distingue "no hay coincidencias" de "no
> puedo leer el fichero"**. El `||` se tragó un `Permission denied` y dio por desaparecidas
> unas variables que estaban perfectamente, con lo que se "arregló" un problema inexistente.
> Es el mismo fallo que este handoff lleva documentando en el código (un `except` ancho
> que convierte un error en salida vacía), cometido en una herramienta de diagnóstico.
> Si consultas el `.env` de la VM: con `sudo`, y mirando el código de salida —`grep` sale
> con 1 si no encuentra nada y con 2 si no pudo leer—, nunca tapándolo con un `||`.
>
> Y al tocarlo, **conservar dueño y permisos**: reescribir el mismo inodo (`cat tmp > .env`)
> y no `mv tmp .env`, que lo dejaría de root y el servicio se quedaría sin poder leer sus
> claves — sin chat y sin voz, no solo sin muletillas.

**`desplegar.sh` estaba ROTO desde la mudanza** y se arregló el 2026-10-03. Por lo mismo:
hacía `git pull` y `rm -rf dist` como el usuario de la cuenta de Google, sobre un repo de
`hugo`. Git contesta `fatal: detected dubious ownership` y, con `set -e`, eso se lleva por
delante el resto del bloque — **no se extraía el dist ni se reiniciaba el servicio**.

Lo peor es el síntoma: imprime "4/4 Actualizando la VM…", suelta UNA línea de error y
termina. Parece que ha ido. **Si alguien creyó haber desplegado entre el 02/10 y el
03/10, no llegó nada.** La comprobación honesta es la línea `commit desplegado: <sha>`
que ahora imprime al final; si no sale, no se ha desplegado.

Ahora todo lo que toca `$RUTA` va con `sudo -u hugo -H`. **El `-H` no es adorno**: sin él
sudo conserva el HOME de quien llama y git busca el `~/.ssh/config` con el alias
`github-hb` en el home equivocado, fallando con `Permission denied (publickey)`. Y el
`.tgz` pasa por `/tmp` porque el home del usuario con el que entras no tiene por qué ser
legible para `hugo`.

**El puerto 8443 no es capricho:** el 443 de esa máquina lo ocupa el panel de Streamlit del
screener desde agosto. El frontend de Jarvis pide rutas absolutas (`/data`, `/tts`), así
que colgarlo de un subdirectorio lo rompería; cambiar de puerto lo deja en la raíz.

**El crontab es COMPARTIDO** entre los dos proyectos, con dos `CRON_TZ`: el screener va en
UTC (sus tandas están atadas a cierres de mercado) y Jarvis en hora de Madrid. No reordenar
líneas: `CRON_TZ` aplica a las que vienen DESPUÉS.

**La tanda `us+emerging` del screener se movió** de `15 21 * * 1-5` UTC a
`30 0 * * 2-6` (Madrid) porque Hugo habla con Jarvis antes de medianoche y es la única
tanda que consume RAM de verdad (puede durar 2h24 según el comentario de su crontab). El
**`2-6` es obligatorio**: al cruzar medianoche el cierre del VIERNES cae en SÁBADO, y con
`1-5` se perdería sin que nadie se entere. Ahora cae en 00:30-03:00, la única ventana en
la que Jarvis no tiene ningún cron.

**RAM**: 511 MB de 955 con las dos cargas conviviendo, más 2 GB de swap. Durante la tanda
larga pagina ~100 MB, de madrugada y sin nadie hablando con Jarvis.

**La VM `jarvis` YA NO EXISTE.** Se paró primero para tener vuelta atrás y se borró el
mismo 2026-10-02, porque parada seguía facturando su disco de 30 GB, que es justo lo que
sacaba a Hugo de la capa gratuita. Comprobado el 2026-10-03 desde el portátil:
`gcloud compute instances list` y `disks list` en `health-boost-500507` devuelven cero.

> **No hay vuelta atrás a la máquina vieja**, así que no la busques. Si hay que rehacer
> algo, el camino es `docs/reconstruir_vm.md`. Esta misma sección decía hasta el
> 2026-10-03 que la VM "quedó parada" y que había que borrarla, cuando ya estaba borrada:
> prometía un rollback inexistente.

### El respaldo de la memoria
`respaldar_memoria.py` sube `jarvis.db` a `gs://jarvis-respaldos-health-boost` (cron diario
a las 3:30). Era **lo único del proyecto sin copia**: los datos de salud viven en la hoja,
el keep en Drive, el código en git y las claves están en las dos máquinas de Hugo; esto son
sus conversaciones y los hechos que Jarvis ha aprendido.

Empuja la VM y no tiran las máquinas de Hugo **a propósito**: la VM está siempre encendida,
así que no depende de que él encienda un equipo ni de montar un programador distinto en
Linux y en Windows (su portátil es Windows: systemd no existe allí).

**No va a Drive aunque el keep sí viva en Drive**: un service account no puede ser
propietario de ficheros en Drive ni con una carpeta compartida —no tiene cuota de
almacenamiento— y la salida que propone Google son las unidades compartidas, que piden
Workspace. El bucket es gratis (capa siempre libre: 5 GB-mes; esto son 23 MB al año) y
**sobrevive a la VM**: borrarla no lo toca.

Escribe **siempre el mismo objeto**; el bucket tiene versionado, así que el histórico y la
rotación salen gratis. Y **verifica la base antes de subirla**: subir un fichero corrupto
encima del bueno sería peor que no tener respaldo, porque parecería que sí lo hay.

Restaurar:
```bash
gcloud storage cp gs://jarvis-respaldos-health-boost/jarvis.db . \
  --project=health-boost-500507 --account=hugogalvezu96@gmail.com
```

### Si hay que rehacer la VM
**No hay snapshots, y es una decisión de Hugo**: 0,25 €/mes para siempre no compensa frente
a montarla a mano las pocas veces que haga falta. Es viable porque **los datos no viven en
la VM** — están en los dos buckets, en la hoja y en Drive, y todos sobreviven a borrarla.
El manual, con los comandos que se ejecutaron de verdad en la migración, está en
**`docs/reconstruir_vm.md`**.

### El respaldo del screener
`/opt/swing-screener/respaldar.sh` sube `state.sqlite`, `out/` y `.env` a
`gs://swing-screener-respaldos` (cron 03:35, después de la tanda larga). Versionado con
caducidad a 30 días, porque son 4,4 MB diarios y sin caducidad serían ~1,6 GB al año contra
los 5 GB del tramo gratis.

**La VM tiene scope `devstorage.read_only`** y el IAM no lo arregla: los scopes de la
instancia mandan por encima, y cambiarlos obliga a parar la máquina. Por eso ambos
respaldos usan la clave del service account vía `CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE`.

**Y el script verifica el resultado en vez de fiarse del código de salida**: con los scopes
mal, `gcloud storage cp` imprimía el error y **salía con 0**. Un cron a secas habría fallado
cada noche en silencio. Comprueba que el fichero está en el bucket y tiene menos de 2 horas.

### Quitarse los 3,65 USD/mes de la IPv4 (investigado el 2026-10-02, SIN hacer)

Es el único gasto que queda. **Google no cobra IPv6**, así que una VM solo-IPv6 costaría
cero. El problema es qué alcanza desde ahí. Comprobado con `dig` contra 8.8.8.8 y 1.1.1.1:

| Lo que la VM necesita | IPv6 |
|---|---|
| Sheets, Drive, Storage | **Sí** (y además llegan por Private Google Access, gratis) |
| Anthropic — el chat | **Sí** |
| Intervals — HRV, sueño, pasos | **Sí** |
| Groq — muletillas | **Sí** |
| **ElevenLabs — la voz** | **NO** (`api.elevenlabs.io`, ni el dominio raíz) |
| GitHub | NO, pero se salva: que `desplegar.sh` empuje por `scp` en vez de que la VM haga `git pull` |

**Solo falla la voz.** Descartadas: Cloud NAT cuesta ~32 USD/mes (diez veces la IP) y los
NAT64 públicos son servicios comunitarios sin garantías.

**Así que la vía es cambiar de proveedor de voz**, y hay varios con IPv6. Lo que ElevenLabs
tiene de propio no es hacer tonos —eso es común— sino hacerlos con **etiquetas dentro del
texto** (`[sarcastic]`), que encaja con esta arquitectura porque Jarvis las escribe él solo
mientras genera la respuesta. Con los demás habría que pasar la intención **aparte** del
texto: `personalidad.py` ya le hace marcarla, así que sería extraerla en vez de reenviarla.
Cambio de diseño pequeño, no solo de URL.

| Proveedor | IPv6 | Control de tono |
|---|---|---|
| **OpenAI** `gpt-4o-mini-tts` | Sí | Campo `instructions` en **texto libre** ("habla con sarcasmo seco"). Más flexible que una etiqueta fija — el candidato fuerte |
| **Hume** (Octave) | Sí | Construido alrededor de la expresión emocional, con indicaciones de actuación |
| **Azure Speech** | Sí | SSML `mstts:express-as`, estilos con nombre (cheerful, sad, whispering…) |
| **Cartesia** | Sí | Voz conversacional de baja latencia con controles de emoción |
| Resemble | Sí | Expresividad; menos conocido |
| Neuphonic | Sí | Expresividad; menos conocido |
| Google Cloud TTS | Sí | Solo SSML: pausas y énfasis, **no** intención. Pero es la única que además sería gratis por Private Google Access |
| Deepgram, PlayHT, LMNT, Inworld | **No** | Descartados por IPv6 |

**Cómo decidirlo**: no leyendo, sino como se eligió el proveedor del chat — un arnés tipo
`comparar.py` que sintetice LAS MISMAS frases de Hugo con cada uno y las ponga una detrás
de otra. El requisito es que la ironía se oiga; el precio es secundario, porque el sarcasmo
era el requisito del personaje y no un adorno (ver su reacción al estrenar v3 en §
"CAPA DE VOZ"). **Si ningún sustituto convence, quedarse con ElevenLabs y pagar.**

**Revisar de vez en cuando si ElevenLabs añade IPv6**: Anthropic, Groq, Intervals y casi
todos sus competidores ya lo tienen, así que van a contracorriente. El día que lo hagan,
migrar a solo-IPv6 es medio día y el gasto baja a cero sin tocar la voz. Comprobarlo es un
`dig AAAA api.elevenlabs.io`, no otra investigación.

### Pendientes de la migración
- ~~Borrar la VM `jarvis`~~ — **hecho el 2026-10-02**. Queda una sola instancia y un solo
  disco de 30 GB: exactamente el límite de la capa gratuita.
- ~~Confirmar si la IPv4 externa se cobra~~ — **confirmado el 2026-10-02**, consultando el
  catálogo de precios de Google (`cloudbilling.googleapis.com`, servicio `6F81-5844-456A`,
  grupo `IpAddress`). **Sí se cobra**: el SKU *External IP Charge on a Standard VM* son
  0,005 USD/hora en `us-central1`, unos **3,65 USD/mes por VM**. No es gratis por ser
  efímera ni por tener la instancia encendida; lo que decía antes este handoff era falso, y
  explica parte de los 4,35 € de septiembre (con dos VMs eran dos IPs). Alternativas, todas
  peores: Cloud NAT cuesta MÁS (~0,044 USD/hora de gateway) y solo-IPv6 es gratis pero
  Anthropic y ElevenLabs podrían no tener IPv6, dejando a Jarvis sin chat ni voz. Se asume.
- **Darle a Jarvis la URL sin puerto** (idea de Hugo, aplazada). Hoy el 443 es del screener
  y Jarvis va en el 8443. Dos salidas: intercambiarlos (dos comandos, pero el marcador del
  screener pasa a llevar puerto) o un segundo nodo de Tailscale en la misma VM (bastante
  más lío). **Ojo: en Tailscale una máquina tiene UN solo nombre**, así que no se puede
  darle un alias `jarvis` a `swing-screener` sin ese segundo nodo.

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

### Sesión 2026-10-13 (que lo que Hugo escribe signifique lo que significa)
Seis peticiones suyas de una tacada, todas de lo mismo: el programa entero tiene que ser
la base de conocimiento de Jarvis. El `0x0` dejó de contar como serie fallada —era un
ejercicio que no hizo, y le metía 30 puntos de carga—, entró `Build II` con su
calentamiento (que NO va al keep y por tanto no puede ocupar un slot, o los nombres se
corren un puesto), el parser entiende los minutos y las series compuestas por tiempo, y
los formularios de la app dejaron el texto libre por el reloj nativo y una rueda tipo
Zepp. **Detalle en §19.**

Tocado: `entreno_pipeline.py`, `status_pipeline.py`, `briefing.py`, `chat.py`,
`personalidad.py`, `formularios.py`, `main.py`, `FormulariosPanel.tsx`,
`lib/formularios.ts`, `test_entreno.py` (nuevo), `CLAUDE.md`.
Pipeline pasado: el histórico ya está recalculado.

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
| `voz.ts` | `ESPERA_MULETILLA_MS` | 2600 | Lo pidió él a 4500 ("el orbe en pensando 4-5 s") y luego se le hizo largo ("tardas 4 s en contestar"). 2600 sigue dando de sobra al modelo rápido (~1,5 s) |
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

### El interruptor CASCOS / ALTAVOZ, y por qué existe
Con un solo micro **no se puede tener todo**, y esto no se arregla programando mejor:

- Mientras Jarvis habla, el micro lo tiene **el detector**, que solo mide energía y **no
  transcribe**. Por eso se puede cortarle hablando… pero **las palabras con las que le
  cortas se pierden**: para cuando el reconocedor coge el micro, ya las has dicho. Eso es
  el "no pilla el principio cuando le interrumpo" — y NO lo arregla afinar el relevo, que
  es lo que se intentó primero.
- Si en vez de eso deja uno escuchando siempre al reconocedor, no se pierde nada… pero por
  el altavoz se oiría a sí mismo.

Como no hay forma de saber por software qué salida está usando y Hugo dijo que **depende
del día**, lo dice él con un botón (`voz.cascos`, recordado en `localStorage`):

| | Altavoz | Cascos |
|---|---|---|
| Quién tiene el micro mientras Jarvis habla | el VAD | **el reconocedor, siempre** |
| Cortarle hablando | sí, por energía | sí, **por transcripción** (si llega texto, es Hugo) |
| El principio de tu frase | **se pierde** | se conserva entero |
| Anti-eco | hace falta (`abort()`) | no hace falta: su voz no llega al micro |

Dos trampas del modo cascos, las dos ya resueltas y fáciles de reintroducir:
- **`parar()` y `finHabla` NO deben abortar el reconocedor** ahí: se llevarían por delante
  justo lo que Hugo está diciendo para cortarle. Es lo contrario que con altavoz.
- **La sesión no se corta entre turnos, así que `ev.results` se acumula.** Se vacía en
  `despachar` (ahí sí se aborta), que es el punto seguro: acaba de terminar de hablar.

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
| `openai/gpt-oss-120b` | **~720 ms** | **EL ELEGIDO desde el 2026-10-03.** Razona: necesita `GROQ_ESFUERZO=low` y sitio de tokens. Se descartó por error el 12/09 (ver abajo) |
| `openai/gpt-oss-20b` | ~7,2 s | Escribe bien con `effort=low`, pero es diez veces más lento que su hermano mayor. Inservible |
| `qwen/qwen3.6-27b` | 430 ms | Escupe su razonamiento (`<think>…`) dentro del contenido, en inglés |
| `groq/compound-mini` | ~1,5 s | Fue el elegido del 12/09 al 03/10. **Groq lo RETIRÓ**: ver abajo |

### 2026-10-03: el modelo caducó, y los gpt-oss estaban mal descartados
**Groq retiró `groq/compound-mini`.** Las muletillas a medida llevaban semanas apagadas y
**no se notó**, porque degradar a las pregrabadas no rompe nada y esas suenan bien. Se
descubrió por casualidad, comprobando otra cosa. Dos consecuencias en el código:
- El **404 ahora es `log.error`** con el nombre del modelo y qué hacer, no un warning
  perdido. Es *el* fallo de esta pieza y tiene que gritar.
- El catálogo pasó de 7 modelos a 4 en tres semanas. **`elegir_modelo.py` no es una
  herramienta de una vez**: es lo que hay que correr cada vez que esto deje de sonar.

**Y una corrección a lo de abajo: los `gpt-oss` no "devolvían vacío" por malos, los
ahogaba yo.** Son modelos de RAZONAMIENTO: con `max_tokens: 40` se lo gastaban pensando y
no les quedaba nada para contestar. Con `GROQ_ESFUERZO=low` (que se manda como
`reasoning_effort`) y `MAX_TOKENS = 300`, `openai/gpt-oss-120b` contesta en ~720 ms y
escribe mejor que ninguno de los otros. Si un modelo devuelve cadena vacía, **sospecha del
presupuesto de tokens antes que del modelo**.

**Tercera cosa, de la misma tanda: si copia un ejemplo del prompt, se descarta.** Se midió
que 3 de cada 8 respuestas eran copias literales de las muletillas pregrabadas que se le
dan como ejemplo de tono. Eso es un cambio **a peor**: esa frase exacta ya existe grabada
con el modelo de voz caro y con retintín, mientras que la copia se sintetiza en modo
rápido y sale plana. `_es_copia_de_ejemplo` lo detecta y devuelve `None`, con lo que suena
la buena. Mira la inclusión en los dos sentidos, no la igualdad: lo típico no es clavarlo,
es soltar el ejemplo entero con cuatro palabras pegadas.

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

---

## 17. PENDIENTE — el reconocedor de Android se reinicia sin parar (2026-09-12, cierre)

**Estado: SIN RESOLVER.** Lo de arriba (§14, §16, el modo cascos) mejoró cosas, pero el
síntoma principal sigue: **se pierden las primeras palabras al cortarle**, en los DOS
modos, con cascos y con altavoz.

### El dato nuevo, y por qué lo cambia todo
Hugo: *"suena todo el rato turum, turum, como de abrir y cerrar el micrófono"*.

Ese es el pitido con el que Android avisa de que abre y cierra su reconocedor. Si suena
constantemente, **se está reiniciando sin parar**. Y eso tira abajo la premisa sobre la
que se construyó el modo cascos:

> **`continuous = true` NO se respeta en Android.** La sesión se cierra sola —por
> silencio, por fin de frase, o por nada— y `onend` la relanza a los 250 ms. "Que el
> reconocedor escuche siempre" **no existe** ahí: lo que hay es un bucle de sesiones
> cortas, cada una con su pitido y con **su hueco sordo de unos cientos de ms**.

O sea que el ladrón de las primeras palabras **no es (solo) el relevo del micro**, que es
lo que se arregló en `fa1c699`: son los huecos entre reinicios, que ocurren todo el rato y
también sin que nadie interrumpa a nadie. El `aplazar()` del hueco sordo compensa el
RELOJ, pero no recupera el audio perdido — eso no se puede.

### Antes de tocar nada: MEDIRLO
La traza ya registra `rec: arrancado` / `micro capturando` / `sesión cerrada`. Con
`?vozdebug=1`, hablar un minuto y contar:
- cuántos reinicios por minuto,
- cuánto dura el hueco entre `micro suelto` y `micro capturando`.

Eso dice si el problema es de 200 ms o de 1 s, y si merece la pena lo de abajo. **No
optimizar a ciegas otra vez**: ya se ha fallado dos veces adivinando la causa.

### La salida que probablemente valga: quitar la Web Speech API de en medio
Capturar el audio nosotros (`MediaRecorder` sobre el mismo `getUserMedia` que ya usa
`vad.ts`) y transcribir en el servidor. **Se lleva por delante, de una vez, TODOS los
problemas de Android que llevamos tres sesiones persiguiendo:**

| Problema | Qué pasa con esto |
|---|---|
| Micro exclusivo, relevo VAD ↔ reconocedor (§14) | Desaparece: un solo `getUserMedia`, el VAD y la grabación comparten pista |
| Reinicios, pitidos y huecos sordos (esto) | Desaparecen: la captura no se corta |
| La frase entera repetida en cada resultado (§14) | Desaparece: `reconstruir()` dejaría de hacer falta |
| Los números dictados como dígitos (§14) | Depende del modelo, pero `CORTA_VALIDA` ya lo cubre |
| El interruptor cascos/altavoz (§14) | Probablemente sobra: el corte por voz lo seguiría haciendo el VAD |

**Y la pieza ya está medio puesta**: Hugo tiene clave de Groq, y en su catálogo aparecen
`whisper-large-v3-turbo` y `whisper-large-v3`. Mismo proveedor, misma clave, mismo cliente
compatible con OpenAI que ya hay en `rapido.py`.

Lo que habría que resolver, y hay que decirlo antes de vendérselo:
- **Deja de ser en directo.** Hoy se van viendo los parciales; con esto habría que trocear
  (mandar cada ~2-3 s) o esperar al final del turno. El fin de turno lo puede marcar el
  VAD, que ya detecta cuándo deja de hablar.
- **Latencia nueva**: subir el audio + transcribir. Whisper turbo es rápido, pero hay que
  MEDIRLO con un trozo de 10 s antes de decidir.
- **Coste**: hoy la transcripción es gratis (la pone el navegador). Pasaría a facturarse
  por minuto de audio.
- El respaldo de la Web Speech API conviene dejarlo: en el portátil funciona bien y no
  tiene ninguno de estos problemas.

### Lo que NO hay que volver a intentar
- **Afinar el relevo del micro.** Ya se hizo (esperar a `ctx.close()`, esperar al `onend`)
  y no era eso. Está en `fa1c699` y se queda porque es correcto, pero no resuelve esto.
- **Dar por hecho que el reconocedor puede quedarse escuchando.** No puede. Es lo que se
  supuso al hacer el modo cascos y es falso.

## 18. Rellenar formularios hablando (2026-10-12, `df9c102`)

Hugo intentó rellenar cuatro AM atrasados desde el móvil: *"no tiene memoria, me corta, no
se entera ni del clima, le cuesta guardar las cosas, es desesperante"*. **No era un fallo,
eran cinco**, y dos explican casi todo. Está desplegado y pendiente de que él lo pruebe
con un formulario de verdad.

### 18.1 El enrutado contestaba SIN VER EL HILO (la gorda)
`enrutar()` manda a Haiku **el mensaje suelto**, sin una línea de conversación. Si Haiku
decide que es charla corta devuelve `RESPUESTA:` y el turno se cierra ahí: **Sonnet no se
entera**. Resultado literal, en mitad de un formulario:
- *"no tengo memoria de mensajes anteriores. Empieza de cero conmigo"* — **mentira**, el
  hilo estaba ahí; el enrutado se inventó una limitación que no existe.
- *"no necesitas repetir como un loro"* — ante "le pongo un uno".

**El atajo solo vale para ABRIR conversación.** `main.py` descarta `ruta["respuesta"]` si
`memoria.conversacion_caliente(sesion)` (último mensaje hace < 10 min) y se va por el
camino largo; la muletilla sí se mantiene. Un "hola" en frío sigue saliendo en 0,7 s, que
es para lo que se hizo el atajo. **Cualquier atajo nuevo que responda sin el hilo tiene
que pasar por la misma puerta.**

### 18.2 La duplicación del dictado eran REVISIONES, no repeticiones
`reconstruir()` ya sabía que Android reemite la frase entera y comparaba **prefijos**. Pero
Android también **corrige la cola**: `…al levantarme 7 estrés` pasó a `…al levantarme 7 es
3 3`. Ninguno es prefijo del otro → caía en "segmento nuevo" y **concatenaba**, una vez por
corrección. Así una frase llegó a Jarvis nueve veces.

Ahora mide **cuánto prefijo común comparten** (≈60 % del más corto → misma frase). Y se
queda con **la última, no con la más larga**: una corrección suele acortar ("ánimo de un
siete" → "ánimo de un ocho") y quedarse con la larga guardaría el número viejo en un
formulario de salud. Los casos reales de la transcripción están en `test_voz.cjs`.

### 18.3 Tres menores
- **Ventana del hilo: 20 → 60 mensajes.** Un AM son ~6 idas y venidas; cuatro días
  seguidos se comían la ventana entera.
- **Una sesión por día**: `hugo-YYYY-MM-DD` (`chat.ts`), con fecha **local**, no
  `toISOString()` (a las 23:30 en Madrid ya diría mañana). El historial se limpia solo al
  cambiar el día y el día queda entero — lo que pidió. En `jarvis.db` **no se borra nada**.
  El historial pintado lleva sello de sesión (`jarvis.chat.historial.sesion`) o vería
  burbujas de ayer sobre un hilo que el backend da por vacío.
- **Wake lock de pantalla** mientras la voz está encendida, **re-pedido en
  `visibilitychange`**: el navegador la suelta al cambiar de pestaña y no vuelve sola. Si
  no está soportada no pasa nada, es opcional por diseño.

### 18.4 "No escucha lo primero que digo": mitigado, NO arreglado
Se quitaron los 250 ms fijos antes de relanzar el reconocedor (se sumaban al hueco propio
de Android en cada ciclo, y el hueco es donde muere la primera palabra). El retardo
sobrevive **solo como freno**: si la sesión muere en menos de 400 ms desde que abrió, se
espera 600 ms. La causa de raíz sigue siendo **§17**, con su orden de medir primero.

### 18.5 Pendiente de esto
- Que Hugo rellene un formulario entero hablando. Es el único criterio que importa.
- **A veces confirma dos veces seguidas** al guardar (bucle de herramientas). Feo, no
  rompe nada, sin mirar.

## 19. Que entienda lo que escribe (2026-10-13)

Seis cosas que Hugo pidió juntas y van de lo mismo: **que lo que él apunta signifique lo
que significa**, dentro del programa y dentro de la cabeza de Jarvis. Cinco son del
parser y del prompt; la sexta es de los formularios de la app.

### 19.1 `0x0` no era un fallo, era un ejercicio que no hizo
Lo que separa los dos casos es **el peso**:
- `200x0@10` → lo intentó y no sacó la repe. Esfuerzo máximo: flag `fallo`, y en el sRPE
  pesa como una serie a RPE 10 × `FACTOR_FALLO` (3).
- `0x0` a secas → **no hizo el ejercicio**. Flag `no_hecho`, `n_series` a nulo, cero
  volumen y **cero carga**.

Hasta ahora los dos entraban como `fallo`, así que **saltarse un ejercicio le sumaba 30
puntos de sRPE**, los mismos que un intento a tope. Afecta a cinco días del histórico
(17/08, 03/09, 04/09, 09/09, 15/09) y a su carga de esas semanas, ya recalculada.

Los nombres de lo que no hizo salen por `entreno_sesion.no_hechos` y llegan al parte de
estado. **El número solo no servía**: "te faltó un ejercicio" no es nada, "no hiciste la
plancha" es una conversación. En el mismo saco entran los que se dejó sin apuntar al
final de la sesión, que ya se marcaban `no_hecho` desde antes.

### 19.2 El plan empieza a traer calentamiento, y el calentamiento no va al keep
`Build II SN` → (plan 2, bloque 3, "Build II"), que es el `BLOQUE 3` que Hugo ya escribe.

Desde `Build II S2` cada día del Excel abre con una cabecera `Warm up`. Hugo **no apunta
el calentamiento**, así que si esos ejercicios se quedan en la lista los nombres se
corren un puesto y la sentadilla pasa a llamarse "Tibial raises" — el fallo clásico de
este pipeline, y silencioso. `_sin_calentamiento` los quita.

No basta con saltarse la sección de la cabecera: **el mismo ejercicio se repite suelto al
final de Accesorios** (sesiones 1 y 3). Y tampoco vale filtrar por el prefijo "Warm up",
porque Hugo dice que no garantiza escribirlo siempre. Así que se recoge el nombre de lo
que cuelga de la cabecera y se borra donde reaparezca **en esa misma sesión**. El punto
ciego que queda: un ejercicio de calentamiento que NO salga nunca bajo su cabecera.

### 19.3 La notación de tiempo
`1"` es un segundo y `1'` **un minuto** (esto último no se entendía: el `2x1'@8` del
05/10 se leía como "1 serie de 2 repeticiones").

`2x30"-30"@7` es una serie **compuesta**: 2 series, y dentro de cada una 30 s + descanso
+ 30 s. Los tramos **no son series sueltas** —decisión de Hugo, y es la que manda en el
sRPE—, y pueden ser más de dos: `2x30"-30"-30"-20"`. Lo que lo distingue de dos series
distintas es que **entre series hay espacio y aquí no**: `2x7x10RIR0 - 6x10RIR0` son dos,
`2x30"-30"@7` es una. Ese criterio lo puso Hugo y ya estaba implementado para los rangos
de repes (`6x10-8RIR3`, unilateral: 10 de un lado y 8 del otro).

Las duraciones **se perdían enteras** (un `3x30"` guardaba "3 series" y nada más). Ahora
van a `nota`: `30"+30" = 60s`, `30"`, `tempo 2"`. A la nota y no a una columna propia
porque se quieren para leerlas, no para graficar la plancha.

### 19.4 Todo el programa es su base de conocimiento
Dos cambios para que Jarvis no pregunte lo que ya tiene delante:
- Las series que le llegan por la herramienta `dia` traen **`marca` y `nota`**. Sin eso,
  un día en el que se dejó medio entreno le llegaba idéntico a uno completo, solo que con
  menos filas.
- El prompt gana dos bloques: qué significa cada marca del keep, y la regla de cruzar
  antes de preguntar — **si no hizo un ejercicio y la nota del PM ya dice por qué, se
  comenta, no se pregunta**. Preguntarle lo que acaba de escribir es exactamente lo que
  hace insoportable hablar con él.

También se le dice, en el prompt y en la herramienta, que **el alcohol y la cafeína del
AM son de AYER**: el formulario se rellena al levantarse y él ya había pillado a Jarvis
tratándolo como lo de hoy.

### 19.5 Los formularios de la app, sin texto libre
Las horas usan `<input type="time">` (en el móvil, el reloj nativo; y no hay forma de
escribir algo que no sea HH:MM, que es lo que el backend exige). El peso y la cafeína se
meten con una **rueda** tipo Zepp: el peso de 0,1 en 0,1 y la cafeína de 50 en 50.

La rueda **se despliega al pulsar** y se cierra al elegir; abierta siempre ocupaba cinco
filas por campo y el formulario se convertía en una tira. Cerrada enseña el valor (o la
última vez que lo registró). Se puede **girar o pinchar la opción**: con el ratón acertar
girando es un incordio y el valor que quieres suele estar a la vista. Al abrirse hace
`scrollIntoView({block:'nearest'})`, porque si el campo cae al final del formulario —que
tiene su propio scroll— la rueda se abriría medio tapada.

El salto lo define `formularios.ESQUEMA` con el campo `paso`, por lo mismo que los
rangos: si lo declara el frontend, acaban divergiendo.

La rueda **arranca en el último valor registrado** (`formularios.sugerencias`), que para
el peso es casi siempre el valor correcto ±0,2 kg. Esa sugerencia **viaja aparte de los
valores y no se guarda si él no toca la rueda**: si se mandara sola, abrir el formulario
y darle a Guardar apuntaría el peso de la semana pasada como la pesada de hoy. Solo se
pinta ventana (±50 pasos alrededor del punto de partida): el peso va de 30 a 300 kg, que
a 0,1 son 2701 opciones, y eso en el móvil no se scrollea.

### 19.6 El entrenador escribe el mismo ejercicio de varias formas
Al revisar el plan con Build II dentro salieron **111 nombres para 100 ejercicios**. No es
cosmético: dos nombres son dos históricos, así que la sentadilla principal de Hugo
**empezaba de cero al entrar en Build II** (`tacón 2 cm` → `tacón 2cm`) y su banca de
competición estaba partida en dos DENTRO DE LA MISMA SEMANA (`Banca competición` en la
sesión 2, `Comp bp` en la 4).

Cuatro eran puro formato y se arreglaron solas (mayúsculas, un espacio doble, `2 cm` vs
`2cm`): `_key` ya ignora tildes, mayúsculas y espacios de más, así que basta con que
ambas caigan en el mismo `ALIAS`. Y `canon_exercise` colapsa los espacios internos, que
es de donde salía `Hip thrust  en máquina`.

Las otras once las confirmó Hugo una a una, porque **la regla de que las variantes no se
fusionan hace que adivinar sea caro**: fusionó `Sumo dl`/`Peso muerto sumo`,
`Ext cuádriceps`/`Extensión cuádriceps`, los tres tríceps con barra en polea, los dos
jalones al pecho estrecho/cerrado, `Sq high bar`/`Sentadilla high bar`,
`Bp mid grip`/`Banca mid grip`, `Peck deck inverso`/`Reverse peck deck`, los dos curl
bayesian, las dos elevaciones laterales en polea, los tres cruces de poleas, los dos
jalones unilaterales, los dos curl martillo, y las coletillas del entrenador
(`... o la otra`, `... VÍDEO`).

Y dijo que NO son el mismo: `Hip thrust unilateral` (mancuerna) vs `en máquina`, y
`Banca larssen mid grip` vs `Banca mid grip`. Lo que queda por encima del 0,5 de
parecido son variantes de verdad (step down lateral, búlgara en multipower, las plancha
laterales, peck deck normal vs inverso, curl araña vs predicador).

**Al dar de alta una etapa nueva, mirar esto**: el barrido es un rato de script y el
daño es silencioso. Un `itertools.combinations` con Jaccard de palabras sobre
`extract_exercises` saca los candidatos en un minuto.

### 19.7 Pendiente de esto
- **Probar la rueda en el móvil con el dedo.** En el ordenador va con la rueda del ratón
  (y pinchando), que es lo único que se puede probar aquí; el gesto táctil con
  `scroll-snap` no se simula ni se puede pinchar la pestaña "Peso" desde el navegador
  headless.
- `test_entreno.py` (nuevo, en la raíz): `./venv/bin/python test_entreno.py`. Cubre el
  enrutado de Build II, el calentamiento, `0x0` vs `200x0`, las compuestas y los rangos.
