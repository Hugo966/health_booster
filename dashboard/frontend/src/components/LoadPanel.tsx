import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import Panel from "./Panel";
import { anim, theme, tooltipStyle } from "./../lib/theme";
import { percentile, rollingSumByDate } from "./../lib/stats";
import { num, type SetRow } from "../lib/api";

// Widget 3.4 — Carga de entreno.
//
// Métrica PRINCIPAL: sRPE = RPE de sesión (form PM, 0-10) × nº de series. Es la
// medida de carga validada en ciencia del deporte y usa el RPE que Hugo puntúa,
// que ya pondera intensidad y singles pesados como el tonelaje nunca podría (un
// 170×1 @9.5 hace que la sesión sepa a RPE alto aunque el tonelaje sea bajo).
//
// DETALLE (de dónde viene la fatiga): series duras = series de trabajo cerca del
// fallo (RIR≤2 / RPE≥8), leyendo @ o RIR indistintamente (RPE = 10 − RIR).
// El tonelaje queda como dato secundario.

export type Sesion = {
  fecha: string;
  nSeries: number | null;
  rpeSesion: number | null; // RPE de sesión 0-10 (form PM)
  volumen: number;          // tonelaje total (kg·reps·series), secundario
  volBasicos: number | null;
  volAccesorios: number | null;
};

const VENTANA = 7; // días naturales

/** sRPE de una sesión = RPE sesión × nº series. null si falta el RPE de sesión. */
const srpe = (s: Sesion): number | null =>
  s.rpeSesion !== null && s.nSeries !== null ? s.rpeSesion * s.nSeries : null;

type Banda = { label: string; color: string };
function banda(v: number, p25: number, p75: number, p90: number): Banda {
  if (v < p25) return { label: "BAJO", color: theme.accent };
  if (v <= p75) return { label: "NORMAL", color: theme.good };
  if (v <= p90) return { label: "ALTO", color: theme.amber };
  return { label: "PICO", color: theme.alert };
}

const fmtDate = (f: string) => f.slice(8, 10) + "/" + f.slice(5, 7);
const COLOR_BASICOS = theme.accent;
const COLOR_ACCESORIOS = "#1b5a72";

type Analisis = {
  actual: number;
  mediana: number;
  p25: number; p75: number; p90: number;
  min: number; max: number;
  b: Banda;
  pct: number;
  rolling: { fecha: string; v: number }[];
};

/** sRPE acumulado de 7 días, solo en ventanas totalmente cubiertas por sesiones
 *  con RPE de sesión (las anteriores al form PM no cuentan). */
function rollingValido(sesiones: Sesion[]) {
  const con = sesiones
    .filter((s) => srpe(s) !== null)
    .map((s) => ({ fecha: s.fecha, v: srpe(s)! }));
  if (con.length === 0) return [];
  const desde = Date.parse(con[0].fecha) + (VENTANA - 1) * 86400000;
  return rollingSumByDate(con, VENTANA).filter((r) => Date.parse(r.fecha) >= desde);
}

/** Percentiles SIEMPRE sobre todo el histórico, no sobre el rango visible. */
function analizar(sesiones: Sesion[]): Analisis | null {
  const rolling = rollingValido(sesiones);
  if (rolling.length < 3) return null;
  const hist = rolling.map((r) => r.v);
  const actual = hist[hist.length - 1];
  const mediana = percentile(hist, 0.5);
  const p25 = percentile(hist, 0.25);
  const p75 = percentile(hist, 0.75);
  const p90 = percentile(hist, 0.9);
  return {
    actual, mediana, p25, p75, p90,
    min: Math.min(...hist),
    max: Math.max(...hist),
    b: banda(actual, p25, p75, p90),
    pct: mediana > 0 ? (actual / mediana - 1) * 100 : 0,
    rolling,
  };
}

// --- intensidad por serie: @ (RPE) o RIR indistintamente -------------------
const rpeEff = (s: SetRow): number | null => {
  const rpe = num(s.rpe);
  const rir = num(s.rir);
  const v = rpe !== null ? rpe : rir !== null ? 10 - rir : null;
  // descarta datos corruptos (RPE solo tiene sentido 0-10; hay algún token mal
  // parseado en el pipeline que da rpe>10, no debe reventar la escala).
  return v !== null && v >= 0 && v <= 10 ? v : null;
};
const esDura = (s: SetRow): boolean => {
  const e = rpeEff(s);
  return e !== null && e >= 8; // RIR ≤ 2
};

/** Detalle "de dónde viene la fatiga" en dos páginas, porque básicos y accesorios
 *  fatigan distinto: básicos por INTENSIDAD (el top set), accesorios por VOLUMEN
 *  cerca del fallo (series duras). El RPE de sesión va de referencia en ambas. */
