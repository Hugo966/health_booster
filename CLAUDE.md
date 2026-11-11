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
- **En el CÓDIGO se habla de "el usuario", no de Hugo** (barrido el 2026-11-11, 209
  menciones). Hugo es el AUTOR —firma los commits y el repo cuelga de su cuenta, y eso se
  queda—, pero la aplicación tiene que poder adoptarla cualquiera: un comentario que dice
  "Hugo apunta el entreno" se lee como que la app es de una persona. En los docs internos
  (HANDOFF, este fichero, `docs/`) sí se le nombra: son notas de desarrollo, no producto.
  Los mensajes de commit van como el código: "the user".
- **El nombre del usuario sale de `JARVIS_USUARIO` (`.env`), no del prompt.** El prompt y
  las descripciones de herramientas llevan un hueco `{usuario}` / `{Usuario}` que rellena
  `personalidad.con_usuario()` al montar el sistema; `chat.py` hace lo mismo con
  `HERRAMIENTAS` y con los prompts del enrutado y de las muletillas. Sin la variable,
  Jarvis dice "el usuario" y funciona igual. Dos formas porque el prompt es prosa, y el
  hueco **nunca va detrás de "de" ni de "a"** ("de el usuario" no existe): esas frases
  están escritas con "su". **El `.env` NO viaja con `./desplegar.sh`**, así que la VM
  necesita su propia línea `JARVIS_USUARIO=` o empezará a llamarle "el usuario".
- Los comentarios explican **por qué**, no qué hace el código.

## Cosas que cuesta redescubrir

- **Backend en el puerto 8099**, no 8000 (lo ocupa otra app). El sandbox de Bash bloquea
  los binds: arrancar servidores con el sandbox desactivado.
- **La carga se mide con sRPE** (RPE de sesión × nº de series, suma de 7 días), no con
  ACWR ni con tonelaje. El ACWR se pegaba a su techo de 4.0 por falta de datos de duración.
- **Las variantes de ejercicio son ejercicios distintos.** Banca competición, banca 3 ct
  y banca mid grip no se fusionan nunca. Pero **el entrenador escribe el MISMO ejercicio
  de varias formas** y eso sí hay que fusionarlo: en octubre de 2026 había 111 nombres
  para 100 ejercicios, y la sentadilla principal de Hugo empezaba de cero al entrar en
  Build II (`tacón 2 cm` → `tacón 2cm`). Van en `ALIAS`, cuya clave pasa por `_key`
  (ignora tildes, mayúsculas y espacios de más). **Al dar de alta una etapa nueva, pasar
  un barrido de parecidos por los nombres del plan** y preguntarle a Hugo los dudosos:
  adivinar es caro en las dos direcciones.
  Segundo caso, el 2026-11-11 y en la misma sentadilla: el entrenador le puso un **tacón
  de 2 cm** en septiembre por un dolor de pie y se lo quitó en Build II S6. Quitarlo NO
  es un ejercicio nuevo, es **volver** al de junio-julio, que estaba apuntado como
  `Sentadilla LB` con un máximo de 170 kg; sin fusionarlos, su sentadilla nacía el 10/11
  en 125 kg y la progresión de vuelta se medía contra un suelo falso. `Sentadilla LB` y
  `sq low bar` apuntan ya a `Sentadilla low bar`, que es como lo escribe el plan HOY (el
  mismo criterio que el sumo). **El del tacón sigue aparte**: ese sí era otro movimiento.
  La pista que lo destapó fue el panorama: dos nombres casi iguales, uno con cinco
  semanas de histórico y el otro con una sola.
- **El plan de entreno de Drive mezcla todas las etapas en una hoja**, distinguidas solo
  por el nombre de la pestaña. `entreno_pipeline.PLAN_TAB_RULES` enruta pestaña →
  **(plani, bloque)**, y el número capturado es la semana. Hugo **reinicia la numeración
  de bloques con cada plan**, así que el número debe cuadrar con el que él escribe en el
  keep, no ser correlativo. Hoy: `Semana N`→(1,3) y `Peaking SN`→(1,4);
  `Offseason SN`→(2,1), `Build SN`→(2,2) y `Build II SN`→(2,3). También se enruta ya el
  formato **`PxBySz`**, aunque todavía no exista ninguna pestaña así.
