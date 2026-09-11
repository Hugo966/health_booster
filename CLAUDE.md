# Contexto para Claude Code

Proyecto personal de Hugo (powerlifter): dashboard de bienestar "Jarvis" que consolida
datos de salud y entreno. Trabajamos en español.

## Dónde está cada cosa

- **`HANDOFF.md`** — estado completo del proyecto: arquitectura, decisiones y por qué,
  ficheros importantes, problemas conocidos. **Léelo antes de tocar nada.**
- **`docs/fase2_plan.md`** — el plan aprobado de la Fase 2 (chat Jarvis), con el orden
  de trabajo y qué está hecho.
- **`roadmap.md`** — las 4 fases y el principio de no adelantarse.

## Dos equipos de desarrollo (importante)

El proyecto se desarrolla en **dos máquinas**: el portátil de Hugo (RTX 3060 Laptop) y
un segundo equipo, cada una con su propia sesión de Claude Code. El git es el
canal de sincronización, así que:

- **Al empezar la sesión: `git pull`** antes de tocar nada.
- **Commit + push al CERRAR la sesión, no cada cambio suelto.** Hugo prefiere agrupar
  el trabajo de la sesión en vez de un commit por cada cosa. Pero nunca cerrar (ni
  cambiar de máquina) sin pushear: lo que no está en `origin/main` no le llega al otro equipo.
- **Al cerrar la sesión, avisar a Hugo** de si hay algo **fuera de git** que necesite
  traspaso a mano (pendrive, etc.) para retomar en el otro equipo: `.env`, `keep.txt`,
  `jarvis.db`, `health-boost-*.json`. Precisar cuáles cambiaron y si el otro equipo los
  necesita de verdad.
- **El modelo local (Ollama, `qwen2.5:3b`) solo vive en el portátil.** El segundo equipo NO lo ejecuta, así que la config del modelo en `.env` no le hace falta.

## Convenciones

- **Código, comentarios, nombres de variables y UI: en español.** Decisión firme de Hugo
  (2026-08-15): es su herramienta y la personalidad de Jarvis vive en español. No hay que
  volver a plantearlo.
- **Mensajes de commit: en inglés.** El histórico mezcla ambos idiomas, así que mirar
  `git log` para deducirlo lleva a error.
- **El `README.md` va en INGLÉS.** Es la carta de presentación: Hugo quiere que lo lean
  empresas que trabajan en inglés. El resto de documentación (HANDOFF, roadmap, `docs/`)
  es interna y se queda en español. Al terminar algo grande, contarlo en el README **con
  las cifras medidas** — es lo que de verdad se lee.
- Los comentarios explican **por qué**, no qué hace el código.

## Cosas que cuesta redescubrir

- **Backend en el puerto 8099**, no 8000 (lo ocupa otra app). El sandbox de Bash bloquea
  los binds: arrancar servidores con el sandbox desactivado.
- **La carga se mide con sRPE** (RPE de sesión × nº de series, suma de 7 días), no con
  ACWR ni con tonelaje. El ACWR se pegaba a su techo de 4.0 por falta de datos de duración.
- **Las variantes de ejercicio son ejercicios distintos.** Banca competición, banca 3 ct
  y banca mid grip no se fusionan nunca.
- **El plan de entreno de Drive mezcla todas las etapas en una hoja**, distinguidas solo
  por el nombre de la pestaña. `entreno_pipeline.PLAN_TAB_RULES` enruta pestaña →
  **(plani, bloque)**, y el número capturado es la semana. Al empezar una etapa nueva hay
  que añadir ahí su patrón, o sus sesiones entran sin nombre de ejercicio. Hugo
  **reinicia la numeración de bloques con cada plan**, así que el número debe cuadrar con
  el que él escribe en el keep, no ser correlativo. Hoy: `Semana N`→(1,3) y
  `Peaking SN`→(1,4); `Offseason SN`→(2,1) y `Build SN`→(2,2). También se enruta ya el
  formato **`PxBySz`** que Hugo quiere usar cuando migre el plan a una hoja propia,
  aunque todavía no exista ninguna pestaña así.
