import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import Panel from "./Panel";
import { anim, theme, tooltipStyle } from "./../lib/theme";
import { mean } from "../lib/stats";

// Widget 3.3 — Sueño.
//
// Dos magnitudes distintas apiladas en la misma barra:
//   · la parte sólida son las horas DORMIDAS, que mide el reloj;
//   · la parte difusa de encima es el resto del TIEMPO EN CAMA (del formulario AM),
//     o sea lo que tardas en dormirte más los despertares.
// Su cociente es la eficiencia. Rellenar las horas dormidas con el tiempo en cama
// inflaría el sueño, así que las noches que el reloj no registró salen solo como
// barra difusa: se ve que estuviste en la cama y que no sabemos cuánto dormiste.
export const OBJETIVO_HORAS = 7.5;

export type Row = {
  fecha: string;
  horas: number | null;      // dormidas (reloj)
  cama: number | null;       // en cama (formulario)
  calidad: number | null;    // percibida, formulario AM (1-9)
  score: number | null;      // score del reloj (0-100)
  eficiencia: number | null; // %
};

const fmtDate = (f: string) => f.slice(8, 10) + "/" + f.slice(5, 7);

const COLOR_DORMIDO = theme.accent;
const COLOR_DESPIERTO = "#24506b";
// Dos medidas de LO MISMO desde fuentes distintas: cómo dijo Hugo que durmió y qué dijo
// el reloj. Se pintan en una escala común (0-100) porque lo que interesa es justo cuándo
// discrepan; con dos ejes distintos esa comparación se pierde.
const COLOR_CALIDAD = theme.amber;
const COLOR_SCORE = "#7b61ff";

// Caja de valor para la línea de objetivo (como los umbrales de readiness).
function EtiquetaObjetivo({ viewBox }: { viewBox?: { x: number; y: number; width: number } }) {
  if (!viewBox) return null;
  const w = 36, h = 19;
  const x = viewBox.x + viewBox.width - w - 4; // pegada al extremo derecho
  return (
    <g transform={`translate(${x}, ${viewBox.y - h / 2})`}>
      <rect width={w} height={h} rx={4} fill={theme.good} />
      <text x={w / 2} y={h / 2 + 0.5} textAnchor="middle" dominantBaseline="middle"
            fontSize="12" fontWeight={800} fill="#0a0e1a" fontFamily="Inter, ui-sans-serif, sans-serif">
        {OBJETIVO_HORAS}h
      </text>
    </g>
  );
}

type Punto = Row & {
  despierto: number | null;
  soloCama: number | null;
  calidadPct: number | null;  // la percibida (1-9) llevada a 0-100 para comparar
};

function build(rows: Row[]): Punto[] {
  return rows.map((r) => ({
    ...r,
    despierto: r.horas !== null && r.cama !== null ? Math.max(0, r.cama - r.horas) : null,
    soloCama: r.horas === null && r.cama !== null ? r.cama : null,
    calidadPct: r.calidad !== null ? (r.calidad * 100) / 9 : null,
  }));
}

function Chart({ rows, height, legend = false }: { rows: Row[]; height: number | string; legend?: boolean }) {
  const data = build(rows);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 4, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        <XAxis
          dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 10 }}
          minTickGap={24} stroke={theme.grid} tickLine={false}
        />
        <YAxis
          yAxisId="h" domain={[0, 10]} width={30}
          tick={{ fill: theme.muted, fontSize: 10 }} axisLine={false} tickLine={false}
        />
        <YAxis
          yAxisId="q" orientation="right" domain={[0, 100]} width={28}
          tick={{ fill: theme.muted, fontSize: 10 }} axisLine={false} tickLine={false}
        />
        <Tooltip
          {...tooltipStyle}
          formatter={(v: any, name: string) => {
            const n = Number(v);
            if (name === "Dormido") return [`${n.toFixed(2)} h`, "Dormido"];
            if (name === "En dormirte") return [`${Math.round(n * 60)} min`, "En dormirte"];
            if (name === "En cama (sin medir)") return [`${n.toFixed(2)} h`, "En cama, sueño sin medir"];
            // La percibida se dibuja escalada a 0-100; en el tooltip se devuelve a su
            // escala real, que es la que Hugo rellena en el formulario.
            if (name === "Calidad (tú)") return [`${(n * 9 / 100).toFixed(1)} / 9`, "Calidad (tú)"];
            if (name === "Score (reloj)") return [`${Math.round(n)} / 100`, "Score (reloj)"];
            return [n, name];
          }}
        />
        {legend && <Legend wrapperStyle={{ fontSize: 11 }} />}
        <Bar yAxisId="h" name="Dormido" dataKey="horas" stackId="s" fill={COLOR_DORMIDO} fillOpacity={0.8}
             isAnimationActive={anim.on} animationDuration={anim.msBar} />
        <Bar yAxisId="h" name="En dormirte" dataKey="despierto" stackId="s" fill={COLOR_DESPIERTO}
             radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar} />
        <Bar yAxisId="h" name="En cama (sin medir)" dataKey="soloCama" stackId="s"
             fill={theme.muted} fillOpacity={0.3} radius={[3, 3, 0, 0]}
             isAnimationActive={anim.on} animationDuration={anim.msBar} />
        {/* objetivo: DESPUÉS de las barras para que la línea quede por encima */}
        <ReferenceLine
          yAxisId="h" y={OBJETIVO_HORAS} stroke={theme.good} strokeDasharray="6 4" strokeWidth={2}
          strokeOpacity={0.95} label={<EtiquetaObjetivo />}
        />
        <Line
          yAxisId="q" name="Calidad (tú)" type="monotone" dataKey="calidadPct" stroke={COLOR_CALIDAD}
          strokeWidth={2} dot={{ r: 2, fill: COLOR_CALIDAD }} connectNulls={false}
          isAnimationActive={anim.on} animationDuration={anim.ms}
        />
        <Line
          yAxisId="q" name="Score (reloj)" type="monotone" dataKey="score" stroke={COLOR_SCORE}
          strokeWidth={2.4} dot={false} connectNulls={false}
          isAnimationActive={anim.on} animationDuration={anim.ms}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// Minutos que tardas en dormirte = (en cama − dormido). Técnicamente incluye los