function DetalleFatiga({ sets, sesiones }: { sets: SetRow[]; sesiones: Sesion[] }) {
  const [pag, setPag] = useState<"basicos" | "accesorios" | "combinado">("basicos");
  const rpeByFecha = useMemo(
    () => new Map(sesiones.map((s) => [s.fecha, s.rpeSesion])),
    [sesiones],
  );

  // Básicos: RPE del top set por sesión (lo más pesado que tocaste ese día).
  const dBas = useMemo(() => {
    const m = new Map<string, { fecha: string; top: number; rpeSes: number | null }>();
    for (const s of sets) {
      if (String(s.tipo) !== "básico") continue;
      const e = rpeEff(s);
      if (e === null) continue;
      const f = String(s.fecha ?? "");
      if (!f) continue;
      const row = m.get(f) ?? { fecha: f, top: 0, rpeSes: rpeByFecha.get(f) ?? null };
      row.top = Math.max(row.top, e);
      m.set(f, row);
    }
    return [...m.values()].sort((a, b) => a.fecha.localeCompare(b.fecha));
  }, [sets, rpeByFecha]);

  // Accesorios: series duras (RIR≤2) por sesión.
  const dAcc = useMemo(() => {
    const m = new Map<string, { fecha: string; duras: number; rpeSes: number | null }>();
    for (const s of sets) {
      if (String(s.tipo) === "básico") continue;
      const f = String(s.fecha ?? "");
      if (!f) continue;
      const row = m.get(f) ?? { fecha: f, duras: 0, rpeSes: rpeByFecha.get(f) ?? null };
      if (esDura(s)) row.duras += num(s.n_series) ?? 0;
      m.set(f, row);
    }
    return [...m.values()].sort((a, b) => a.fecha.localeCompare(b.fecha));
  }, [sets, rpeByFecha]);

  // Combinado: (máx de básicos + media de accesorios) / 2. En básicos manda la
  // serie más dura; en accesorios, la media. Es una intensidad objetiva (de tus
  // @/RIR) para comparar con tu RPE de sesión subjetivo.
  const dCom = useMemo(() => {
    const maxBas = new Map<string, number>();
    const acc = new Map<string, { suma: number; n: number }>();
    for (const s of sets) {
      const e = rpeEff(s);
      if (e === null) continue;
      const f = String(s.fecha ?? "");
      if (!f) continue;
      if (String(s.tipo) === "básico") {
        maxBas.set(f, Math.max(maxBas.get(f) ?? 0, e));
      } else {
        const ns = num(s.n_series) ?? 1;
        const a = acc.get(f) ?? { suma: 0, n: 0 };
        a.suma += e * ns; a.n += ns; acc.set(f, a);
      }
    }
    const fechas = new Set([...maxBas.keys(), ...acc.keys()]);
    return [...fechas].map((f) => {
      const mb = maxBas.get(f) ?? null;
      const a = acc.get(f);
      const ma = a ? a.suma / a.n : null;
      const comb = mb !== null && ma !== null ? (mb + ma) / 2 : mb !== null ? mb : ma;
      return { fecha: f, comb, rpeSes: rpeByFecha.get(f) ?? null };
    }).sort((a, b) => a.fecha.localeCompare(b.fecha));
  }, [sets, rpeByFecha]);

  const PAGS = { basicos: "BÁSICOS", accesorios: "ACCESORIOS", combinado: "COMBINADO" } as const;
  const SUB = {
    basicos: "intensidad del top set vs RPE de sesión",
    accesorios: "series duras (RIR≤2) vs RPE de sesión",
    combinado: "máx básicos + media accesorios, /2 · vs RPE de sesión",
  } as const;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <span className="text-[11px]" style={{ color: theme.muted }}>De dónde viene la fatiga</span>
        <div className="inline-flex rounded-lg p-0.5" style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.14)" }}>
          {(["basicos", "accesorios", "combinado"] as const).map((p) => (
            <button key={p} onClick={() => setPag(p)} className="jarvis-seg font-display text-[10px] tracking-[0.2em]"
              style={{ color: pag === p ? theme.bg : theme.muted, background: pag === p ? theme.accent : "transparent" }}>
              {PAGS[p]}
            </button>
          ))}
        </div>
        <span className="text-[10px]" style={{ color: theme.muted }}>{SUB[pag]}</span>
      </div>
      <div className="min-h-0 flex-1">
        {pag === "basicos" ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={dBas} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              <XAxis dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 10 }} minTickGap={24} stroke={theme.grid} />
              <YAxis domain={[0, 10]} allowDataOverflow width={26} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
              <Tooltip {...tooltipStyle} formatter={(v: any, n) => [Number(v).toFixed(1), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="top" name="Top set básicos (RPE)" fill={COLOR_BASICOS} fillOpacity={0.8} radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar} />
              <Line dataKey="rpeSes" name="RPE sesión" stroke={theme.amber} strokeWidth={2} dot={{ r: 2, fill: theme.amber }} connectNulls={false} isAnimationActive={anim.on} animationDuration={anim.ms} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : pag === "accesorios" ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={dAcc} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              <XAxis dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 10 }} minTickGap={24} stroke={theme.grid} />
              <YAxis yAxisId="l" width={26} allowDecimals={false} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
              <YAxis yAxisId="r" orientation="right" domain={[0, 10]} width={24} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
              <Tooltip {...tooltipStyle} formatter={(v: any, n) => [n === "RPE sesión" ? Number(v).toFixed(1) : `${v} series`, n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="l" dataKey="duras" name="Series duras accesorios" fill={COLOR_ACCESORIOS} radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar} />
              <Line yAxisId="r" dataKey="rpeSes" name="RPE sesión" stroke={theme.amber} strokeWidth={2} dot={{ r: 2, fill: theme.amber }} connectNulls={false} isAnimationActive={anim.on} animationDuration={anim.ms} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={dCom} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              <XAxis dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 10 }} minTickGap={24} stroke={theme.grid} />
              <YAxis domain={[0, 10]} allowDataOverflow width={26} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
              <Tooltip {...tooltipStyle} formatter={(v: any, n) => [Number(v).toFixed(1), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="comb" name="Intensidad combinada" fill={COLOR_BASICOS} fillOpacity={0.8} radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar} />
              <Line dataKey="rpeSes" name="RPE sesión" stroke={theme.amber} strokeWidth={2} dot={{ r: 2, fill: theme.amber }} connectNulls={false} isAnimationActive={anim.on} animationDuration={anim.ms} />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

/** Regla segmentada con los percentiles propios y un marcador en el valor actual. */
function Regla({ a }: { a: Analisis }) {
  const span = a.max - a.min;
  const pad = span > 0 ? span * 0.12 : Math.max(a.max * 0.05, 1);
  const lo = a.min - pad, hi = a.max + pad;
  const pct = (v: number) => `${Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100))}%`;
  return (
    <div className="mt-2">
      <div className="relative h-2.5 w-full overflow-hidden rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="absolute inset-y-0 left-0" style={{ width: pct(a.p25), background: `${theme.accent}55` }} />
        <div className="absolute inset-y-0" style={{ left: pct(a.p25), width: `calc(${pct(a.p75)} - ${pct(a.p25)})`, background: `${theme.good}66` }} />
        <div className="absolute inset-y-0" style={{ left: pct(a.p75), width: `calc(${pct(a.p90)} - ${pct(a.p75)})`, background: `${theme.amber}66` }} />
        <div className="absolute inset-y-0 right-0" style={{ left: pct(a.p90), background: `${theme.alert}66` }} />
        <div className="jarvis-marker absolute inset-y-[-3px] w-[2.5px] rounded"
             style={{ left: pct(a.actual), background: "#fff", boxShadow: "0 0 8px rgba(255,255,255,0.9)" }} />
      </div>
      <div className="mt-1 flex justify-between text-[9px]" style={{ color: theme.muted }}>
        <span>{Math.round(a.min)}</span>
        <span>mediana {Math.round(a.mediana)}</span>
        <span>{Math.round(a.max)}</span>
      </div>
    </div>
  );
}

function Cabecera({ a }: { a: Analisis }) {
  return (
    <div className="flex items-baseline gap-3">
      <div className="font-display text-3xl leading-none" style={{ color: a.b.color, textShadow: `0 0 16px ${a.b.color}55` }}>
        {Math.round(a.actual)}
        <span className="ml-1 text-sm" style={{ color: theme.muted }}>sRPE</span>
      </div>
      <div className="font-display text-xs tracking-[0.25em]" style={{ color: a.b.color }}>{a.b.label}</div>
      <div className="ml-auto text-[11px]" style={{ color: theme.muted }}>
        {a.pct >= 0 ? "+" : ""}{a.pct.toFixed(0)}% vs tu mediana
      </div>
    </div>
  );
}

/** Barras de sRPE por sesión. */
function BarrasSrpe({ sesiones, height }: { sesiones: Sesion[]; height: number | string }) {
  const data = sesiones
    .map((s) => ({ fecha: s.fecha, sRPE: srpe(s) }))
    .filter((d): d is { fecha: string; sRPE: number } => d.sRPE !== null);
  if (data.length === 0)
    return <div className="flex h-full items-center text-[11px]" style={{ color: theme.muted }}>aún sin RPE de sesión</div>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        <XAxis dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 9 }} minTickGap={18} stroke={theme.grid} />
        <YAxis width={30} tick={{ fill: theme.muted, fontSize: 9 }} stroke={theme.grid} />
        <Tooltip {...tooltipStyle} formatter={(v: any) => [`${Math.round(Number(v))} sRPE`, "Sesión"]} />
        <Bar dataKey="sRPE" fill={theme.accent} fillOpacity={0.8} radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function LoadPanel({
  todas, rango, onExpand,
}: { todas: Sesion[]; rango: Sesion[]; onExpand?: () => void }) {
  const a = analizar(todas);
  const ultima = a?.rolling[a.rolling.length - 1]?.fecha ?? null;
  return (
    <Panel title="Carga" subtitle="sRPE · últimos 7 días" onExpand={onExpand}>
      {a === null ? (
        <div className="flex h-[190px] flex-col items-start justify-center gap-1 text-xs" style={{ color: theme.muted }}>
          <span>Acumulando datos de sRPE.</span>
          <span className="text-[10px]">Necesita ~1 semana con RPE de sesión en el form PM.</span>
        </div>
      ) : (
        <>
          <Cabecera a={a} />
          <Regla a={a} />
          <div className="mt-3" style={{ height: 112 }}>
            <BarrasSrpe sesiones={rango.slice(-14)} height="100%" />
          </div>
          <div className="mt-1 text-[10px]" style={{ color: theme.muted }}>
            Suma del sRPE de tus sesiones en los 7 días hasta tu última{ultima ? ` (${fmtDate(ultima)})` : ""} · RPE sesión × series
          </div>
        </>
      )}
    </Panel>
  );
}