- **La clave del lookup lleva el PLAN, no solo el bloque, y no es opcional.** Indexando
  solo por bloque, PLANI 1 bloque 1 cogía los nombres de las pestañas Offseason (que son
  de PLANI 2): 313 series mal etiquetadas y **21 de 67 ejercicios con una "mejor marca"
  imposible** —plancha copenhague a 101 kg, banca de 178 cuando la real son 101,8—.
  Arreglado el 2026-09-09. Esas series no tienen fecha, así que nunca llegaron a
  `derived_diario`; el daño estaba en `entreno_sets`, o sea en el panel de Fuerza y en la
  herramienta `ejercicio` de Jarvis. `build_rm1` ya agrupaba con `plani`, ahí no había
  colisión.
- **El plan** lo marca la cabecera `PLANI N` del keep; `parse_keep` lo captura en la
  columna `plani` de `entreno_sets`, y el panel de Fuerza etiqueta el eje
  `P{plani}B{bloque}S{semana}` (P2B1S1) ordenado **por fecha**, no por nº de bloque.
- **El dolor de una sesión vive en DOS columnas, y la del keep es solo un borrador.**
  Hugo escribe `Dolores sesión: ...` en el keep al acabar de entrenar y **más tarde copia
  ese mismo texto** al campo "dolor de entreno" del **formulario PM**. De ahí salen
  `dolor_sesion_keep` (keep, vía `parse_keep`) y `dolor_sesion_nota` (form) con el mismo
  párrafo. La fuente buena es **la del formulario**; la del keep solo cubre la ventana
  entre entrenar y rellenarlo. Nunca pasarle las dos a Jarvis a la vez: vería el dolor
  duplicado y lo leería como dos episodios. `briefing.py` incluye el `_keep` solo si ese
  día falta el del form; cualquier consumidor nuevo (panel, herramienta de chat,
  anomalías) debe hacer lo mismo.
- **`@?` y `RIR?` en el keep no son errores de tecleo.** Significan que Hugo **no pudo
  valorar el esfuerzo** de esa serie: lesión, dolor o ir contra el reloj. El peso y las
  repes son reales (suman volumen y fatiga), pero el esfuerzo no se conoce, así que la
  serie **no genera e1RM** y por tanto no puede optar a un PR. Llevan flag propio
  `sin_intensidad`, distinto de `int_no_parseable` (esa sí es basura: `RIRmario`, un `RIR`
  sin número). `0x0` es una serie fallada o no hecha -> flag `fallo`. Los tres son la
  única señal automática de que una sesión se torció, y se agregan por sesión en
  `n_fallos_total` / `n_sin_intensidad_total`.
- **Intervals llega con retraso, a veces de días, y NO es un fallo.** Si la API devuelve
  filas con los campos a `None`, es que el reloj aún no ha subido; el campo `updated` dice
  cuándo llegó de verdad. Reejecutar el pipeline más tarde lo alinea. No diagnostiques
  "sincronización rota" a partir de una consulta puntual — pasó el 2026-07-20 y era falso.
- **Las escalas de los formularios NO son 1-10.** Lo dice la pestaña "Léeme" de la hoja:
  bipolares (sueño, sensación, ánimo, energía) **1-9** con 5=normal y 9=mejor; unipolares
  (estrés, molestias) **0-9** con 0=nada; alcohol 0-27; `rpd_sesion` 0-10. `readiness`
  divide entre 9, así que un 10 colado en una bipolar da readiness > 100 sin avisar. La
  fuente única es `dashboard/backend/formularios.ESQUEMA`: la UI y las herramientas de
  Jarvis sacan de ahí sus rangos, no los declaran por su cuenta.
- **El backend YA escribe en `wellness_am` / `wellness_pm` / `peso`** (`formularios.py`),
  aunque el docstring de `status_pipeline.py` diga "NUNCA toca": eso sigue siendo cierto
  *para el pipeline*. La escritura es un **upsert por fecha** —Hugo corrige lo que ya
  metió— y edita la ÚLTIMA fila que coincida, que es la que gana en `consolidate()`.
  Ya hay fechas duplicadas de antes (`wellness_am` 2026-06-25 y 2026-08-04, `peso`
  2026-08-11), así que esa regla no es teórica.
