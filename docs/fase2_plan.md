# Fase 2 — Jarvis: asistente conversacional que maneja el dashboard

## Contexto

La Fase 1 dejó un dashboard que Hugo **mira**. La Fase 2 busca dos cosas a la vez:
alguien con quien **hablar**, y alguien que **maneje la interfaz por él**.

El roadmap original describía "caja de texto → gráfico ad-hoc". Se queda corto. Lo que
Hugo pidió es un asistente con el que se lleva bien: que le diga _"tío estás fuerte,
buenas semanas llevas, ahora toca offseason"_, que gaste bromas y sarcasmo sin que se
los pidan, que **recuerde** (si le cuenta que está leyendo un libro, que pregunte
semanas después) y que además **conduzca el dashboard**: "muéstrame el sueño" y abre el
panel; "hazme una revisión general" y va abriendo paneles, comentando y cerrando; y si
lo que quiere enseñar no se ve en ningún panel, se fabrica un gráfico.

Objetivo de esta fase: chat escrito, con personalidad, memoria y control de la interfaz.
**La voz se añade después**, como capa aparte (decisión de Hugo), para no mezclar "el
personaje no suena bien" con "el micrófono no coge".

## El hallazgo que abarata todo esto

**Los paneles ya son direccionables.** El widget abierto vive en el hash de la URL
(`useWidgetEnHash` en `App.tsx:32`) y hay un listener de `hashchange`. Así que "Jarvis
abre el panel de sueño" es `location.hash = "sueno"`, y el zoom FLIP, el cierre con
Escape y el deep-link ya funcionan gratis. No hay que construir control de UI: existe.

## Decisiones ya tomadas

| Decisión | Elección | Por qué |
|---|---|---|
| Memoria | SQLite local (`jarvis.db`) | Rápido, sin red; la hoja es read-only hoy |
| Acceso a datos | Briefing precocinado + herramientas | Cubre "¿cómo me ves?" y "¿qué tal la banca del martes?" |
| Orden | Conversación y memoria primero, voz después | El tono se itera hablando; la voz es independiente |
| Modelo | Ollama local primero, API detrás de la misma interfaz | Coste cero y datos en casa; cambiar es una env var |
| Señalar | **Resaltado con glow**, no puntero de ratón | Comunica casi lo mismo, encaja con el tema y cuesta una fracción |
| Tour | **Automático pero interrumpible** | Cinematográfico, pero se para en cuanto Hugo escribe |

**Hardware objetivo:** portátil con RTX 3060 + 16 GB RAM (NO el sobremesa, que tiene una
GT 710 inservible). Falta confirmar VRAM con
`nvidia-smi --query-gpu=name,memory.total --format=csv`: 12 GB → 14B; 6 GB → 8B.

## Arquitectura

```
Frontend (React)                    Backend (FastAPI :8099)          Datos
────────────────                    ───────────────────────          ─────
ChatPanel ──POST /chat──────────>  chat.py                    jarvis.db (SQLite)
    │                                ├─ briefing.py ──lee──>  Google Sheet (fetch_all)
    │  <──{texto, acciones[]}──      ├─ memoria.py            jarvis.db
    │                                └─ proveedor.py ──> Ollama | API Anthropic
    ▼
reproductor de acciones
  → location.hash / resaltar / gráfico ad-hoc
```

### Las dos familias de herramientas

Distinción central del diseño, y la razón de que la respuesta no sea solo texto:

- **De lectura** — se ejecutan **en el backend**, devuelven datos al modelo y este sigue
  razonando: `dia(fecha)`, `ejercicio(nombre)`, `recordar(tema, texto)`.
- **De actuación** — el servidor **no puede** ejecutarlas. Se devuelven al navegador como
  una lista de acciones: `abrir_panel(nombre)`, `cerrar_panel()`, `cambiar_rango(dias)`,
  `resaltar(ancla)`, `grafico(spec)`.

Una respuesta es por tanto `{texto, acciones[]}`, y **un tour no es más que una respuesta
con muchas acciones intercaladas con frases**. No hace falta un motor de tours aparte.

## Backend

Hoy `dashboard/backend/` son dos ficheros diminutos (`main.py` 18 líneas, `sheets.py` 56).
Se añaden cinco módulos y se toca `main.py` lo mínimo.

### `proveedor.py` — hacerlo bien desde el principio

Una interfaz, dos implementaciones. Barato ahora, carísimo de retrofitear.

```python
def responder(mensajes: list[dict], herramientas: list[dict]) -> Respuesta
```

