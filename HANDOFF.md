# Jarvis — Dashboard de bienestar · Handoff de contexto

> Resumen autocontenido para continuar el proyecto en una sesión nueva.
> Usuario: Hugo (powerlifter). Idioma de trabajo: español. Código y comentarios en español.

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
- **Puertos**: backend `8099`, frontend `5173` (Vite).
- **`.env` (raíz)** — claves: `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`, `GOOGLE_SA_JSON`,
  `SHEET_ID`, `KEEP_TXT`, `DRIVE_EXCEL_ID`. Opcionales del pipeline:
  `INTERVALS_REINTENTOS` (def. 3), `INTERVALS_ESPERA_S` (def. 8).
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
- `dashboard/backend/proveedor.py` — Ollama y Anthropic tras una interfaz común; se cambia
  con `JARVIS_PROVEEDOR` en `.env`. Normalización probada; Ollama **sin probar de verdad**.

**Siguiente, por orden:**
1. `chat.py` + `POST /chat` con las herramientas (`dia`, `ejercicio`, `recordar`) y las
   acciones de UI (`abrir_panel`, `resaltar`, `grafico`). Se puede montar y verificar con
   un **proveedor de mentira** que devuelva respuestas fijas, sin modelo detrás.
2. `ChatPanel` / `ChatExpanded` + enganche en `App.tsx` (4 puntos de contacto).
3. Reproductor de acciones interrumpible + tour.
4. **En el portátil (RTX 3060 Laptop, 6 GB):** instalar Ollama, `ollama pull qwen2.5:7b`,
   y comprobar si el modelo local da el tono. **Es la decisión que condiciona el resto**;
   si no lo da, se cambia `JARVIS_PROVEEDOR=anthropic` y se compara.

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
- Memoria persistente del proyecto (en `~/.claude/.../memory/`): variantes distintas, estado
  Fase 1, plan de entreno en Drive ("Peaking SN" = bloque 4), sueño cama≠dormido, backlog post-v1.