- **Una etapa NUEVA ya no hace falta darla de alta a mano** (2026-11-11). El entrenador
  bautiza la pestaña como le sale, y el plan y el bloque son números de Hugo que no están
  en ese nombre, así que `rutas_automaticas()` los **deduce**: etapa desconocida = bloque
  siguiente del plan en curso, que es lo que ha pasado en las cinco etapas del histórico
  (Offseason→1, Build→2, Build II→3). La semana es el número final del título, y las
  pestañas de una misma etapa comparten bloque porque la clave pasa por `_etapa()`, que
  normaliza como `_key` (una tilde o un espacio de más no fundan una etapa nueva).
  **Dos frenos**: tiene que acabar en número Y su columna A tiene que traer una cabecera
  `Sesión N`, o "Movilidad 2" entraría como semana de plan. **Y la red**: el bloque es una
  deducción, así que si no cuadra con el `BLOQUE n` del keep el lookup no casa, las series
  entran con `sin_excel` y la luz "Plan (nombres de ejercicio)" de `huecos.py` se pone en
  ámbar ese mismo día. Adivinar sale barato PORQUE el error se ve. Lo que sigue
  necesitando una línea a mano es el NOMBRE de la etapa (`nombre_etapa`): `P2B4S1` enruta
  solo, pero el parte de estado no sabe que eso se llama "Build III".
- **Si el nombre NO acaba en número, no se adivina: lo pregunta Jarvis** (2026-11-11). Sin
  número no hay semana, y la semana decide a qué sesión van los nombres, así que un fallo
  ahí le pone a las series el nombre de otro día sin dar error. Una pestaña que trae
  cabeceras `Sesión N` pero no se puede enrutar se apunta a medias en la pestaña
  **`plan_pestanas`** del hub (`pestana | plani | bloque | semana`), `briefing.py` la mete
  en el parte, Jarvis le pregunta y la completa con la herramienta `enrutar_pestana`
  (`dashboard/backend/plan_pestanas.py`). También se contesta **desde el panel de
  Formularios ampliado**, con las letras P/B/S fijas y **tres ruedas** (las mismas del
  resto del panel), en un bloque que solo aparece si hay alguna pendiente. Existe porque
  dictarle tres números sueltos al reconocedor de voz es justo donde más se equivoca.
  Las ruedas **arrancan ya puestas** en la semana siguiente a la última entrenada
  (`plan_pestanas.sugerencia()`, que lo saca de `entreno_sesion`, o sea de los números
  del keep), así que lo normal es mirar que cuadra y darle a Guardar. **Ojo, aquí la
  sugerencia SÍ se manda sin tocarla**, al revés que el peso: no existe el "no
  contesto", la fila está esperando respuesta y se guarda lo que se ve en pantalla. La
  UI manda el código `P2B4S3` y lo parsea el MISMO `route_tab` del pipeline
  (`POST /plan/enrutar`), para no inventar una sintaxis aparte; los rangos de las ruedas
  los declara el backend (`plan_pestanas.CAMPOS`), como los de los formularios. El
  pipeline lo lee a la hora siguiente: **no hace falta tocar código ni desplegar.** Dos cosas que importan de esa pestaña: es la
  ÚNICA de entrada que lee el backend (va en `sheets.TABS`), y el pipeline solo le hace
  `append_row` — pasarle `write_tab` borraría las respuestas de Hugo, porque esa función
  limpia la pestaña antes de escribir. La respuesta cuenta además como ancla: si dice que
  una es el bloque 4, la siguiente etapa deducida será la 5.
- **El calentamiento del plan NO va al keep, así que no puede ocupar un slot.** Desde
  Build II cada día del Excel empieza con una cabecera `Warm up`, y Hugo no apunta esos
  ejercicios. Si se quedaran en la lista, los nombres se correrían un puesto y la
  sentadilla se llamaría "Tibial raises". `_sin_calentamiento` los quita, y no basta con
  saltarse la sección: el MISMO ejercicio se repite suelto al final de Accesorios (Build
  II S2, sesiones 1 y 3), así que se recoge su nombre bajo la cabecera y se borra donde
  reaparezca en esa sesión. **No se filtra por el prefijo "Warm up"**: hoy lo llevan,
  pero Hugo no garantiza que siga.