// microdespertares de la noche, pero son breves e inconscientes, así que a efectos
// prácticos es la latencia (lo que tardas en coger el sueño).
const minutosEnDormirse = (rows: Row[]) =>
  rows
    .filter((r) => r.horas !== null && r.cama !== null && r.cama >= r.horas)
    .map((r) => (r.cama! - r.horas!) * 60);

function Resumen({ rows }: { rows: Row[] }) {
  const horas = rows.map((r) => r.horas).filter((v): v is number => v !== null);
  if (horas.length === 0) return null;
  const ok = horas.filter((h) => h >= OBJETIVO_HORAS).length;
  const mins = minutosEnDormirse(rows);
  return (
    <>
      Media {mean(horas).toFixed(1)} h · {ok}/{horas.length} noches ≥ {OBJETIVO_HORAS} h
      {mins.length > 0 && ` · tardas ${Math.round(mean(mins))} min en dormirte de media`}
    </>
  );
}

export default function SleepPanel({ rows, onExpand }: { rows: Row[]; onExpand?: () => void }) {
  const data = rows.slice(-30);
  return (
    <Panel title="Sueño" subtitle={`objetivo ${OBJETIVO_HORAS} h`} onExpand={onExpand}>
      <div style={{ height: 190 }}>
        {data.length === 0 ? (
          <div className="flex h-full items-center" style={{ color: theme.muted }}>—</div>
        ) : (
          <Chart rows={data} height="100%" />
        )}
      </div>
      <div className="mt-1 text-[10px]" style={{ color: theme.muted }}>
        <Resumen rows={data} />
      </div>
    </Panel>
  );
}

export function SleepExpanded({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <div style={{ color: theme.muted }}>Sin datos de sueño en este rango.</div>;
  const sinMedir = rows.filter((r) => r.horas === null && r.cama !== null).length;
  const mins = minutosEnDormirse(rows);
  const peorMin = mins.length ? Math.max(...mins) : null;

  return (
    <div className="flex h-[70vh] flex-col">
      <div className="mb-3 flex flex-wrap gap-x-8 gap-y-2 text-xs" style={{ color: theme.muted }}>
        <span><Resumen rows={rows} /></span>
        {peorMin !== null && (
          <span>Peor noche: <b style={{ color: theme.text }}>{Math.round(peorMin)} min en dormirte</b></span>
        )}
        {sinMedir > 0 && (
          <span>{sinMedir} noche{sinMedir > 1 ? "s" : ""} sin medir por el reloj (solo tiempo en cama)</span>
        )}
      </div>
      <div className="mb-3 text-[11px] leading-relaxed" style={{ color: theme.muted }}>
        La barra sólida son horas dormidas, que mide el reloj. La difusa de encima es lo que
        <b style={{ color: theme.text }}> tardas en dormirte</b>: el rato en la cama antes de coger el sueño
        (en cama menos dormido).{" "}
        Las dos líneas son <b style={{ color: theme.text }}>qué tal</b> dormiste, no cuánto, y vienen de
        sitios distintos: la <b style={{ color: COLOR_CALIDAD }}>ámbar</b> es la calidad que pones tú en el
        formulario de la mañana y la <b style={{ color: COLOR_SCORE }}>violeta</b> el score que calcula el
        reloj. Comparten el eje de la derecha (0-100, tu 1-9 reescalado) justamente para poder
        compararlas: lo interesante es <b style={{ color: theme.text }}>cuándo discrepan</b> — noches en
        las que el reloj puntúa alto y tú te levantaste mal, o al contrario.
      </div>
      <div className="min-h-0 flex-1">
        <Chart rows={rows} height="100%" legend />
      </div>
    </div>
  );
}
