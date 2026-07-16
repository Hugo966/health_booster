import type { ReactNode } from "react";
import {
  CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import Panel from "./Panel";
import { anim, theme, tooltipStyle } from "./../lib/theme";
import { movingAverage } from "./../lib/stats";
import { colorDelta, type Objetivo } from "../lib/goal";

// Widget 3.6 — Peso: puntos de cada pesada + línea de tendencia (media móvil de 4).
// Las pesadas son ~semanales, así que la métrica que importa es el RITMO (kg/sem),
// no el cambio bruto "en el rango" (que cambia de escala según mires 7D o 90D).
// El color del ritmo depende de si vas hacia donde QUIERES ir, no de si sube o baja.
type Row = { fecha: string; peso: number };

const TREND_WIN = 4;   // ~1 mes (pesadas semanales): la tendencia principal
const TREND_WIN2 = 6;  // ~1 mes y medio, atenuada
const TREND_WIN3 = 12; // ~3 meses, más atenuada
const fmtDate = (f: string) => f.slice(8, 10) + "/" + f.slice(5, 7);

// Color de etiquetas HUD (más claro que theme.muted, que sobre el tile oscuro se perdía).
const HUD_LABEL = "#b4c2d6";

const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"] as const;
const diaSemana = (f: string) => {
  const [y, m, d] = f.split("-").map(Number);
  return DIAS[new Date(y, m - 1, d).getDay()];
};

function build(rows: Row[]) {
  const peso = rows.map((r) => r.peso);
  const t4 = movingAverage(peso, TREND_WIN);
  const t6 = movingAverage(peso, TREND_WIN2);
  const t12 = movingAverage(peso, TREND_WIN3);
  return rows.map((r, i) => ({ ...r, tendencia: t4[i], tendencia6: t6[i], tendencia12: t12[i] }));
}

/** Ritmo en kg/semana = pendiente por mínimos cuadrados sobre las pesadas dadas, ×7 días.
 *  Se le pasa una ventana (últimas 4/6/12 pesadas) para estimar el ritmo a corto/medio/largo. */
function ritmoSemanal(rows: Row[]): number | null {
  if (rows.length < 2) return null;
  const t0 = Date.parse(rows[0].fecha);
  const xs = rows.map((r) => (Date.parse(r.fecha) - t0) / 86400000); // días desde la 1ª
  const ys = rows.map((r) => r.peso);
  const n = rows.length;
  const mx = xs.reduce((s, x) => s + x, 0) / n;
  const my = ys.reduce((s, y) => s + y, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my);
    den += (xs[i] - mx) ** 2;
  }
  return den === 0 ? null : (num / den) * 7;
}

/** Tooltip: día de semana + pesada + tendencia + cuánto se desvía la pesada de la
 *  tendencia (un día de "peso alto por agua/comida" se ve sin confundirlo con subir). */