- **La notación de tiempo del keep.** `1"` es un segundo y `1'` un minuto. `3x30"` son 3
  series de 30 s. `2x30"-30"@7` es una serie COMPUESTA: el número de delante son las
  **series** (2) y los tramos separados por guion son el trabajo dentro de cada una
  (30 s + descanso + 30 s), no series sueltas; pueden ser más de dos
  (`2x30"-30"-30"-20"`). Los separa del caso normal que **entre series hay espacio y
  aquí no** (`2x7x10RIR0 - 6x10RIR0` son dos series; `2x7-8x10RIR0` es una). En un unilateral (`2x10x7-8RIR0`) las repes se
  promedian (7,5) y el volumen es el de UN LADO: contar los dos lados no sería más
  generoso, sería falso, porque la serie que hace cada brazo es la que se promedió.
  Decidido el 2026-10-14. Las
  duraciones van a la columna `nota` (`30"+30" = 60s`), no a una columna propia: se
  quieren para leerlas, no para graficarlas. Antes se perdían enteras.
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
  sin número). Lo que separa un fallo de un ejercicio que no hizo es EL PESO: `200x0@10`
  es un intento fallado (esfuerzo máximo, flag `fallo`, pesa 10 × FACTOR_FALLO en el
  sRPE), y `0x0` a secas es **que no hizo el ejercicio** (flag `no_hecho`, cero series y
  cero carga). Hasta el 2026-10-13 los dos entraban como `fallo` y un ejercicio que se
  saltó le metía 30 puntos de carga. Son la única señal automática de que una sesión se
  torció, y se agregan por sesión en `n_fallos_total` / `n_sin_intensidad_total` /
  `no_hechos` (esta última con los NOMBRES, que es lo que Jarvis necesita decir).
- **El pipeline reparsea el keep ENTERO cada hora, y está bien así.** Medido el
  2026-10-14: parsear las 806 líneas (1119 series) cuesta **0,07 s**; bajar el keep, 1,5 s;
  y bajar el plan —27 pestañas, una petición cada una— **58,5 s**. Lo caro es hablar con
  Google, no parsear, así que un parseo incremental ahorraría centésimas a cambio de
  llevar estado de qué sesión cambió. Y reescribir las pestañas de cero es justo lo que
  hace que Hugo pueda apuntar el entreno sucio y limpiarlo dos días después: a la hora
  siguiente queda como él lo dejó, sin series fantasma ni PRs inventados. Si algún día
  molestan esos 58 s, lo que hay que tocar es la lectura del plan (`values_batch_get`, una
  petición en vez de 27), no el parser.
- **Intervals llega con retraso, a veces de días, y NO es un fallo.** Si la API devuelve
  filas con los campos a `None`, es que el reloj aún no ha subido; el campo `updated` dice
  cuándo llegó de verdad. Reejecutar el pipeline más tarde lo alinea. No diagnostiques
  "sincronización rota" a partir de una consulta puntual — pasó el 2026-07-20 y era falso.
- **Las escalas de los formularios NO son 1-10.** Lo dice la pestaña "Léeme" de la hoja:
  bipolares (sueño, sensación, ánimo, energía) **1-9** con 5=normal y 9=mejor; unipolares
  (estrés, molestias) **0-9** con 0=nada; alcohol 0-27; `rpd_sesion` 0-10. `readiness`
  divide entre 9, así que un 10 colado en una bipolar da readiness > 100 sin avisar. La
  fuente única es `dashboard/backend/formularios.ESQUEMA`: la UI y las herramientas de
  Jarvis sacan de ahí sus rangos —y desde el 2026-10-13 también el `paso` de la rueda—,
  no los declaran por su cuenta.
- **El alcohol del AM es del día ANTERIOR**, no del día de la fila: el formulario se
  rellena al levantarse. Jarvis llegó a dar por hecho que `alcohol_ayer` era lo de hoy.
  Lo dicen el prompt y la descripción de la herramienta `guardar_am`, no la etiqueta del
  campo: eso había que enseñárselo a JARVIS, y la etiqueta del alcohol se dejó como
  estaba porque Hugo ya sabe de qué día es lo que rellena (2026-10-14).
- **La cafeína se apunta UNA vez, en el PM, el día que se la toma** (`cafeina_hoy_mg` y
  `cafeina_hoy_hora`). Hasta el 2026-11-11 se preguntaba también en el AM como "la de
  ayer" —porque le toca el sueño de esa noche— y era rellenar lo mismo dos veces. El
  alcohol NO se tocó: ese sí se bebe después de las 12 y le pega al día siguiente, así
  que apuntarlo a la mañana siguiente es lo correcto. **`derived_diario.cafeina_ayer_mg`
  sigue existiendo pero ya es DERIVADA**: `status_pipeline.cafeina_de_ayer()` desplaza la
  del PM un día. Desplaza por **fecha natural, no con `shift(1)`**, porque
  `derived_diario` solo tiene los días con datos y un hueco de dos días le colgaría el
  cafeína del martes a la noche del jueves (`hrv_ayer` y `sueno_horas_ayer` sí arrastran ese
  defecto, sin arreglar). La columna del AM se queda en la hoja y hace de respaldo donde
  no hay PM del día anterior, que es todo el histórico. Si se borrara sin reponerla, el
  par "Cafeína ayer × sueño" del panel de Correlaciones se iría degradando a "n insuf"
  sin avisar.
