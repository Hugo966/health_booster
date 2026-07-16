# Spec — Dashboard "Jarvis" de bienestar (Fase 1)

> Este documento va dirigido a Claude Code. Contiene todo el contexto necesario
> para construir la app sin ambigüedad. Sigue las decisiones ya tomadas;
> no las reabras salvo que haya un bloqueo técnico real.

---

## 0. Contexto rápido

El usuario (Hugo) ya tiene:
- Una hoja de Google (`Health_booster_data`, ID en `.env`) con `derived_diario` y otras pestañas alimentadas por un pipeline Python.
- Un Service Account de Google con acceso de Editor a esa hoja. El JSON está en `~/Documents/health_booster/sa.json` (o donde diga `GOOGLE_SA_JSON` en `.env`).
- `entreno_pipeline.py` y `status_pipeline.py` funcionando en la misma carpeta.
- Familiaridad con Python, Docker, FastAPI, React, GCP.

Este dashboard **solo lee** de la hoja. Nunca escribe. El pipeline es quien escribe.

Fuente única de verdad para los gráficos: la pestaña `derived_diario`.
Esquema de columnas (una fila por fecha):

```
fecha, readiness, sueno_calidad, sensacion_am, animo, estres, energia,
sensacion_global, delta_am_pm, molestias_nivel, cafeina_ayer_mg, alcohol_ayer,
dolor_sesion_zona, hrv_rmssd, fc_reposo, sueno_horas, peso_kg,
volumen_total, mejor_e1rm, sRPE, hrv_ayer, sueno_horas_ayer,
sRPE_7d, sRPE_28d, ACWR
```

Convenciones importantes:
- Escalas 1–9 (bipolares, 9=mejor) y 0–9 (unipolares como estrés/molestias, 0=nada).
- `readiness` es 0–100.
- `ACWR`: verde 0.8–1.3, ámbar 1.3–1.5, rojo >1.5 o <0.8.
- Muchos días tendrán NaN en varias columnas. Gestiona con dignidad, no pintes ceros falsos.

---

## 1. Alcance de la Fase 1

Un solo entregable: **una web local con dashboard fijo**.
Tema oscuro estilo Jarvis (neones azul/cian sobre negro, tipografía tech).
Se abre en el navegador, consulta la hoja al cargar (o cada N min), pinta los gráficos.

**NO incluir en Fase 1**: chat con Claude, generación dinámica de gráficos, autenticación, multi-usuario. Todo eso es Fase 2.

---

## 2. Stack recomendado

**Backend**: FastAPI (Python). Un solo endpoint `/data` que lee la hoja con `gspread` (usando el mismo Service Account que el pipeline) y devuelve JSON.
**Frontend**: React + Recharts + Tailwind. Servido por FastAPI en dev o build estático.
**Cache**: en memoria del backend, TTL 5 min. La hoja se toca poco, no la martilleemos.

Alternativa aceptable si Hugo prefiere menos capas: **Streamlit** todo-en-uno. Pero es menos personalizable estéticamente y el look Jarvis queda más flojo. **Decisión por defecto: FastAPI + React.**

Estructura de carpetas:

```
dashboard/
  backend/
    main.py            # FastAPI + endpoint /data
    sheets.py          # cliente gspread cacheado
    .env               # reutiliza el existente
  frontend/
    src/
      App.tsx
      components/
        Readiness.tsx
        HrvTrend.tsx
        SleepPanel.tsx
        LoadPanel.tsx
        StrengthTrend.tsx
        WeightTrend.tsx
        CorrelationHeatmap.tsx
      lib/
        api.ts         # fetch a /data
        theme.ts       # colores, tipografía
    index.html
    vite.config.ts
  README.md
```

---

## 3. Los 7 gráficos core

Todos con tema oscuro. Fondo `#0a0e1a`. Acento principal cian `#00d4ff`. Rojo alerta `#ff4757`.

### 3.1 Readiness gauge (hero, arriba centrado)

Círculo grande tipo Iron Man, valor de HOY (última fila con `readiness` no nulo).
Bandas de color: rojo <40, ámbar 40–65, verde >65. Al lado, número grande + texto ("Ready", "Cooked", según banda).
Debajo, delta vs media 7d ("+3.2 vs 7d avg").

### 3.2 HRV rMSSD — últimos 60 días

Line chart. Encima, una banda semi-transparente con la media móvil 7d ± 1 desviación (baseline personal).
Puntos individuales del día encima. Si el punto de hoy cae por debajo de la banda → punto rojo.
Eje X: fecha. Eje Y: ms.

### 3.3 Sueño — dual axis

Barras: `sueno_horas` (últimos 30 días). Línea encima: `sueno_calidad` (1–9).
Barra objetivo horizontal a 7h.

