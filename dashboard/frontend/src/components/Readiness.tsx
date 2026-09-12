import { useRef } from "react";
import { anim, panelStyle, readinessBand, theme, tooltipStyle } from "../lib/theme";
import { esFondo, ExpandIcon } from "./Panel";
import {
  Area, AreaChart, CartesianGrid, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

// Caja de color en el eje para un umbral especial (40 rojo, 65 ámbar), además de
// los ticks normales de 25 en 25. Recharts inyecta `viewBox` con la posición.
function CajaUmbral({ viewBox, valor, color }: { viewBox?: { x: number; y: number }; valor: number; color: string }) {
  if (!viewBox) return null;
  const w = 30, h = 19;
  return (
    <g transform={`translate(${viewBox.x + 3}, ${viewBox.y - h / 2})`}>
      <rect width={w} height={h} rx={4} fill={color} />
      <text x={w / 2} y={h / 2 + 0.5} textAnchor="middle" dominantBaseline="middle"
            fontSize="13" fontWeight={800} fill="#0a0e1a"
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif">
        {valor}
      </text>
    </g>
  );
}

// Ticks del eje X a intervalos de días CONSTANTES (no "cada N categorías", que da
// saltos irregulares de 2-3 días). Se ancla en la fecha más reciente y baja de
// `paso` en `paso`, así el último día siempre cae en un tick.
function ticksTemporales(times: number[]): number[] {
  const min = Math.min(...times), max = Math.max(...times);
  const dias = (max - min) / 86400000;
  if (dias <= 0) return [max];
  const cand = [1, 2, 3, 7, 14, 30, 60, 90];
  const paso = cand.find((d) => dias / d <= 8) ?? cand[cand.length - 1];
  const stepMs = paso * 86400000;
  const out: number[] = [];
  for (let t = max; t >= min; t -= stepMs) out.unshift(t);
  return out;
}

const tMs = (fecha: string) => Date.parse(fecha + "T00:00:00");
const fmtT = (t: number) => {
  const d = new Date(t);
  return String(d.getDate()).padStart(2, "0") + "/" + String(d.getMonth() + 1).padStart(2, "0");
};

// Gauge circular (270°, hueco abajo) estilo Iron Man. Pinta el readiness de HOY
// (última fila con valor no nulo) y el delta vs los 7 días ANTERIORES.
type Props = {
  value: number | null;  // readiness de hoy (0-100) o null si no hay dato
  base7: number | null;  // media de los 7 valores previos, sin incluir el de hoy
  fecha: string | null;
  onExpand?: (origin?: DOMRect) => void;
};

const SIZE = 260;
const STROKE = 18;
const R = (SIZE - STROKE) / 2;
const CX = SIZE / 2;
const CY = SIZE / 2;
const GAP_DEG = 90;                  // hueco inferior
const SPAN_DEG = 360 - GAP_DEG;      // arco útil = 270°
const START_DEG = 90 + GAP_DEG / 2;  // empieza abajo-izquierda

function polar(angleDeg: number, r = R) {
  const a = (angleDeg * Math.PI) / 180;
  return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) };
}