- **En la hoja, `fecha` y las horas son valores numéricos, no texto** (46258 = 2026-08-24,
  0.9722 = 23:20): se ven bien por el formato de la columna. Por eso se escriben con
  `USER_ENTERED`. El texto libre va aparte con `RAW`, o una nota que empiece por `=` se
  convertiría en fórmula.
- **Los huecos se detectan contra las pestañas ORIGEN, nunca contra `derived_diario`**
  (`huecos.py`): esa tabla solo la regenera el pipeline y no tiene fila para los días
  vacíos, que son justo los que hay que encontrar. Por leer de `derived_diario`,
  `briefing.py` reclamaba RPEs que Hugo ya había rellenado.
- **`rpd_sesion` del form PM es la señal fiable de "ese día entrenó".** Hugo lo rellena
  cuando ha entrenado y lo deja vacío cuando no, así que no depende de que haya volcado el
  keep ni de en qué máquina esté. Comparado con `entreno_sesion` (que sí sale del keep)
  da los días que le falta escribir. Verificado el 2026-08-24: los 33 días con RPE puesto
  estaban todos en el keep, y ningún día del keep posterior a junio se quedaba sin RPE.
- **`entreno_sesion` (hoja) y `keep.txt` (local) se desincronizan entre las dos máquinas.**
  El keep no va por git: si se vuelca en un equipo y se corre el pipeline, la hoja se
  adelanta y el keep del otro equipo se queda atrás. Pasó el 2026-08-24: la hoja tenía
  sesiones hasta el 20/08 y el keep del otro equipo se quedaba en el 17/08. Por eso la luz de
  entreno de `huecos.py` compara las dos y distingue "falta traer el keep" de "no ha
  entrenado" — decir lo segundo cuando entrenó anteayer es peor que no decir nada.
- **El prompt de Jarvis son DOS constantes** (`personalidad.py`): `PERSONAJE` (quién es:
  tono, voz, cuándo deja de bromear) y `OPERACION` (el manual: herramientas, vocabulario,
  formularios). Se separaron el 2026-09-11 porque el bloque único había crecido a nueve
  secciones de las que solo tres iban del personaje. **No volver a mezclarlas**: iterar el
  tono no debe arriesgar el manejo de herramientas.
- **En el prompt solo va lo PERMANENTE.** Lo que caduca —en qué bloque entrena, qué le
  duele, qué le pasó ayer— sale de los datos o de la memoria. `QUÉ SABES DE ÉL` llevaba
  desde julio diciendo "entra en offseason" y Jarvis lo afirmaba en septiembre estando en
  Build. La etapa la resuelve `entreno_pipeline.nombre_etapa(plani, bloque)` desde la 4ª
  columna de `PLAN_TAB_RULES`, y llega por el parte de estado.
- **Al tocar `personalidad.py` hay que reiniciar el backend** (`systemctl restart jarvis`
  en la VM): el prompt se lee al importar, no en cada mensaje.
- **Alturas de panel en px fijos, nunca en %.** `ResponsiveContainer height="100%"` dentro
  de un `flex-1` sin altura definida provoca un bucle de ResizeObserver.
- **Capturas de verificación**: `google-chrome --headless=new --force-prefers-reduced-motion`.
  Sin ese flag las animaciones de Recharts no avanzan y los gráficos salen vacíos.

## Antes de hacer el repo público

Ver **`docs/publicar_repo.md`**: el histórico entero se publica, así que la limpieza va en
una sola pasada antes de publicar. Dos reglas: nada de datos personales en ficheros
trackeados, y **no decir cuáles son los dos equipos** (que hay dos y se sincronizan por git
sí es información necesaria). El árbol de trabajo ya está neutralizado; el histórico se
arregla con la receta de `filter-repo` de ese documento.

## Ficheros que NUNCA van al repo

`.env`, `health-boost-*.json`, `keep.txt` y `jarvis.db` (conversaciones privadas). El
histórico de git se publicaría al hacer el repo público.

## Comandos

```bash
./run.sh                    # pipeline + backend (8099) + frontend (5173)
./run.sh --no-pipeline      # solo servir, sin tocar datos
./venv/bin/python status_pipeline.py     # solo actualizar datos
```