export function LoadExpanded({
  todas, rango, sets,
}: { todas: Sesion[]; rango: Sesion[]; sets: SetRow[] }) {
  const a = analizar(todas);
  const tonProm = (() => {
    const v = rango.filter((s) => s.volumen > 0).map((s) => s.volumen);
    return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null;
  })();

  return (
    <div className="flex h-[74vh] flex-col gap-4">
      <p className="max-w-3xl text-xs leading-relaxed" style={{ color: theme.muted }}>
        La carga principal es el <b style={{ color: theme.text }}>sRPE</b> = tu RPE de sesión (0-10) × nº de
        series, sumado en los últimos 7 días. Es la medida validada de carga y usa tu RPE, que ya pondera la
        intensidad como el tonelaje no puede. Debajo, <b style={{ color: theme.text }}>de dónde viene la
        fatiga</b>: básicos por intensidad, accesorios por series duras, y el combinado de ambos.
      </p>

      {a === null ? (
        <div className="text-sm" style={{ color: theme.muted }}>
          Aún no hay suficientes sesiones con RPE de sesión (necesita ~3 ventanas de 7 días). Se irá
          llenando según sigas rellenando el form PM.
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-x-10 gap-y-3">
          <div className="min-w-[280px] flex-1">
            <Cabecera a={a} />
            <Regla a={a} />
          </div>
          <div className="flex flex-wrap gap-x-7 gap-y-1 text-xs" style={{ color: theme.muted }}>
            <span>mediana <b style={{ color: theme.text }}>{Math.round(a.mediana)}</b></span>
            <span>p75 <b style={{ color: theme.amber }}>{Math.round(a.p75)}</b></span>
            <span>p90 <b style={{ color: theme.alert }}>{Math.round(a.p90)}</b></span>
            {tonProm !== null && <span>tonelaje medio <b style={{ color: theme.text }}>{(tonProm / 1000).toFixed(1)} t</b></span>}
          </div>
        </div>
      )}

      {a !== null && (
        <div className="min-h-0 flex-1">
          <div className="mb-1 text-[11px]" style={{ color: theme.muted }}>
            sRPE acumulado de {VENTANA} días (línea gris = tu mediana)
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={a.rolling.map((r) => ({ fecha: r.fecha, sRPE: r.v, color: banda(r.v, a.p25, a.p75, a.p90).color }))}
                           margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid stroke={theme.grid} vertical={false} />
              <XAxis dataKey="fecha" tickFormatter={fmtDate} tick={{ fill: theme.muted, fontSize: 10 }} minTickGap={24} stroke={theme.grid} />
              <YAxis width={40} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
              <Tooltip {...tooltipStyle} formatter={(v: any) => [`${Math.round(Number(v))} sRPE`, `${VENTANA}d`]} />
              <Bar dataKey="sRPE" radius={[3, 3, 0, 0]} isAnimationActive={anim.on} animationDuration={anim.msBar}>
                {a.rolling.map((r, i) => <Cell key={i} fill={banda(r.v, a.p25, a.p75, a.p90).color} fillOpacity={0.75} />)}
              </Bar>
              <Line dataKey={() => a.mediana} stroke={theme.muted} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="h-[34%] min-h-[160px]">
        <DetalleFatiga sets={sets} sesiones={rango} />
      </div>
    </div>
  );
}
