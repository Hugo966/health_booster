import { useMemo, useState } from "react";
import Panel from "./Panel";
import { theme } from "./../lib/theme";
import { num, type DerivedRow } from "../lib/api";

// Widget de Notas: el texto libre que el usuario escribe en los formularios AM y PM
// (`notas_am`, `notas_pm`) y la nota del dolor de sesión (`dolor_sesion_nota`),
// por fecha. Da contexto que los números no capturan; Jarvis también las lee (van
// en el briefing). Al clicar una nota se abre un detalle con 3 indicadores de ESE
// día y el SIGUIENTE (readiness · sueño · HRV), para ligar cómo se sintió con los
// datos y ver si arrastra al día siguiente.

type Nota = { fecha: string; am: string; pm: string; dolor: string };

function extraer(rows: DerivedRow[]): Nota[] {
  const out: Nota[] = [];
  for (const r of rows) {
    const am = String(r.notas_am ?? "").trim();
    const pm = String(r.notas_pm ?? "").trim();
    const dolor = String(r.dolor_sesion_nota ?? "").trim();
    if (am || pm || dolor) out.push({ fecha: String(r.fecha ?? ""), am, pm, dolor });
  }
  return out.sort((a, b) => b.fecha.localeCompare(a.fecha)); // más recientes primero
}

const fmtFecha = (f: string) => (f.length >= 10 ? `${f.slice(8, 10)}/${f.slice(5, 7)}` : f);