- **"Vacío" y "bórralo" son cosas DISTINTAS, y viajan por separado** (2026-11-11). En
  estos formularios un campo sin rellenar significa "no lo he contestado, deja lo que
  hubiera" —es lo que permite corregir un solo número sin reenviar el día—, así que no
  se puede usar el vacío para borrar: abrir el formulario y guardar vaciaría todo lo no
  rellenado. Por eso `formularios.guardar` lleva un argumento `borrar` con los NOMBRES
  de los campos a vaciar, y la herramienta de Jarvis un `borrar: [...]`. El editor del
  panel lo deduce de `tocados`: tocado y con valor → se guarda; tocado y dejado en blanco
  → se borra; sin tocar → ni se manda. **Si no hay fila de ese día, un borrado no la
  crea**: sería inventarse justo el día que se quiere quitar. Hace falta porque Hugo
  mete a veces el RPE de un día que no entrenó, y un 0 no sirve: un 0 es un entreno que
  existió y salió fatal. Dos cosas sin cubrir: **las ruedas no se pueden vaciar** (peso,
  cafeína) porque siempre tienen un valor, y esto NO toca el keep — `entreno_sesion`
  sale de ahí, así que una sesión fantasma apuntada en el keep hay que borrarla a mano.
- **Los campos con `paso` se pintan como RUEDA** (peso 0,1 kg, cafeína 50 mg), y las
  horas usan `<input type="time">`, que en el móvil abre el reloj nativo. La rueda
  ARRANCA en el último valor registrado (`formularios.sugerencias`), pero esa sugerencia
  **no se guarda si no la toca**: si se mandara sola, abrir el formulario y darle a
  Guardar apuntaría el peso de la semana pasada como la pesada de hoy.
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
- **Jarvis tiene que ver lo MISMO que los paneles, nunca menos** (principio de Hugo,
  2026-11-11). Dos sitios donde no era así, y los dos daban números que le contradecían
  en pantalla: la **carga** (la del parte cierra la ventana HOY y la del panel en el
  último entreno; con días de descanso la primera baja y la segunda no — ahora el parte
  lleva **las dos** y dice cuál es cuál) y el **peso** (el panel enseña cuatro ventanas de
  ritmo —4, 6, 12 pesadas e histórico— y el parte daba una sola, encima sobre días y no
  sobre pesadas: `_ritmos_peso` replica las cuatro). Al tocar un panel, mirar si el parte
  dice lo mismo.
- **`panorama.completo()` es "todo lo que enseñan los paneles" y va SOLO en `refrescar`**
  (fuerza por bloque desde `rm1`, la serie de sesiones del panel de Carga, eficiencia del
  sueño y las 8 correlaciones del heatmap con sus mismos umbrales: 14 pares mínimo,
  |r|≥0,2 para que cuente). Son **~460 tokens**: en el parte de cada mensaje encarecería
  toda conversación normal, y lo que se necesita cuando algo no cuadra no es lo que se
  necesita para charlar. Replica cuentas que viven en el frontend, así que **si se toca un
  panel hay que tocar esto**; cada bloque dice de qué panel sale, y `test_panorama.py`
  fija los umbrales.
- **`refrescar` es la herramienta para ponerse al día a mitad de conversación.** El parte
  se monta al empezar el turno pero `sheets.fetch_all` cachea 5 minutos, así que Hugo
  puede estar viendo en pantalla algo que Jarvis no. La herramienta tira la caché y
  devuelve el parte recién hecho **más el panorama entero**. En el prompt le queda dicho que la use cuando le lleven
  la contraria con un número **en vez de decir "puede ser"**, y que no la llame en cada
  mensaje: cuesta una lectura entera de la hoja.
- **Jarvis sabe cuánto hace que no hablas con él** (`memoria.ultima_visita`), y el parte
  lo dice: *"Última vez que hablasteis: viernes, 11 de septiembre (hace 61 días)"*. El
  registro existía desde siempre —cada mensaje se guarda con su `ts`—, solo que nadie
  preguntaba, y como **el hilo es diario**, al día siguiente está vacío igual que tras un
  mes: desde dentro, volver después de comer y volver tras una semana eran idénticos.
  Se miran solo los mensajes DEL USUARIO (que hablara Jarvis no es que pasara él) y se
  excluye la sesión de hoy (eso ya está en el hilo). **Ojo: `jarvis.db` es de cada
  máquina**, así que cada una cuenta sus propias visitas; la que importa es la de la VM,
  que es donde habla de verdad. **Lo que NO se guarda es el canal**: voz y texto entran
  por el mismo sitio, así que no se puede decir "llevas una semana sin hablarme por voz".
