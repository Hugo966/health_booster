import { useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import Panel from "./Panel";
import { anim, PALETTE, theme, tooltipStyle } from "./../lib/theme";
import {
  bloqueSemana, bsOrden, categoria, CATEGORIA_LABEL, COMPETICION, patron,
  type Categoria,
} from "../lib/exercises";
import type { SetRow } from "../lib/api";
import { num } from "../lib/api";

// Widget 3.5 — Fuerza.
//
// Básicos y variantes: una línea por ejercicio, métrica PESO del top set (con
// toggle a e1RM y volumen). Accesorios: demasiados ejercicios, así que se agrupan
// por GRUPO MUSCULAR (empuje, tracción…) y se mira volumen o series duras.
// Al pasar el ratón por una línea (o su chip) se resalta y los demás se atenúan;
// el tooltip da el detalle (series×reps×@ en ejercicios; series/duras en grupos).

type MetExc = "peso" | "e1rm" | "volumen";
type MetAcc = "volumen" | "duras";

type SetN = {
  ejercicio: string; cat: Categoria; pat: string; bs: string; orden: number;
  kg: number | null; reps: number | null; rpe: number | null; rir: number | null;
  e1rm: number | null; volumen: number; nSeries: number;
};

function normalizar(sets: SetRow[]): SetN[] {
  const out: SetN[] = [];
  for (const s of sets) {
    const ej = String(s.ejercicio ?? "").trim();
    const b = num(s.bloque), sem = num(s.semana);
    if (!ej || b === null || sem === null) continue;
    out.push({
      ejercicio: ej,
      cat: categoria(ej, String(s.tipo ?? "")),
      pat: patron(ej),
      bs: bloqueSemana(b, sem),
      orden: bsOrden(b, sem),
      kg: num(s.kg), reps: num(s.reps), rpe: num(s.rpe), rir: num(s.rir),
      e1rm: num(s.e1rm), volumen: num(s.volumen) ?? 0, nSeries: num(s.n_series) ?? 1,
    });
  }
  return out;
}

const rpeEff = (rpe: number | null, rir: number | null) =>
  rpe != null ? rpe : rir != null ? 10 - rir : null;

// Estructura común para el gráfico: clave -> semana -> {valor, detalle}.
type Celda = { orden: number; valor: number | null; detalle: string };
type Agg = Map<string, Map<string, Celda>>;

/** Una clave por ejercicio, top set (máx kg) por semana. `pat` opcional filtra a
 *  un grupo muscular (para el drill-down de accesorios). */
function aggEjercicios(filas: SetN[], cat: Categoria, metrica: MetExc, pat?: string): Agg {
  type Raw = { orden: number; kg: number | null; reps: number | null; rpe: number | null; rir: number | null; nSeries: number; e1rm: number | null; volumen: number };
  const raw = new Map<string, Map<string, Raw>>();
  for (const f of filas) {
    if (f.cat !== cat) continue;
    if (pat && f.pat !== pat) continue;
    let byBs = raw.get(f.ejercicio);
    if (!byBs) { byBs = new Map(); raw.set(f.ejercicio, byBs); }
    let r = byBs.get(f.bs);
    if (!r) { r = { orden: f.orden, kg: null, reps: null, rpe: null, rir: null, nSeries: 0, e1rm: null, volumen: 0 }; byBs.set(f.bs, r); }
    r.volumen += f.volumen;
    if (f.kg != null && (r.kg == null || f.kg > r.kg)) {
      r.kg = f.kg; r.reps = f.reps; r.rpe = f.rpe; r.rir = f.rir; r.nSeries = f.nSeries; r.e1rm = f.e1rm;
    }
  }
  const out: Agg = new Map();
  for (const [ex, byBs] of raw) {
    const m = new Map<string, Celda>();
    for (const [bs, r] of byBs) {
      const valor = metrica === "peso" ? r.kg : metrica === "e1rm" ? r.e1rm : r.volumen;
      const inten = r.rpe != null ? `@${r.rpe}` : r.rir != null ? `RIR${r.rir}` : "";
      const detalle = `${r.nSeries}×${r.reps ?? "?"}${inten ? ` ${inten}` : ""}${r.e1rm != null ? ` · e1RM ${r.e1rm.toFixed(0)}` : ""}`;
      m.set(bs, { orden: r.orden, valor, detalle });
    }
    out.set(ex, m);
  }
  return out;
}

/** Accesorios: una clave por GRUPO muscular, volumen y series duras por semana. */
function aggGrupos(filas: SetN[], metrica: MetAcc): Agg {
  const raw = new Map<string, Map<string, { orden: number; volumen: number; series: number; duras: number }>>();
  for (const f of filas) {
    if (f.cat !== "accesorio") continue;
    let byBs = raw.get(f.pat);
    if (!byBs) { byBs = new Map(); raw.set(f.pat, byBs); }
    let r = byBs.get(f.bs);
    if (!r) { r = { orden: f.orden, volumen: 0, series: 0, duras: 0 }; byBs.set(f.bs, r); }
    r.volumen += f.volumen;
    r.series += f.nSeries;
    const e = rpeEff(f.rpe, f.rir);
    if (e != null && e >= 8) r.duras += f.nSeries;
  }
  const out: Agg = new Map();
  for (const [g, byBs] of raw) {
    const m = new Map<string, Celda>();
    for (const [bs, r] of byBs) {
      const valor = metrica === "duras" ? r.duras : r.volumen;
      m.set(bs, { orden: r.orden, valor, detalle: `${r.series} series · ${r.duras} duras · ${(r.volumen / 1000).toFixed(2)} t` });
    }
    out.set(g, m);
  }
  return out;
}

/** PRs (récords): semanas en que una clave marca un nuevo máximo histórico. Se calcula
 *  sobre el agg de TODO el historial (no el rango) y solo tiene sentido en métricas donde
 *  "más = mejor" (peso, e1RM). La primera semana no cuenta como récord (es la línea base). */
function prsDe(aggFull: Agg): Set<string> {
  const prs = new Set<string>();
  for (const [key, byBs] of aggFull) {
    const celdas = [...byBs.entries()].sort((a, b) => a[1].orden - b[1].orden);
    let max = -Infinity, primera = true;
    for (const [bs, c] of celdas) {
      if (c.valor == null) continue;
      if (!primera && c.valor > max) prs.add(`${key}|${bs}`);
      if (c.valor > max) max = c.valor;
      primera = false;
    }
  }
  return prs;
}

function colorDe(key: string, orden: string[]): string {
  const i = orden.indexOf(key);
  return PALETTE[(i < 0 ? 0 : i) % PALETTE.length];
}

type Formato = { valor: (v: number) => string; tick: (v: number) => string; cero: boolean };

function Grafico({
  agg, keys, orden, fmt, height, activo, setActivo, onClave, pr,
}: {
  agg: Agg; keys: string[]; orden: string[]; fmt: Formato;
  height: number | string; activo: string | null; setActivo: (s: string | null) => void;
  onClave?: (k: string) => void; // si se pasa, pinchar una línea la selecciona (drill-down)
  pr?: Set<string>; // claves|semana que son récord → se marcan con ★
}) {
  // Punto normal, o estrella si esa semana es un PR de esa clave.
  const hazDot = (k: string, c: string, atenua: boolean) => (props: any) => {
    const { cx, cy, payload, index } = props;
    if (cx == null || cy == null || payload?.[k] == null) return <g key={`${k}-${index}`} />;
    const op = atenua ? 0.2 : 1;
    if (pr?.has(`${k}|${payload.bs}`))
      return (
        // Récord = estrella amarilla (dorada), no del color de la línea, para que destaque.
        <text key={`${k}-${index}`} x={cx} y={cy + 0.5} textAnchor="middle" dominantBaseline="central"
          fontSize={activo === k ? 16 : 13} fill="#ffdd59" fillOpacity={op} stroke={theme.bg} strokeWidth={0.7}
          style={{ paintOrder: "stroke" }}>★</text>
      );
    return <circle key={`${k}-${index}`} cx={cx} cy={cy} r={2.6} fill={c} fillOpacity={op} />;
  };
  const { rows, det } = useMemo(() => {
    const bsOrd = new Map<string, number>();
    for (const k of keys) for (const [bs, c] of agg.get(k) ?? []) bsOrd.set(bs, c.orden);
    const bsList = [...bsOrd.entries()].sort((a, b) => a[1] - b[1]).map(([bs]) => bs);
    const det = new Map<string, string>();
    const rows = bsList.map((bs) => {
      const row: Record<string, any> = { bs };
      for (const k of keys) {
        const c = agg.get(k)?.get(bs);
        if (!c) continue;
        det.set(`${bs}|${k}`, c.detalle);
        if (c.valor != null) row[k] = c.valor;
      }
      return row;
    });
    return { rows, det };
  }, [agg, keys]);

  if (rows.length === 0)
    return <div className="flex h-full items-center" style={{ color: theme.muted }}>Sin datos en este rango.</div>;

  const ys = rows.flatMap((r) => keys.map((k) => r[k]).filter((v): v is number => typeof v === "number"));
  const dom: [number, number] = fmt.cero
    ? [0, ys.length ? Math.max(...ys) * 1.05 : 1]
    : ys.length
      ? [Math.floor((Math.min(...ys) - 10) / 10) * 10, Math.ceil((Math.max(...ys) + 10) / 10) * 10]
      : [0, 100];

  const Contenido = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const bs = String(label);
    const items = activo ? payload.filter((p: any) => p.dataKey === activo) : payload;
    if (items.length === 0) return null;
    return (
      <div style={{ ...tooltipStyle.contentStyle, padding: "6px 10px" }}>
        <div style={tooltipStyle.labelStyle}>{bs}</div>
        {items.map((p: any) => (
          <div key={p.dataKey} style={{ fontSize: 12, marginTop: 2 }}>
            <span style={{ color: p.color, fontWeight: 700 }}>{p.dataKey}</span>{" "}
            <span style={{ color: theme.text }}>{fmt.valor(Number(p.value))}</span>
            {activo && det.get(`${bs}|${p.dataKey}`) && (
              <div style={{ color: theme.muted, fontSize: 11 }}>{det.get(`${bs}|${p.dataKey}`)}</div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ height, cursor: onClave ? "pointer" : undefined }}>
      <ResponsiveContainer width="100%" height="100%">
        {/* pinchar mientras hay una línea resaltada (ratón encima) = entrar en ella;
            reusa el hover, que sí es fiable, en vez del onClick de <Line>. */}
        <LineChart data={rows} onMouseLeave={() => setActivo(null)}
          onClick={() => { if (onClave && activo) onClave(activo); }}
          margin={{ top: 10, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis dataKey="bs" tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
          <YAxis width={44} domain={dom} allowDataOverflow tickFormatter={fmt.tick} tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid} />
          <Tooltip content={<Contenido />} />
          {keys.map((k) => {
            const c = colorDe(k, orden);
            const atenua = activo !== null && activo !== k;
            return (
              <Line
                key={k} dataKey={k} name={k} stroke={c} connectNulls
                strokeWidth={activo === k ? 3.2 : 2} strokeOpacity={atenua ? 0.15 : 1}
                isAnimationActive={anim.on} animationDuration={anim.ms}
                dot={hazDot(k, c, atenua) as any}
                activeDot={{ r: activo === k ? 6 : 5, onMouseEnter: () => setActivo(k), onClick: () => onClave?.(k) } as any}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Chips({
  items, activos, onToggle, color, resaltar,
}: {
  items: string[]; activos: string[]; onToggle: (s: string) => void;
  color: (s: string) => string; resaltar?: (s: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((it) => {
        const on = activos.includes(it);
        const c = color(it);
        return (
          <button
            key={it} onClick={() => onToggle(it)}
            onMouseEnter={() => resaltar?.(it)} onMouseLeave={() => resaltar?.(null)}
            className="jarvis-chip"
            style={{ borderColor: on ? c : "rgba(255,255,255,0.10)", color: on ? theme.text : theme.muted, background: on ? `${c}1f` : "transparent" }}
          >
            <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: on ? c : theme.muted }} />
            {it}
          </button>
        );
      })}
    </div>
  );
}

// Formatos por métrica.
const FMT_KG: Formato = { valor: (v) => `${v} kg`, tick: (v) => String(v), cero: false };
const FMT_E1RM: Formato = { valor: (v) => `${v.toFixed(1)} kg`, tick: (v) => String(v), cero: false };
const FMT_VOL: Formato = { valor: (v) => `${(v / 1000).toFixed(2)} t`, tick: (v) => `${(v / 1000).toFixed(0)}t`, cero: true };
const FMT_DURAS: Formato = { valor: (v) => `${v} series duras`, tick: (v) => String(v), cero: true };

// ---------------------------------------------------------------------------

/** Orden que fija la paleta: primero básicos de competición, luego alfabético. */
function useOrden(todos: SetRow[]): string[] {
  return useMemo(() => {
    const nombres = new Set(todos.map((s) => String(s.ejercicio ?? "").trim()).filter(Boolean));
    const comp = (COMPETICION as readonly string[]).filter((e) => nombres.has(e));
    const resto = [...nombres].filter((e) => !comp.includes(e)).sort();
    return [...comp, ...resto];
  }, [todos]);
}

export default function StrengthTrend({
  todos, rango, onExpand,
}: { todos: SetRow[]; rango: SetRow[]; onExpand?: () => void }) {
  const filas = useMemo(() => normalizar(rango), [rango]);
  const orden = useOrden(todos);
  const [activo, setActivo] = useState<string | null>(null);
  const agg = useMemo(() => aggEjercicios(filas, "basico", "peso"), [filas]);
  // PRs sobre TODO el historial (récord absoluto), no solo el rango dibujado.
  const pr = useMemo(() => prsDe(aggEjercicios(normalizar(todos), "basico", "peso")), [todos]);
  const basicos = useMemo(() => (COMPETICION as readonly string[]).filter((e) => (agg.get(e)?.size ?? 0) > 0), [agg]);
  return (
    <Panel title="Fuerza" subtitle="peso · básicos" onExpand={onExpand}>
      <div style={{ height: 229 }}>
        <Grafico agg={agg} keys={basicos} orden={orden} fmt={FMT_KG} height="100%" activo={activo} setActivo={setActivo} pr={pr} />
      </div>
      <div className="mt-1 text-[10px]" style={{ color: theme.muted }}>
        peso del top set por semana · ★ = récord · amplía para variantes, accesorios y e1RM
      </div>
    </Panel>
  );
}

export function StrengthExpanded({ todos, rango }: { todos: SetRow[]; rango: SetRow[] }) {
  const filas = useMemo(() => normalizar(rango), [rango]);
  const orden = useOrden(todos);
  const [cat, setCat] = useState<Categoria>("basico");
  const [metExc, setMetExc] = useState<MetExc>("peso");
  // Grupos: por defecto SERIES DURAS. El tonelaje se distorsiona al rotar ejercicios
  // (prensa mueve mucho más que unas elevaciones); una serie dura cuenta 1 dé igual
  // el ejercicio, así que progresa limpio (el landmark de volumen de hipertrofia).
  const [metAcc, setMetAcc] = useState<MetAcc>("duras");
  const [grupoSel, setGrupoSel] = useState<string | null>(null); // drill-down de accesorios
  const [activo, setActivo] = useState<string | null>(null);

  const cambiarCat = (c: Categoria) => { setCat(c); setGrupoSel(null); setActivo(null); };

  // modo de vista
  const esAcc = cat === "accesorio";
  const modo: "ejercicios" | "grupos" | "detalle" = !esAcc ? "ejercicios" : grupoSel ? "detalle" : "grupos";
  const usaMetExc = modo !== "grupos"; // grupos usa metAcc; el resto metExc

  const patrones = useMemo(
    () => [...new Set(filas.filter((f) => f.cat === "accesorio").map((f) => f.pat))].sort(),
    [filas],
  );
  // ejercicios de la categoría (o del grupo, en drill-down), más frecuentes primero
  const ejercicios = useMemo(() => {
    const cuenta = new Map<string, number>();
    for (const f of filas) {
      if (modo === "detalle") { if (f.cat !== "accesorio" || f.pat !== grupoSel) continue; }
      else if (f.cat !== cat) continue;
      cuenta.set(f.ejercicio, (cuenta.get(f.ejercicio) ?? 0) + 1);
    }
    return [...cuenta.entries()].sort((a, b) => b[1] - a[1]).map(([e]) => e);
  }, [filas, cat, modo, grupoSel]);

  const claves = modo === "grupos" ? patrones : ejercicios;
  const ordenClaves = modo === "grupos" ? patrones : orden;

  // visibilidad (toggle) por vista; en "grupos" el clic no filtra, entra al grupo
  const selKey = modo === "detalle" ? `acc:${grupoSel}` : cat;
  const [sel, setSel] = useState<Record<string, string[] | null>>({});
  const activos = modo === "grupos" ? patrones : (sel[selKey] ?? claves);
  const onClic = (k: string) => {
    if (modo === "grupos") { setGrupoSel(k); setActivo(null); return; }
    const next = activos.includes(k) ? activos.filter((x) => x !== k) : [...activos, k];
    setSel({ ...sel, [selKey]: next });
  };

  const agg = useMemo(() => {
    if (modo === "grupos") return aggGrupos(filas, metAcc);
    if (modo === "detalle") return aggEjercicios(filas, "accesorio", metExc, grupoSel!);
    return aggEjercicios(filas, cat, metExc);
  }, [filas, modo, cat, grupoSel, metAcc, metExc]);

  // PRs (★) solo en BÁSICOS y en métricas donde "más = mejor" (peso/e1RM). Variantes y
  // accesorios no llevan récord (rotan mucho y no son los levantamientos de referencia).
  const pr = useMemo(() => {
    if (cat !== "basico" || !(metExc === "peso" || metExc === "e1rm")) return undefined;
    return prsDe(aggEjercicios(normalizar(todos), "basico", metExc));
  }, [todos, cat, metExc]);

  const fmt = !usaMetExc ? (metAcc === "duras" ? FMT_DURAS : FMT_VOL)
    : metExc === "volumen" ? FMT_VOL : metExc === "e1rm" ? FMT_E1RM : FMT_KG;

  return (
    <div className="flex h-[74vh] flex-col">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg p-0.5" style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.14)" }}>
          {(["basico", "variante", "accesorio"] as Categoria[]).map((c) => (
            <button key={c} onClick={() => cambiarCat(c)} className="jarvis-seg font-display text-[10px] tracking-[0.2em]"
              style={{ color: cat === c ? theme.bg : theme.muted, background: cat === c ? theme.accent : "transparent" }}>
              {CATEGORIA_LABEL[c].toUpperCase()}
            </button>
          ))}
        </div>
        <div className="inline-flex rounded-lg p-0.5" style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.14)" }}>
          {(!usaMetExc
            ? ([["duras", "SERIES DURAS"], ["volumen", "VOLUMEN"]] as [MetAcc, string][]).map(([v, l]) => (
                <button key={v} onClick={() => setMetAcc(v)} className="jarvis-seg font-display text-[10px] tracking-[0.2em]"
                  style={{ color: metAcc === v ? theme.bg : theme.muted, background: metAcc === v ? theme.accent : "transparent" }}>{l}</button>
              ))
            : ([["peso", "PESO"], ["e1rm", "e1RM"], ["volumen", "VOLUMEN"]] as [MetExc, string][]).map(([v, l]) => (
                <button key={v} onClick={() => setMetExc(v)} className="jarvis-seg font-display text-[10px] tracking-[0.2em]"
                  style={{ color: metExc === v ? theme.bg : theme.muted, background: metExc === v ? theme.accent : "transparent" }}>{l}</button>
              )))}
        </div>
        {modo === "detalle" && (
          <button onClick={() => { setGrupoSel(null); setActivo(null); }} className="jarvis-chip" style={{ borderColor: "rgba(0,212,255,0.3)", color: theme.accent }}>
            ← grupos
          </button>
        )}
        <span className="text-[10px]" style={{ color: theme.muted }}>
          {modo === "grupos"
            ? (metAcc === "duras" ? "series duras por grupo · pincha un grupo para ver sus ejercicios" : "volumen por grupo · pincha un grupo para ver sus ejercicios")
            : modo === "detalle"
              ? `${grupoSel} · ${metExc === "peso" ? "peso del top set" : metExc === "e1rm" ? "e1RM" : "volumen"} por ejercicio`
              : metExc === "peso" ? "peso del top set por semana"
                : metExc === "e1rm" ? "1RM estimado (proyección) por semana" : "volumen total por semana"}
        </span>
      </div>

      <div className="mb-3">
        <div className="mb-1.5 text-[10px] uppercase tracking-[0.2em]" style={{ color: theme.muted }}>
          {modo === "grupos" ? "Grupo muscular (pincha para entrar)" : "Ejercicio"} · pasa el ratón por una línea para destacarla
        </div>
        <Chips items={claves} activos={activos} onToggle={onClic} color={(k) => colorDe(k, ordenClaves)} resaltar={setActivo} />
      </div>

      <div className="min-h-0 flex-1">
        <Grafico agg={agg} keys={activos} orden={ordenClaves} fmt={fmt} height="100%" activo={activo} setActivo={setActivo} pr={pr}
          onClave={modo === "grupos" ? (g) => { setGrupoSel(g); setActivo(null); } : undefined} />
      </div>

      <div className="mt-2 text-[11px]" style={{ color: theme.muted }}>
        {cat === "basico"
          ? `Levantamientos de competición: ${COMPETICION.join(", ")}.`
          : cat === "variante"
            ? "Variantes de los básicos. Cada una es un ejercicio distinto."
            : modo === "detalle"
              ? `Ejercicios del grupo "${grupoSel}". Vuelve con "← grupos".`
              : "Accesorios por grupo muscular. Pincha un grupo para ver sus ejercicios uno a uno."}
      </div>
    </div>
  );
}
