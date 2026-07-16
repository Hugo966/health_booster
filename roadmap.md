# Roadmap del dashboard de bienestar

Este documento es intencional, no técnico. Los specs detallados se escriben
justo antes de implementar cada fase, no antes, para que reflejen el estado
real del código y lo aprendido.

## Fase 1 — Dashboard core (en curso)
Ver `dashboard_spec_fase1.md`. Objetivo: 7 gráficos fijos, tema oscuro,
lectura de la hoja hub. Sin IA.

## Fase 2 — Chat "Jarvis"
Objetivo: caja de texto en el dashboard donde se hacen preguntas en
lenguaje natural sobre los datos y Claude devuelve un gráfico ad-hoc o
una respuesta razonada.

Preguntas abiertas a resolver **antes** de escribir el spec:
- ¿Qué tipo de preguntas surgen realmente al usar la Fase 1?
- ¿Claude devuelve una spec JSON que se renderiza en el frontend,
  o texto + código Python que se ejecuta en el backend?
- ¿Historial de preguntas persistente o efímero?

## Fase 3 — Automatización del pipeline
Objetivo: que `status_pipeline.py` corra solo cada día (o cada N horas).
Opciones a evaluar cuando toque: GitHub Actions, cron en Hetzner,
Cloud Run Job en GCP. Elección depende de dónde viva mejor el resto
del stack en ese momento.

## Fase 4 — Insights proactivos
Objetivo: que el sistema mande resúmenes/alertas cuando detecte algo
relevante (bajón sostenido de HRV, ACWR en rojo, correlación nueva
significativa, etc.).

## Principio general
Cada fase se planifica cuando la anterior está viva y usada al menos
2 semanas. Antes es prematuro.