### 3.4 Carga (semáforo ACWR + sRPE 7d)

Panel con dos elementos:
- Gauge horizontal del ACWR con las bandas (verde/ámbar/rojo definidas arriba).
- Bar chart de `sRPE` últimos 14 días.

### 3.5 Fuerza — tendencia e1RM básicos

Line chart multi-serie: `mejor_e1rm` a partir de `entreno_sesion` (una serie por ejercicio básico si es viable — hazlo con la pestaña `rm1`, que ya está agregada por semana + ejercicio). Eje X: semana. Eje Y: kg.

### 3.6 Peso — tendencia

Line chart con puntos (uno por pesada). Línea de tendencia (media móvil 4 semanas) encima. Eje Y ajustado al rango real ±2 kg, no desde 0.

### 3.7 Correlaciones — heatmap

Matriz de correlaciones (Spearman preferentemente) entre pares clave:
`sueno_horas_ayer × sensacion_am`, `hrv_ayer × readiness`, `cafeina_ayer_mg × sueno_horas`,
`alcohol_ayer × hrv_rmssd`, `sRPE_7d × readiness`, `ACWR × molestias_nivel`.
Color divergente cian↔rojo. Requiere ≥14 puntos por par; si no hay, escribe "n insuficiente" en la celda.

### Layout

```
+---------------------------------------------------+
|                READINESS (gauge grande)           |
+-------------------+-------------------+-----------+
|      HRV          |     SUEÑO         |  CARGA    |
+-------------------+-------------------+-----------+
|      FUERZA       |     PESO          |  CORREL   |
+-------------------+-------------------+-----------+
```

Grid CSS. Responsive: en pantalla estrecha se apilan.

---

## 4. Backend — detalles

`backend/sheets.py`:

```python
import os, time
from functools import lru_cache
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_client = None
_cache = {"ts": 0, "data": None}

def client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SA_JSON"], scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client

def fetch_all(ttl=300):
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < ttl:
        return _cache["data"]
    sh = client().open_by_key(os.environ["SHEET_ID"])
    data = {}
    for tab in ["derived_diario", "entreno_sesion", "rm1", "peso"]:
        try:
            data[tab] = pd.DataFrame(sh.worksheet(tab).get_all_records()).to_dict(orient="records")
        except Exception:
            data[tab] = []
    _cache.update(ts=now, data=data)
    return data
```

`backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sheets import fetch_all

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/data")
def data():
    return fetch_all()
```

Arranque: `uvicorn main:app --reload --port 8000`.

---

## 5. Frontend — detalles

Vite + React + TypeScript. Tailwind con paleta custom (cian/negro).
`recharts` para todo salvo el heatmap; para el heatmap, `visx` o SVG a mano (matriz 6×6 es trivial).
Tipografía: `Orbitron` para números/títulos, `Inter` para el resto.

`lib/api.ts`:

```ts
export async function fetchData() {
  const r = await fetch("http://localhost:8000/data");
  return r.json();
}
```

Cada componente recibe el slice que necesita, no todo el objeto.

Efecto de "aura" en los widgets:
```css
box-shadow: 0 0 20px rgba(0, 212, 255, 0.15);
border: 1px solid rgba(0, 212, 255, 0.3);
```

Ojo con no pasarse: sutil siempre gana a saturado.

---

## 6. Criterios de aceptación

- `pip install -r requirements.txt && uvicorn main:app` arranca sin error.
- `npm run dev` en `frontend/` sirve la app en localhost.
- La app se abre y en <3s muestra los 7 widgets con datos reales de la hoja.
- Ningún NaN visible en pantalla: se muestra "—" o "sin datos".
- Refrescar la página vuelve a llamar al backend; el backend cachea 5 min.
- Los colores respetan la paleta oscura. El readiness gauge es el elemento más grande y llamativo.
- Con menos de 14 días de datos, el heatmap muestra el mensaje de "n insuficiente" en las celdas donde toque, no un cero.

---

## 7. Fuera de alcance (Fase 2, no hacer ahora)

- Chat con Claude embebido para preguntas ad-hoc.
- Generación dinámica de gráficos desde prompt.
- Persistencia de configuración del usuario.
- Deploy fuera de local (Docker sí es aceptable si es trivial).
- Autenticación.

---

## 8. Notas prácticas

- Los `NaN` de la hoja llegan como string vacío "" tras `get_all_records`. Filtrar antes de graficar.
- `fecha` viene como string ISO `YYYY-MM-DD`. Parsear en el frontend.
- Empezar por el gauge de readiness y el line chart de HRV. Con esos dos vivos, el resto es replicar patrón.
- Priorizar que **funcione feo** antes que el CSS. La estética Jarvis viene al final.