// Arco SVG entre dos ángulos (grados, sentido horario en coords pantalla).
function arcPath(fromDeg: number, toDeg: number): string {
  const start = polar(fromDeg);
  const end = polar(toDeg);
  const large = toDeg - fromDeg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${R} ${R} 0 ${large} 1 ${end.x} ${end.y}`;
}

export default function Readiness({ value, base7, fecha, onExpand }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const abrir = () => onExpand?.(ref.current?.getBoundingClientRect());
  const hasData = value !== null;
  const band = hasData ? readinessBand(value) : null;
  const frac = hasData ? Math.max(0, Math.min(1, value / 100)) : 0;
  const valueEndDeg = START_DEG + SPAN_DEG * frac;

  const delta = hasData && base7 !== null ? value - base7 : null;
  const deltaColor =
    delta === null ? theme.muted : delta > 0 ? theme.good : delta < 0 ? theme.alert : theme.muted;

  return (
    <div
      ref={ref}
      className="jarvis-panel group relative flex flex-col items-center justify-center rounded-2xl p-6"
      style={{ ...panelStyle, cursor: onExpand ? "pointer" : undefined }}
      onClick={onExpand && ((e) => esFondo(e) && abrir())}
    >
      {onExpand && (
        <button
          onClick={() => abrir()}
          aria-label="Ampliar Readiness"
          title="Ampliar"
          // Readiness no usa `Panel`, así que lleva su propia copia de este botón — y por
          // tanto llevaba también su propia copia del fallo: sin `hover:none` es
          // invisible en el móvil, porque en táctil no hay hover (ver Panel.tsx).
          className="jarvis-expand absolute right-3 top-3 rounded-md p-1.5 opacity-0 transition group-hover:opacity-100 focus:opacity-100 [@media(hover:none)]:opacity-100"
        >
          <ExpandIcon />
        </button>
      )}

      <div
        className="mb-1 font-display text-[11px] uppercase tracking-[0.4em]"
        style={{ color: theme.muted }}
      >
        Readiness
      </div>

      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE}>
          <path
            d={arcPath(START_DEG, START_DEG + SPAN_DEG)}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          {hasData && (
            <path
              key={value}
              className="jarvis-arc"
              d={arcPath(START_DEG, valueEndDeg)}
              fill="none"
              stroke={band!.color}
              strokeWidth={STROKE}
              strokeLinecap="round"
              pathLength={1}
              style={{ filter: `drop-shadow(0 0 6px ${band!.color})` }}
            />
          )}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div
            className="jarvis-fade font-display leading-none"
            style={{ fontSize: 64, color: hasData ? band!.color : theme.muted }}
          >
            {hasData ? Math.round(value) : "—"}
          </div>
          <div
            className="mt-2 font-display text-lg tracking-[0.35em]"
            style={{ color: hasData ? band!.color : theme.muted }}
          >
            {hasData ? band!.label : "SIN DATOS"}
          </div>
        </div>
      </div>

      <div className="mt-3 text-sm">
        {delta === null ? (
          <span style={{ color: theme.muted }}>—</span>
        ) : (
          <>
            <span style={{ color: deltaColor }}>
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(1)}
            </span>
            <span style={{ color: theme.muted }}> vs los 7 días previos</span>
          </>
        )}
      </div>
      {fecha && (
        <div className="mt-1 text-xs" style={{ color: theme.muted }}>
          {fecha}
        </div>
      )}
    </div>
  );
}

// Vista ampliada: readiness en el tiempo con las bandas de referencia.
export function ReadinessExpanded({ series }: { series: { fecha: string; v: number }[] }) {
  if (series.length === 0)
    return <div style={{ color: theme.muted }}>Sin datos de readiness en este rango.</div>;

  const rows = series.map((s) => ({ t: tMs(s.fecha), readiness: s.v }));
  const times = rows.map((r) => r.t);
  const ticks = ticksTemporales(times);

  // Color de la LÍNEA por tramo: verde ≥65, ámbar 40-65, rojo <40. El gradiente
  // del trazo se mide sobre el recuadro de la propia línea (de su mín a su máx),
  // así que los cortes se calculan con el rango real de los datos; si no, el color
  // no cae en 65/40 sino comprimido. Las FRANJAS de fondo, en cambio, van con
  // <ReferenceArea>, que sí se mapea exacto a los valores del eje.
  const vals = rows.map((r) => r.readiness);
  const hi = Math.max(...vals);
  const lo = Math.min(...vals);
  const span = hi - lo || 1;
  const clamp = (x: number) => Math.max(0, Math.min(1, x));
  const oCaution = clamp((hi - 65) / span);
  const oCooked = clamp((hi - 40) / span);

  return (
    <div className="flex h-[70vh] flex-col">
      <div className="mb-4 text-xs" style={{ color: theme.muted }}>
        Rojo por debajo de 40 (COOKED), ámbar hasta 65 (CAUTION), verde por encima (READY).
      </div>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <defs>
            <linearGradient id="rdStroke" x1="0" y1="0" x2="0" y2="1">
              <stop offset={0} stopColor={theme.good} />
              <stop offset={oCaution} stopColor={theme.good} />
              <stop offset={oCaution} stopColor={theme.amber} />
              <stop offset={oCooked} stopColor={theme.amber} />
              <stop offset={oCooked} stopColor={theme.alert} />
              <stop offset={1} stopColor={theme.alert} />
            </linearGradient>
          </defs>
          {/* franjas de fondo: mapeadas exacto al eje */}
          <ReferenceArea y1={65} y2={100} fill={theme.good} fillOpacity={0.1} strokeOpacity={0} />
          <ReferenceArea y1={40} y2={65} fill={theme.amber} fillOpacity={0.16} strokeOpacity={0} />
          <ReferenceArea y1={0} y2={40} fill={theme.alert} fillOpacity={0.14} strokeOpacity={0} />
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
            ticks={ticks} tickFormatter={fmtT}
            tick={{ fill: theme.muted, fontSize: 11 }} stroke={theme.grid}
          />
          <YAxis
            domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} width={40}
            tick={{ fill: theme.muted, fontSize: 11 }} stroke={theme.grid}
          />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(t) => fmtT(Number(t))}
            formatter={(v: any) => [Math.round(Number(v)), "Readiness"]}
          />
          <Area
            type="monotone"
            dataKey="readiness"
            stroke="url(#rdStroke)"
            strokeWidth={2.5}
            fill="none"
            connectNulls={false}
            isAnimationActive={anim.on} animationDuration={anim.ms}
          />
          {/* umbrales especiales: raya + cajita en el eje */}
          <ReferenceLine y={65} stroke={theme.amber} strokeDasharray="6 4" strokeWidth={2} strokeOpacity={0.85}
            label={<CajaUmbral valor={65} color={theme.amber} />} />
          <ReferenceLine y={40} stroke={theme.alert} strokeDasharray="6 4" strokeWidth={2} strokeOpacity={0.85}
            label={<CajaUmbral valor={40} color={theme.alert} />} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
