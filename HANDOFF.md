# Jarvis — Dashboard de bienestar · Handoff de contexto

> Resumen autocontenido para continuar el proyecto en una sesión nueva.
> Usuario: Hugo (powerlifter). Idioma de trabajo: español. Código y comentarios en español.

## 0. LO PRIMERO — pendientes del 2026-09-04 (leer antes de tocar nada)

Escrito en el portátil al cerrar la sesión. Cada punto lleva el porqué, porque el orden
importa y saltárselo tiene consecuencias.

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
Pendiente de Hugo. Lo que ya se sabe (2026-08-21): Intervals **no guarda el HRV**, lo
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
- `components/Expanded.tsx` — overlay ampliado + zoom FLIP (Web Animations API).
- `components/RangeSelector.tsx` — 7D/14D/30D/90D; `inRange`, `rangeStart`, tipo `Range`.
- `lib/api.ts` — `fetchData()`, `num()`, tipo `SheetData`.
- `lib/exercises.ts` — clasificación: `COMPETICION=["Sentadilla LB","Banca comp","Sumo dl"]`,
  `categoria()` (basico/variante/accesorio), `patron()` (grupos musculares por regex EN ORDEN),
  `bloqueSemana`/`bsOrden`.
- `lib/theme.ts` — paleta Jarvis, PALETTE (12 colores), panelStyle, tooltipStyle,
  `anim` (respeta reduced-motion), bandas readiness.
- `lib/stats.ts` — `mean`, percentiles, etc. `lib/goal.ts` — objetivo de peso en localStorage.

## 6. Cambios de esta sesión

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