- `ProveedorOllama` — `http://localhost:11434/api/chat`
- `ProveedorAnthropic` — SDK `anthropic`, con prompt caching del bloque de sistema

Se elige con `JARVIS_PROVEEDOR=ollama|anthropic`. **Ambos deben normalizar a la misma
forma de respuesta**, incluidas las llamadas a herramientas — es donde más difieren las
dos APIs y es el grueso del módulo.

### `memoria.py` — el corazón de la fase

```sql
CREATE TABLE conversaciones (
  id INTEGER PRIMARY KEY, sesion TEXT, ts TEXT, rol TEXT, texto TEXT
);
CREATE TABLE hechos (
  id INTEGER PRIMARY KEY, tema TEXT, texto TEXT,
  fecha_alta TEXT, ultima_mencion TEXT, veces INTEGER DEFAULT 1
);
```

`conversaciones` es el hilo reciente. `hechos` es lo que lo hace un amigo: _"está leyendo
Shogun, empezó ~20/07/26"_.

Jarvis llama a `recordar(tema, texto)` cuando detecta algo que guardar. **Riesgo: los
modelos pequeños llaman peor a las herramientas**, así que si con Ollama no recuerda nada,
esa es la causa probable, no un bug. Mitigación: un pase de extracción al cerrar la
conversación, releyendo el hilo.

Funciones: `guardar_mensaje`, `hilo_reciente(n)`, `recordar`, `hechos_relevantes()`,
`marcar_mencionado(id)` — la última permite sacar temas que llevan tiempo sin salir.

`jarvis.db` **debe entrar en `.gitignore`**: son conversaciones personales, y el fichero
ya advierte que el histórico se publica al abrir el repo.

### `briefing.py` — el parte de estado

Convierte la hoja en algo que el modelo entiende. Reutiliza `sheets.fetch_all()` tal cual.

```
Readiness 71 (↗ +6 vs semana pasada)
HRV 68 ms, dentro de su rango normal
Sueño 6.9 h media 7d — por debajo de su objetivo de 7.5
Peso 84.2 kg, +0.3 kg/semana
Bloque 5 (offseason) S1 — acaba de terminar peaking
```

**Duplicación asumida:** la lógica de tendencias existe en TypeScript (`lib/stats.ts`,
`readinessBand` en `theme.ts`) y aquí se reescribe en Python. Unificarla obligaría a mover
cálculos al backend y rehacer los 7 paneles. **Los umbrales sí deben coincidir** con
`readinessBand` (<40 COOKED, 40-65 CAUTION, >65 READY) o Jarvis contradirá la pantalla.

### `personalidad.py` — el prompt de sistema

Módulo propio, no una constante escondida: es lo que más se va a iterar. Describe el
personaje (cercano, sarcástico, tutea, bromea sin que se lo pidan) y —más importante—
**cuándo NO hacer el gracioso**: si Hugo dice que está jodido, lesionado o desanimado, el
sarcasmo se apaga. Es el fallo típico de estos personajes y hay que escribirlo explícito.

Incluye contexto de dominio (powerlifter, bloques, los 3 básicos) y **el catálogo de
paneles**, para que sepa que "sueño" es un panel que puede abrir.

### `chat.py` + endpoint

`POST /chat` con `{sesion, mensaje}` → `{texto, acciones[]}`. Orquesta: briefing + memoria
+ hilo → proveedor → ejecuta las herramientas de lectura → devuelve texto y acciones.

**Sin streaming en la v1.** Si al usarlo se siente lento, se añade SSE después.

## Frontend

Sigue el patrón existente: compacto + `Expanded`, como los 7 paneles.

- **`components/ChatPanel.tsx`** — `ChatPanel` (compacto) y `ChatExpanded` (conversación
  completa). Reutiliza `Panel`, `panelStyle` y la clase **`.jarvis-input`** que ya existe
  con borde cian y glow al enfocar.
- **`lib/acciones.ts`** — el reproductor. Recibe `acciones[]` y las ejecuta en orden con
  sus pausas. **Interrumpible**: mantiene un `AbortController`; escribir en el input o
  mandar mensaje lo aborta y deja la UI en un estado limpio (sin resaltados colgando,
  sin panel a medio abrir). Esta cancelación es la parte con más aristas del frontend.
- **`components/GraficoAdHoc.tsx`** — traduce una spec JSON a Recharts. Esquema pequeño
  y cerrado: `{tipo: "linea"|"barra", titulo, unidad, puntos: [{x, y}], referencia?}`.
  Cerrado a propósito: cuanto más libre, más se lo inventa el modelo.