function TooltipPeso({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const peso = payload.find((p: any) => p.dataKey === "peso")?.value as number | undefined;
  const tend = payload.find((p: any) => p.dataKey === "tendencia")?.value as number | undefined;
  const desv = peso != null && tend != null ? peso - tend : null;
  return (
    <div style={{ ...tooltipStyle.contentStyle, padding: "6px 10px" }}>
      <div style={{ ...tooltipStyle.labelStyle }}>
        {fmtDate(label)} · {diaSemana(label)}
      </div>
      {peso != null && <div style={{ color: theme.text }}>Pesada: {peso.toFixed(1)} kg</div>}
      {tend != null && <div style={{ color: theme.accent }}>Tendencia: {tend.toFixed(1)} kg</div>}
      {desv != null && Math.abs(desv) >= 0.05 && (
        <div style={{ color: theme.muted, marginTop: 2 }}>
          {desv >= 0 ? "+" : "−"}{Math.abs(desv).toFixed(1)} kg vs tendencia
        </div>
      )}
    </div>
  );
}

/** Punto de pesada coloreado según esté por encima/debajo de la tendencia, respetando
 *  la dirección deseada: al subir, encima = verde (bien) y debajo = rojo; al bajar, al revés.
 *  Justo sobre la media móvil (±0.05 kg) = amarillo (ni bien ni mal, "en la línea"). */
function DotPeso(props: any) {
  const { cx, cy, payload, direccion } = props;
  if (cx == null || cy == null) return null;
  const fill = payload?.tendencia == null
    ? theme.amber
    : colorDelta(payload.peso - payload.tendencia, direccion, theme.good, theme.alert, theme.amber);
  return <circle cx={cx} cy={cy} r={2.6} fill={fill} stroke="none" />;
}

function Chart({ rows, objetivo, height }: { rows: Row[]; objetivo: Objetivo; height: number | string }) {
  const data = build(rows);
  const vals = rows.map((r) => r.peso);
  const lo = Math.min(...vals, objetivo.meta ?? Infinity);
  const hi = Math.max(...vals, objetivo.meta ?? -Infinity);
  // Dominio con holgura (±1 kg): a Hugo le lee mejor la tendencia con aire; apretarlo
  // a los datos exageraba los vaivenes semanales y hacía la subida parecer más brusca.
  const dLo = Math.floor(lo - 1);
  const dHi = Math.ceil(hi + 1);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        <XAxis
          dataKey="fecha" tickFormatter={fmtDate} minTickGap={28}
          tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid}
        />
        <YAxis
          width={38} domain={[dLo, dHi]} allowDecimals={false}
          tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid}
        />
        <Tooltip {...tooltipStyle} content={<TooltipPeso />} />
        {objetivo.meta !== null && (
          <ReferenceLine
            y={objetivo.meta} stroke={theme.good} strokeDasharray="5 4" strokeOpacity={0.8}
            label={{ value: `meta ${objetivo.meta}`, position: "insideTopRight", fill: theme.good, fontSize: 9 }}
          />
        )}
        {/* Medias móviles largas, tenues y detrás: dan el rumbo de fondo sin robar
            protagonismo a la principal (MA de 4). */}
        <Line
          type="monotone" dataKey="tendencia12" stroke={theme.accent} strokeWidth={1.2}
          strokeOpacity={0.2} dot={false} connectNulls isAnimationActive={false}
        />
        <Line
          type="monotone" dataKey="tendencia6" stroke={theme.accent} strokeWidth={1.5}
          strokeOpacity={0.38} dot={false} connectNulls isAnimationActive={false}
        />
        <Line
          dataKey="peso" stroke="none" strokeWidth={0} isAnimationActive={false}
          dot={<DotPeso direccion={objetivo.direccion} />} activeDot={{ r: 5 }}
        />
        <Line
          type="monotone" dataKey="tendencia" stroke={theme.accent} strokeWidth={2.2}
          dot={false} connectNulls isAnimationActive={anim.on} animationDuration={anim.ms}
          style={{ filter: "drop-shadow(0 0 5px rgba(0,212,255,0.4))" }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function Controles({ objetivo, onChange }: { objetivo: Objetivo; onChange: (o: Objetivo) => void }) {
  return (
    // data-no-expand: pinchar aquí ajusta el objetivo, no amplía la tarjeta.
    <div data-no-expand className="flex w-fit items-center gap-3 text-[11px]" style={{ color: theme.muted, cursor: "default" }}>
      <div className="inline-flex rounded-md p-0.5" style={{ border: "1px solid rgba(0,212,255,0.16)" }}>
        {(["subir", "bajar"] as const).map((d) => (
          <button
            key={d}
            onClick={() => onChange({ ...objetivo, direccion: d })}
            className="jarvis-seg text-[10px]"
            style={{
              color: objetivo.direccion === d ? theme.bg : theme.muted,
              background: objetivo.direccion === d ? theme.accent : "transparent",
            }}
          >
            {d === "subir" ? "SUBIR" : "BAJAR"}
          </button>
        ))}
      </div>
      <label className="flex items-center gap-1.5">
        meta
        <input
          type="number" step="0.5" placeholder="—"
          value={objetivo.meta ?? ""}
          onChange={(e) =>
            onChange({ ...objetivo, meta: e.target.value === "" ? null : Number(e.target.value) })
          }
          className="jarvis-input w-16"
        />
        kg
      </label>
    </div>
  );
}

/** Menú chico: peso actual + cuánto ha cambiado respecto a la pesada anterior.
 *  Usa el historial completo (`todo`), no el rango: es el estado real de hoy. */
function Delta({ todo, objetivo }: { todo: Row[]; objetivo: Objetivo }) {
  const actual = todo[todo.length - 1]?.peso ?? null;
  if (actual === null) return <span style={{ color: theme.muted }}>—</span>;
  const prev = todo.length >= 2 ? todo[todo.length - 2].peso : null;
  const d = prev !== null ? actual - prev : null;
  const color = d === null ? theme.muted
    : colorDelta(d, objetivo.direccion, theme.good, theme.alert, theme.amber);
  return (
    <>
      <span style={{ color: theme.text }}>{actual.toFixed(1)} kg</span>
      {d !== null && (
        <span style={{ color }}> {d >= 0 ? "▲" : "▼"} {Math.abs(d).toFixed(1)} kg</span>
      )}
      {d !== null && <span style={{ color: theme.muted }}> vs anterior</span>}
    </>
  );
}

// Ventanas de ritmo (últimas N pesadas) y su peso en la media ponderada de la estimación:
// más peso a lo reciente, la histórica solo ancla. Ordenadas de corto a largo plazo.
const RITMOS: { n: number | null; etiqueta: string; peso: number }[] = [
  { n: TREND_WIN, etiqueta: `${TREND_WIN} sem`, peso: 4 },
  { n: TREND_WIN2, etiqueta: `${TREND_WIN2} sem`, peso: 3 },
  { n: TREND_WIN3, etiqueta: `${TREND_WIN3} sem`, peso: 2 },
  { n: null, etiqueta: "hist", peso: 1 }, // n=null → todo el historial
];

const ritmoVentana = (todo: Row[], n: number | null) =>
  ritmoSemanal(n === null ? todo : todo.slice(-n));

/** Media ponderada de los ritmos disponibles (4/6/12/histórica) → kg/semana estimado. */
function ritmoPonderado(todo: Row[]): number | null {
  let num = 0, den = 0;
  for (const { n, peso } of RITMOS) {
    const r = ritmoVentana(todo, n);
    if (r !== null) { num += r * peso; den += peso; }
  }
  return den === 0 ? null : num / den;
}

/** Peso actual (hero) + cuánto ha cambiado respecto a la pesada anterior. */
function PesoActual({ todo, objetivo }: { todo: Row[]; objetivo: Objetivo }) {
  const actual = todo[todo.length - 1]?.peso ?? null;
  if (actual === null) return <span style={{ color: theme.muted }}>—</span>;
  const prev = todo.length >= 2 ? todo[todo.length - 2].peso : null;
  const d = prev !== null ? actual - prev : null;
  const c = d === null ? theme.muted : colorDelta(d, objetivo.direccion, theme.good, theme.alert, theme.amber);
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 2, color: HUD_LABEL, textTransform: "uppercase" }}>Actual</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: theme.text, lineHeight: 1.1, fontVariantNumeric: "tabular-nums" }}>
        {actual.toFixed(1)}<span style={{ fontSize: 12, color: theme.muted, fontWeight: 400 }}> kg</span>
      </div>
      {d !== null && (
        <div style={{ fontSize: 10, color: c, fontVariantNumeric: "tabular-nums" }}>
          {d >= 0 ? "▲" : "▼"} {Math.abs(d).toFixed(1)} <span style={{ color: theme.muted }}>vs anterior</span>
        </div>
      )}
    </div>
  );
}

