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
- **El modelo local (Ollama, `qwen2.5:3b`) solo vive en el portátil.** El equipo del
  trabajo NO lo ejecuta, así que la config del modelo en `.env` no le hace falta.

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
- **El plan de entreno de Drive mezcla todos los bloques en una hoja**, distinguidos solo
  por el nombre de la pestaña. `entreno_pipeline.PLAN_TAB_RULES` enruta pestaña →
  (bloque, semana). Al empezar un bloque nuevo hay que añadir ahí su patrón, o sus
  sesiones entran sin nombre de ejercicio. Hugo **reinicia la numeración con cada plan**,
  así que el número de bloque debe cuadrar con el que él escribe en el keep, no ser
  correlativo. Hoy: `Semana N`→3 y `Peaking SN`→4 (PLANI 1); `Offseason SN`→1 (PLANI 2,
  su primera etapa). El **plan** lo marca la cabecera `PLANI N` del keep; `parse_keep` lo
  captura en la columna `plani` de `entreno_sets`, y el panel de Fuerza etiqueta el eje
  `P{plani}B{bloque}S{semana}` (P2B1S1) ordenado **por fecha**, no por nº de bloque. Aún
  pendiente: `rm1` agrupa por (bloque, semana) sin plani, así que ahí sí colisionarían dos
  planes con el mismo bloque; hoy no pasa (P1 usa 3/4, P2 usa 1).
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
- **Alturas de panel en px fijos, nunca en %.** `ResponsiveContainer height="100%"` dentro
  de un `flex-1` sin altura definida provoca un bucle de ResizeObserver.
- **Capturas de verificación**: `google-chrome --headless=new --force-prefers-reduced-motion`.
  Sin ese flag las animaciones de Recharts no avanzan y los gráficos salen vacíos.

## Ficheros que NUNCA van al repo

`.env`, `health-boost-*.json`, `keep.txt` y `jarvis.db` (conversaciones privadas). El
histórico de git se publicaría al hacer el repo público.

## Comandos

```bash
./run.sh                    # pipeline + backend (8099) + frontend (5173)
./run.sh --no-pipeline      # solo servir, sin tocar datos
./venv/bin/python status_pipeline.py     # solo actualizar datos
```