- **`lib/chat.ts`** — `enviarMensaje()` reutilizando `API_BASE` de `lib/api.ts`.
  Historial en `localStorage`, patrón de `lib/goal.ts`.
- **Resaltado** — atributos `data-jarvis="..."` en las zonas señalables (el objetivo de
  sueño, la banda de readiness…) y una clase CSS con glow cian en `index.css`. Se aplican
  por `querySelector`, así que **no hay que reescribir los paneles**, solo marcar puntos.
  Se van añadiendo según hagan falta, no los 7 de golpe.
- **`App.tsx`** — cuatro puntos de contacto: tipo `Widget`, `TITULOS`, render en el grid,
  y el caso en `<Expanded>`. El estado del chat vive en `App` (como `objetivo`) para que
  compacto y expandido compartan conversación.

**Dos trampas del código existente:**
1. `Panel` abre la tarjeta al clicar el fondo. El contenedor del chat necesita
   `data-no-expand` (ver `WeightTrend.tsx:146`), o escribir abrirá el overlay.
2. `Expanded` es `overflow-y-auto`; la lista de mensajes con scroll propio necesita
   `min-h-0`, como hacen los gráficos.

No hay librería de markdown. La v1 renderiza texto plano con saltos de línea.

## Orden de trabajo

0. **Paso previo (Hugo):** confirmar VRAM, instalar Ollama, bajar modelo (14B si 12 GB,
   8B si 6 GB). Verificar que hace tool-calling con una llamada suelta.
1. `proveedor.py` + `personalidad.py`. Hito: Jarvis contesta con carácter.
2. `memoria.py` + `recordar`. Hito: le cuentas lo del libro, cierras, vuelves, lo recuerda.
   **Este es el hito que define la fase.**
3. `briefing.py`. Hito: "¿cómo me ves?" responde con tus números reales.
4. Frontend: `ChatPanel` + `ChatExpanded` + wiring en `App.tsx`. Hito: conversación por pantalla.
5. Acciones de UI + reproductor interrumpible. Hito: "muéstrame el sueño" abre el panel.
6. Tour: "hazme una revisión general". Hito: recorre paneles y se para si escribes.
7. Resaltado y `GraficoAdHoc`.
8. Iterar el personaje. Comparar Ollama vs Anthropic cambiando la env var.

Los pasos 1-4 son el asistente; 5-7 son el control del dashboard. **Si el paso 1 revela
que el modelo local no da el tono, conviene resolver eso antes de seguir.**

## Verificación

- **Memoria (lo crítico):** contarle un hecho, matar el backend, relanzarlo, preguntar.
  Debe recordarlo. Confirmar la fila en `jarvis.db` con `sqlite3`.
- **Coherencia con el dashboard:** preguntarle el readiness y contrastar con el panel. Si
  discrepan, los umbrales del briefing no coinciden con `readinessBand`.
- **Tono:** una charla normal (debe bromear solo) y una donde Hugo diga que está jodido
  (no debe bromear). Es el fallo más probable del personaje.
- **Interrupción del tour:** lanzar la revisión general y escribir a mitad. Debe parar sin
  dejar resaltados pegados ni paneles a medias.
- **Intercambiabilidad:** la misma conversación con `JARVIS_PROVEEDOR=ollama` y con
  `anthropic`, herramientas incluidas.
- **UI:** escribir no debe abrir el overlay; `/#chat` enlazable; con `prefers-reduced-motion`
  todo debe seguir funcionando (el tour también).

## Riesgos

1. **El modelo local no da el tono.** Riesgo principal, y por eso el proveedor es
   intercambiable desde el minuto uno. Se sabe en el paso 1.
2. **Demasiadas herramientas para un modelo pequeño.** El control de UI ha subido el
   catálogo a ~8 herramientas, y los modelos de 8-14B se degradan justo ahí: eligen mal o
   se inventan argumentos. Es la consecuencia directa de ampliar el alcance, y refuerza
   el riesgo 1. Si pasa, la salida es agrupar herramientas o mover el control de UI a un
   formato más simple que el tool-calling.
3. **El prompt crece sin control** al acumularse hechos. Por eso `hechos_relevantes()`
   selecciona en vez de volcar. Vigilar con decenas de hechos.
4. **Cancelación del tour**, que es donde suelen quedarse estados a medias en la UI.
5. **Privacidad:** con el proveedor Anthropic las conversaciones de salud salen de casa;
   con Ollama no. Decisión consciente, pero conviene recordarla al cambiar la env var.