/** Un "tile" HUD por ventana de ritmo: etiqueta arriba, valor grande coloreado por
 *  dirección, con barra superior del mismo color (el color nunca va solo: hay flecha + etiqueta). */
function TileRitmo({ etiqueta, r, direccion }: { etiqueta: string; r: number | null; direccion: Objetivo["direccion"] }) {
  const c = r === null ? theme.muted : colorDelta(r, direccion, theme.good, theme.alert, theme.amber);
  return (
    <div
      style={{
        position: "relative", minWidth: 74, padding: "8px 13px 9px", borderRadius: 8, overflow: "hidden",
        border: "1px solid rgba(0,212,255,0.14)",
        background: "linear-gradient(180deg, rgba(0,212,255,0.05) 0%, rgba(0,212,255,0.012) 100%)",
      }}
    >
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: c, opacity: 0.75 }} />
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: HUD_LABEL, textTransform: "uppercase" }}>{etiqueta}</div>
      <div style={{ fontSize: 19, fontWeight: 700, color: c, lineHeight: 1.2, fontVariantNumeric: "tabular-nums" }}>
        {r === null ? "—" : `${r >= 0 ? "▲" : "▼"} ${Math.abs(r).toFixed(2)}`}
      </div>
    </div>
  );
}

/** Fila de tiles con el ritmo (kg/sem) en 4/6/12 pesadas + histórico. */
function TablaRitmos({ todo, objetivo }: { todo: Row[]; objetivo: Objetivo }) {
  return (
    <div>
      <div style={{ display: "flex", gap: 8 }}>
        {RITMOS.map(({ n, etiqueta }) => (
          <TileRitmo key={etiqueta} etiqueta={etiqueta} r={ritmoVentana(todo, n)} direccion={objetivo.direccion} />
        ))}
      </div>
      <div style={{ fontSize: 9, letterSpacing: 1.2, color: HUD_LABEL, marginTop: 5, textTransform: "uppercase", opacity: 0.85 }}>
        kg / semana · ventanas de pesadas
      </div>
    </div>
  );
}