- **Jarvis sabe la HORA, no solo el día, y el hilo va fechado.** Las dos cosas faltaban y
  juntas le hacían ordenar mal la vida del usuario: a las 7:10 de la mañana le despidió
  con un "corre que llegas tarde al alemán" cuando el alemán era por la tarde y a esa
  hora iba al trabajo. El bloque `HOY` lleva ahora la hora (`_ahora_es()`), y
  `memoria.hilo_reciente` deja de tirar el `ts`: `chat.py` le pone `[HH:MM]` delante a
  **sus** mensajes, no a los de Jarvis (marcándolos todos, acaba copiando el formato en
  lo que responde). La regla de que los planes van en orden está en `OPERACION`, sección
  "LA HORA, Y EN QUÉ ORDEN PASAN SUS COSAS".
- **El tiempo sale de Open-Meteo, sin clave, y la ubicación la pregunta la APP** la
  primera vez que se abre (`PedirUbicacion.tsx` → `POST /ubicacion`). Acepta **dirección,
  ciudad o código postal**, las tres, porque cada uno tiene su sitio en la cabeza de una
  forma: eso lo resuelve **Nominatim** (OpenStreetMap, tampoco pide clave) y no el
  geocodificador de Open-Meteo, que solo entiende nombres de sitio. Su política pide
  identificar al cliente por `User-Agent` — va el nombre de la app, **nunca datos de
  nadie**— y máximo una petición por segundo, que sobra para algo que se usa una vez.
  Se guardan **DOS** nombres: `meteo_direccion` con la dirección entera —Hugo la quiere
  para otras cosas que no son el tiempo— y `meteo_lugar` con una etiqueta corta (ciudad y
  país), que es la que se ENSEÑA: si el parte usara la larga, Jarvis diría su calle en
  cada mensaje. También se puede **cambiar luego, desde el botón ⚙ de la cabecera**
  (`Ajustes.tsx`), y no solo la primera vez: una ubicación que solo se puede poner el
  primer día no se puede corregir, y la gente se muda. El aviso de arranque y los ajustes
  comparten la misma casilla (`Ubicacion.tsx`, `CampoUbicacion`). No va en el `.env`
  a propósito: esto lo contesta quien USA la app, no quien la instala, y así vale desde
  el móvil, el portátil y la VM. Se guarda en la pestaña **`ajustes`** (clave/valor) de
  la hoja. `meteo.frase()` mete una línea en el parte y **devuelve `None` si falla o si
  no hay ubicación**: un Jarvis sin saber si llueve sirve, uno mudo no. Caché de 20 min
  porque el parte se monta en CADA mensaje. Hacia fuera solo salen unas coordenadas.
- **Escribir en la hoja gasta cuota de LECTURA.** Cada `ajustes.escribir` son metadatos +
  leer la columna + escribir, así que guardar la ubicación de una en una eran nueve
  peticiones y saltaba el 429. Se escriben todas las claves de una pasada. Y el `except`
  de "la pestaña no existe" tiene que ser **solo** `gspread.WorksheetNotFound`: siendo
  ancho, el 429 se disfrazaba de "no existe" e intentaba crear una pestaña que ya estaba,
  con lo que el log enseñaba el segundo error y no el de verdad (2026-11-11).
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
- **El atajo del enrutado solo vale para ABRIR conversación.** `enrutar()` manda a Haiku el
  mensaje **suelto**, sin hilo; si devuelve `RESPUESTA:`, el turno se cierra y Sonnet no
  llega a verlo. A mitad de un formulario eso produjo "no tengo memoria de mensajes
  anteriores" (falso: el hilo estaba ahí). `main.py` descarta esa respuesta si
  `memoria.conversacion_caliente(sesion)`. Cualquier camino rápido nuevo que responda sin
  ver el hilo tiene que pasar por la misma puerta. Detalle en HANDOFF §18.
- **En el móvil, el reconocedor no solo repite la frase: la CORRIGE.** `…7 estrés` → `…7 es
  3 3`. Por eso `reconstruir()` compara prefijo **parcial** (≈60 %) y se queda con **la
  última versión, no con la más larga**: una corrección suele acortar ("un siete" → "un
  ocho") y la larga guardaría el número viejo en un formulario de salud.
- **La sesión del chat lleva la fecha** (`hugo-YYYY-MM-DD`), en hora **local**: el historial
  se limpia al cambiar de día y el día queda entero. En `jarvis.db` no se borra nada. El
  historial pintado lleva sello de sesión, o aparecen burbujas de ayer sobre un hilo que el
  backend da por vacío.
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