// Fecha AAAA-MM-DD construida en UTC. Antes se usaba `new Date(...).toISOString()`, que
// con la zona horaria local desplazaba el día y devolvía el MISMO día (el bug de que
// "ese día" y "día siguiente" salían iguales).
function isoUTC(y: number, m: number, d: number): string {
  const dt = new Date(Date.UTC(y, m - 1, d));
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}`;
}
function diaSiguiente(f: string): string {
  const [y, m, d] = f.split("-").map(Number);
  if (!y || !m || !d) return "";
  return isoUTC(y, m, d + 1);
}
// Media de readiness de la semana (7 días acabando en `fecha`), para colorear el
// readiness del día: verde si está por encima de su semana, rojo si por debajo.
function mediaReadinessSemana(fecha: string, porFecha: Map<string, DerivedRow>): number | null {
  const [y, m, d] = fecha.split("-").map(Number);
  if (!y) return null;
  const vals: number[] = [];
  for (let i = 0; i < 7; i++) {
    const row = porFecha.get(isoUTC(y, m, d - i));
    const v = row ? num(row.readiness) : null;
    if (v !== null) vals.push(v);
  }
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

// Los 3 indicadores del detalle (recuperación). `sub` es una segunda línea opcional:
// en el sueño, el rato en cama SIN dormir (tiempo en cama − horas dormidas = lo que
// tardas en dormirte + despertares; aún no se separan). Para cambiar un indicador
// (p.ej. HRV -> Carga sRPE), edita aquí.
type Indicador = {
  nombre: string;
  campo: string;
  fmt: (v: number) => string;
  color?: (v: number, fecha: string, porFecha: Map<string, DerivedRow>) => string | undefined;
  sub?: (row: DerivedRow, fecha: string, porFecha: Map<string, DerivedRow>) => { text: string; color: string } | null;
};
const INDICADORES: Indicador[] = [
  {
    nombre: "Readiness", campo: "readiness", fmt: (v) => String(Math.round(v)),
    // Color por la diferencia REDONDEADA con su media semanal: >media verde,
    // <media rojo, = media naranja (así el número y el "vs media" van a juego).
    color: (v, fecha, pf) => {
      const m = mediaReadinessSemana(fecha, pf);
      if (m === null) return undefined;
      const d = Math.round(v - m);
      return d > 0 ? theme.good : d < 0 ? theme.alert : theme.amber;
    },
    // Cuánto por encima/debajo de su media semanal.
    sub: (row, fecha, pf) => {
      const v = num(row.readiness), m = mediaReadinessSemana(fecha, pf);
      if (v === null || m === null) return null;
      const d = Math.round(v - m);
      const color = d > 0 ? theme.good : d < 0 ? theme.alert : theme.amber;
      return { text: `${d > 0 ? "+" : ""}${d} vs media`, color };
    },
  },
  {
    nombre: "Sueño", campo: "sueno_horas", fmt: (v) => `${v.toFixed(1)} h`,
    // >7.5h verde · 6.5-7.5h naranja · <6.5h rojo.
    color: (v) => (v > 7.5 ? theme.good : v >= 6.5 ? theme.amber : theme.alert),
    // Rato en cama sin dormir. ≤10min verde · 10-30 naranja · >30 rojo.
    sub: (row) => {
      const cama = num(row.tiempo_en_cama_h), dorm = num(row.sueno_horas);
      if (cama === null || dorm === null) return null;
      const min = Math.round((cama - dorm) * 60);
      if (min <= 0) return null;
      const color = min <= 10 ? theme.good : min <= 30 ? theme.amber : theme.alert;
      return { text: `+${min} min en cama`, color };
    },
  },
  { nombre: "HRV", campo: "hrv_rmssd", fmt: (v) => `${Math.round(v)} ms` },
];

function Etiqueta({ children, color }: { children: string; color: string }) {
  return (
    <span
      className="font-display mr-2 rounded px-1.5 py-0.5 text-[9px] uppercase tracking-[0.15em]"
      style={{ color, border: `1px solid ${color}55`, background: `${color}14` }}
    >
      {children}
    </span>
  );
}

function Celda({ v, color, sub, subColor }: { v: string | null; color?: string; sub?: string | null; subColor?: string }) {
  return (
    <td className="px-3 py-1 text-right font-display tabular-nums align-top" style={{ color: v === null ? theme.muted : color ?? theme.text }}>
      {v === null ? "—" : v}
      {v !== null && sub && <div className="text-[10px]" style={{ color: subColor ?? theme.muted }}>{sub}</div>}
    </td>
  );
}

// Mini-panel de detalle: 3 indicadores × (ese día, día siguiente), con colores.
function Detalle({ fecha, porFecha }: { fecha: string; porFecha: Map<string, DerivedRow> }) {
  const sig = diaSiguiente(fecha);
  // Cada columna calcula su valor, su color y (para el sueño) la línea de latencia.
  const cel = (row: DerivedRow | undefined, ind: Indicador, fCol: string) => {
    const v = row ? num(row[ind.campo]) : null;
    const s = row && ind.sub ? ind.sub(row, fCol, porFecha) : null;
    return {
      v: v === null ? null : ind.fmt(v),
      color: v !== null && ind.color ? ind.color(v, fCol, porFecha) : undefined,
      sub: s?.text ?? null,
      subColor: s?.color,
    };
  };
  return (
    <div className="mt-2 rounded-lg px-3 py-2" style={{ background: "rgba(0,212,255,0.05)", border: `1px solid ${theme.accent}33` }}>
      <table className="w-full text-[12px]">
        <thead>
          <tr style={{ color: theme.muted }}>
            <th className="py-1 text-left font-normal" />
            <th className="px-3 py-1 text-right font-normal">Ese día</th>
            <th className="px-3 py-1 text-right font-normal">Día sig. ({fmtFecha(sig)})</th>
          </tr>
        </thead>
        <tbody>
          {INDICADORES.map((ind) => (
            <tr key={ind.campo} style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
              <td className="py-1" style={{ color: theme.muted }}>{ind.nombre}</td>
              <Celda {...cel(porFecha.get(fecha), ind, fecha)} />
              <Celda {...cel(porFecha.get(sig), ind, sig)} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Tarjeta({ n, activo, onClick }: { n: Nota; activo: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full rounded-lg px-3 py-2 text-left transition-colors"
      style={{
        background: activo ? "rgba(0,212,255,0.08)" : "rgba(255,255,255,0.03)",
        border: `1px solid ${activo ? theme.accent + "55" : "rgba(255,255,255,0.06)"}`,
      }}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="font-display text-[11px] tracking-[0.15em]" style={{ color: theme.accent }}>{fmtFecha(n.fecha)}</span>
        <span className="text-[10px]" style={{ color: theme.muted }}>{activo ? "▾ día" : "▸ ver día"}</span>
      </div>
      <div className="flex flex-col gap-1 text-[12.5px] leading-snug" style={{ color: theme.text }}>
        {n.am && <div><Etiqueta color={theme.accent}>AM</Etiqueta>{n.am}</div>}
        {n.pm && <div><Etiqueta color={theme.good}>PM</Etiqueta>{n.pm}</div>}
        {n.dolor && <div><Etiqueta color={theme.amber}>Dolor</Etiqueta>{n.dolor}</div>}
      </div>
    </button>
  );
}

function Lista({ notas, porFecha, vacio }: { notas: Nota[]; porFecha: Map<string, DerivedRow>; vacio: string }) {
  const [sel, setSel] = useState<string | null>(null);
  if (notas.length === 0)
    return <div className="text-[13px]" style={{ color: theme.muted }}>{vacio}</div>;
  return (
    <div className="flex flex-col gap-2">
      {notas.map((n, i) => (
        <div key={n.fecha + "-" + i}>
          <Tarjeta n={n} activo={sel === n.fecha} onClick={() => setSel(sel === n.fecha ? null : n.fecha)} />
          {sel === n.fecha && <Detalle fecha={n.fecha} porFecha={porFecha} />}
        </div>
      ))}
    </div>
  );
}

const VACIO = "Aún no has escrito notas en los formularios AM/PM. Cuando lo hagas, aparecen aquí por fecha (y Jarvis las lee).";

function usarDatos(rows: DerivedRow[]) {
  const notas = useMemo(() => extraer(rows), [rows]);
  const porFecha = useMemo(() => new Map(rows.map((r) => [String(r.fecha ?? ""), r])), [rows]);
  return { notas, porFecha };
}

export default function NotasPanel({ rows, onExpand }: { rows: DerivedRow[]; onExpand?: (origin?: DOMRect) => void }) {
  const { notas, porFecha } = usarDatos(rows);
  return (
    <Panel title="Notas" subtitle="de tus formularios · toca para ver el día" onExpand={onExpand}>
      <div className="min-h-0 overflow-y-auto pr-1" style={{ height: 263 }}>
        <Lista notas={notas} porFecha={porFecha} vacio={VACIO} />
      </div>
    </Panel>
  );
}

export function NotasExpanded({ rows }: { rows: DerivedRow[] }) {
  const { notas, porFecha } = usarDatos(rows);
  return (
    <div className="mx-auto flex h-[72vh] min-h-0 w-full max-w-3xl flex-col">
      <div className="mb-2 text-[11px]" style={{ color: theme.muted }}>
        Texto libre de tus formularios AM/PM, por fecha. Toca una nota para ver readiness · sueño · HRV de ese día y el siguiente. Jarvis también las lee.
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <Lista notas={notas} porFecha={porFecha} vacio={VACIO} />
      </div>
    </div>
  );
}