const fmtFechaLarga = (d: Date) =>
  `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;

/** Línea final: proyección a la meta usando la media ponderada de los ritmos. */
function Estimacion({ todo, objetivo }: { todo: Row[]; objetivo: Objetivo }) {
  if (objetivo.meta === null) return null;
  const actual = todo[todo.length - 1]?.peso ?? null;
  if (actual === null) return null;
  const falta = objetivo.meta - actual;

  // Callout HUD: borde/fondo cian tenues, marcador ◎ y los datos clave resaltados.
  const caja = (contenido: ReactNode, tono: string = theme.accent) => (
    <div
      style={{
        display: "inline-flex", alignItems: "center", gap: 9, padding: "8px 15px", borderRadius: 9,
        border: `1px solid ${tono}44`, background: `${tono}12`, fontSize: 13,
      }}
    >
      <span style={{ color: tono, fontSize: 15 }}>◎</span>
      <span>{contenido}</span>
    </div>
  );

  if (Math.abs(falta) < 0.05) {
    return caja(<span style={{ color: theme.good }}>Ya estás en tu meta de {objetivo.meta} kg</span>, theme.good);
  }
  const ritmo = ritmoPonderado(todo);
  if (ritmo === null || Math.abs(ritmo) < 0.01 || Math.sign(ritmo) !== Math.sign(falta)) {
    return caja(
      <span style={{ color: theme.muted }}>A este ritmo no te acercas a los {objetivo.meta} kg</span>,
      theme.muted,
    );
  }
  const semanas = falta / ritmo;
  const fecha = new Date(Date.now() + semanas * 7 * 86400000);
  return caja(
    <span style={{ color: theme.text }}>
      Llegarás a <b style={{ color: theme.accent }}>{objetivo.meta} kg</b> en{" "}
      <b style={{ color: theme.accent }}>≈ {Math.round(semanas)} semanas</b>
      <span style={{ color: theme.muted }}> · hacia el {fmtFechaLarga(fecha)}</span>
    </span>,
  );
}

export default function WeightTrend({
  rows, todo, objetivo, onChangeObjetivo, onExpand,
}: {
  rows: Row[];
  todo: Row[];
  objetivo: Objetivo;
  onChangeObjetivo: (o: Objetivo) => void;
  onExpand?: () => void;
}) {
  return (
    <Panel title="Peso" onExpand={onExpand}>
      <div className="mb-2"><Controles objetivo={objetivo} onChange={onChangeObjetivo} /></div>
      <div style={{ height: 203 }}>
        {rows.length === 0 ? (
          <div className="flex h-full items-center" style={{ color: theme.muted }}>—</div>
        ) : (
          <Chart rows={rows} objetivo={objetivo} height="100%" />
        )}
      </div>
      <div className="mt-1 text-[11px]">
        {todo.length > 0 && <Delta todo={todo} objetivo={objetivo} />}
      </div>
    </Panel>
  );
}

export function WeightExpanded({
  rows, todo, objetivo, onChangeObjetivo,
}: {
  rows: Row[];
  todo: Row[];
  objetivo: Objetivo;
  onChangeObjetivo: (o: Objetivo) => void;
}) {
  if (rows.length === 0) return <div style={{ color: theme.muted }}>Sin pesadas en este rango.</div>;
  return (
    <div className="flex h-[70vh] flex-col">
      <div className="mb-3 flex flex-wrap items-start gap-x-7 gap-y-4">
        <Controles objetivo={objetivo} onChange={onChangeObjetivo} />
        <PesoActual todo={todo} objetivo={objetivo} />
        <TablaRitmos todo={todo} objetivo={objetivo} />
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Estimacion todo={todo} objetivo={objetivo} />
        <span className="text-xs" style={{ color: theme.muted }}>
          {rows.length} pesadas · medias móviles de {TREND_WIN}, {TREND_WIN2} y {TREND_WIN3}
        </span>
      </div>
      <div className="min-h-0 flex-1">
        <Chart rows={rows} objetivo={objetivo} height="100%" />
      </div>
    </div>
  );
}
