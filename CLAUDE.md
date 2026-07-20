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
- **Al terminar cualquier trabajo: `git commit` + `git push`** (siempre, no acumular).
- **Al cerrar la sesión, avisar a Hugo** de si hay algo **fuera de git** que necesite
  traspaso a mano (pendrive, etc.) para retomar en el otro equipo: `.env`, `keep.txt`,
  `jarvis.db`, `health-boost-*.json`. Precisar cuáles cambiaron y si el otro equipo los
  necesita de verdad.
- **El modelo local (Ollama, `qwen2.5:3b`) solo vive en el portátil.** El equipo del
  trabajo NO lo ejecuta, así que la config del modelo en `.env` no le hace falta.

## Convenciones

- **Código, comentarios, nombres de variables y UI: en español.**
- **Mensajes de commit: en inglés.** El histórico mezcla ambos idiomas, así que mirar
  `git log` para deducirlo lleva a error.
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
  sesiones entran sin nombre de ejercicio. Hoy: `Semana N`→3, `Peaking SN`→4, `Offseason SN`→5.
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
