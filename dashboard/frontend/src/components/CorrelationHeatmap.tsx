import { Fragment, type ReactNode } from "react";
import Panel from "./Panel";
import { theme } from "./../lib/theme";
import { spearman } from "./../lib/stats";
import { num, type DerivedRow } from "./../lib/api";

// Widget 3.7 — Correlaciones (Spearman) entre pares clave, agrupadas en dos bloques:
// estilo de vida y entreno. Requiere ≥14 puntos emparejados; si no, la celda muestra
// "n insuf" en vez de un número inventado. Color divergente cian↔rojo, intensidad por |r|.
const MIN_N = 14;
// Umbral para que una correlación cuente como "representativa" en la reflexión: al menos débil.
const R_SIGNIF = 0.2;

type Bloque = "vida" | "entreno";
type Par = {
  a: string; b: string; label: string; bloque: Bloque;
  // Lectura en lenguaje llano según el signo observado. Plantilla fija (sin IA): es la
  // reflexión "tonta" que en Fase 2 podrá sustituir/enriquecer Jarvis con IA.
  interp: (r: number) => string;
  // ¿Es buena noticia? true=verde, false=rojo, null=ambigua/ojo (ámbar). Para colorear la reflexión.
  bueno: (r: number) => boolean | null;
};

// Carga en sRPE (RPE de sesión × nº de series; NO depende de la duración de Intervals,
// que casi no existe para powerlifting). Se cruzan las dos vistas de carga: el sRPE del
// DÍA (dureza puntual; con pocos días de RPE de sesión aún suele salir "n insuf") y el
// sRPE acumulado de 7 DÍAS (fatiga de la semana). El tonelaje se retiró: premia el volumen.
const PARES: Par[] = [
  { a: "sueno_horas_ayer", b: "sensacion_am", label: "Sueño ayer × sensación AM", bloque: "vida",
    interp: (r) => r >= 0 ? "que dormir más se asocia a mejores mañanas" : "que dormir más se asocia a peores mañanas",
    bueno: (r) => r >= 0 },
  { a: "hrv_ayer", b: "readiness", label: "HRV ayer × readiness", bloque: "vida",
    interp: (r) => r >= 0 ? "que un buen HRV precede a más readiness" : "que un buen HRV precede a menos readiness",
    bueno: (r) => r >= 0 },
  { a: "cafeina_ayer_mg", b: "sueno_horas", label: "Cafeína ayer × sueño", bloque: "vida",
    interp: (r) => r >= 0 ? "que más cafeína coincide con dormir más" : "que más cafeína coincide con dormir menos",
    bueno: (r) => r >= 0 },
  { a: "alcohol_ayer", b: "hrv_rmssd", label: "Alcohol ayer × HRV", bloque: "vida",
    interp: (r) => r >= 0 ? "que el alcohol coincide con mejor HRV" : "que el alcohol coincide con peor recuperación (HRV más bajo)",
    bueno: (r) => r >= 0 },
  { a: "sRPE", b: "readiness", label: "sRPE día × readiness", bloque: "entreno",
    interp: (r) => r >= 0 ? "que las sesiones más duras coinciden con más readiness" : "que las sesiones más duras coinciden con menos readiness",
    bueno: () => null },
  { a: "sRPE_7d", b: "readiness", label: "sRPE 7d × readiness", bloque: "entreno",
    interp: (r) => r >= 0 ? "que más carga semanal coincide con más readiness" : "que más carga semanal coincide con menos readiness",
    bueno: (r) => r >= 0 },
  { a: "sRPE", b: "molestias_nivel", label: "sRPE día × molestias", bloque: "entreno",
    interp: (r) => r >= 0 ? "que las sesiones más duras coinciden con más molestias" : "que las sesiones más duras coinciden con menos molestias",
    bueno: () => null },
  { a: "sRPE_7d", b: "molestias_nivel", label: "sRPE 7d × molestias", bloque: "entreno",
    interp: (r) => r >= 0 ? "que las semanas de más carga coinciden con más molestias" : "que las semanas de más carga coinciden con menos molestias (posible causa inversa: al doler, descargas)",
    bueno: () => null },
];

const BLOQUES: { id: Bloque; titulo: string; nombre: string }[] = [
  { id: "vida", titulo: "Estilo de vida", nombre: "estilo de vida" },
  { id: "entreno", titulo: "Entreno", nombre: "entreno" },
];

const FUERZAS = ["insignificante", "débil", "moderada", "fuerte", "muy fuerte"] as const;
// Escala rojo→verde para la etiqueta de fuerza: insignificante = rojo, fuerte = verde.
const FUERZA_COLOR = ["#ff4757", "#ff7f50", "#ffa502", "#7bed9f", "#2ed573"] as const;

const nivelFuerza = (r: number) => {
  const a = Math.abs(r);
  return a < 0.2 ? 0 : a < 0.4 ? 1 : a < 0.6 ? 2 : a < 0.8 ? 3 : 4;
};
const fuerza = (r: number) => FUERZAS[nivelFuerza(r)];
const fuerzaColor = (r: number) => FUERZA_COLOR[nivelFuerza(r)];

const valColor = (v: boolean | null) => (v === true ? theme.good : v === false ? theme.alert : theme.amber);

function corrColor(r: number): string {
  const t = Math.min(1, Math.abs(r));
  const base = r >= 0 ? "0,212,255" : "255,71,87";
  return `rgba(${base},${(0.12 + 0.55 * t).toFixed(2)})`;
}

type Cell = { par: Par; n: number; r: number | null };

function calcular(rows: DerivedRow[]): Cell[] {
  return PARES.map((par) => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const row of rows) {
      const va = num(row[par.a]);
      const vb = num(row[par.b]);
      if (va !== null && vb !== null) { xs.push(va); ys.push(vb); }
    }
    const n = xs.length;
    if (n < MIN_N) return { par, n, r: null };
    const r = spearman(xs, ys);
    return { par, n, r: Number.isFinite(r) ? r : null };
  });
}

/** Las `k` celdas más representativas de un bloque: primero las que tienen dato, de
 *  mayor a menor |r|; luego se rellena con las de "n insuf" (mayor n primero). */
function representativas(cells: Cell[], k: number): Cell[] {
  const conNumero = cells.filter((c) => c.r !== null).sort((a, b) => Math.abs(b.r!) - Math.abs(a.r!));
  const sinNumero = cells.filter((c) => c.r === null).sort((a, b) => b.n - a.n);
  return [...conNumero, ...sinNumero].slice(0, k);
}

/** Reflexión determinista del bloque (plantilla, sin IA): nombra las correlaciones
 *  representativas (n≥MIN_N y |r|≥R_SIGNIF, de más a menos fuerte), coloreando en
 *  verde/rojo/ámbar según sean buena, mala o ambigua noticia. */
function Reflexion({ nombre, cells }: { nombre: string; cells: Cell[] }) {
  const base = { color: theme.text };
  const conNumero = cells.filter((c) => c.r !== null);
  if (conNumero.length === 0)
    return <span style={base}>Aún no hay datos suficientes en {nombre} para sacar conclusiones; se irán rellenando según registres.</span>;
  const signif = conNumero
    .filter((c) => Math.abs(c.r!) >= R_SIGNIF)
    .sort((a, b) => Math.abs(b.r!) - Math.abs(a.r!));
  if (signif.length === 0)
    return <span style={base}>De momento ninguna relación de {nombre} destaca (todas por debajo de |{R_SIGNIF.toFixed(2)}|): sin señales claras todavía.</span>;
  return (
    <span style={base}>
      Las medidas representativas ahora mismo en cuanto a {nombre} son{" "}
      {signif.map((c, i) => (
        <Fragment key={c.par.label}>
          {i > 0 && (i === signif.length - 1 ? " y " : ", ")}
          <b style={{ color: valColor(c.par.bueno(c.r!)) }}>
            {c.par.label} ({c.r! >= 0 ? "+" : "−"}{Math.abs(c.r!).toFixed(2)}, {fuerza(c.r!)})
          </b>
        </Fragment>
      ))}
      , e indican{" "}
      {signif.map((c, i) => (
        <Fragment key={c.par.label}>
          {i > 0 ? "; " : ""}
          <span style={{ color: valColor(c.par.bueno(c.r!)) }}>{c.par.interp(c.r!)}</span>
        </Fragment>
      ))}.
    </span>
  );
}

function Celda({ c, grande = false }: { c: Cell; grande?: boolean }) {
  return (
    <div
      className="jarvis-cell flex flex-col justify-between rounded-lg p-3"
      style={{
        minHeight: grande ? 130 : 84,
        background: c.r !== null ? corrColor(c.r) : "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
      title={`${c.n} días con ambos valores`}
    >
      <div className={grande ? "text-sm leading-tight" : "text-[11px] leading-tight"} style={{ color: theme.text }}>
        {c.par.label}
      </div>
      {c.r !== null ? (
        <div>
          <div className="font-display" style={{ color: theme.text, fontSize: grande ? 40 : 24 }}>
            {c.r >= 0 ? "+" : ""}{c.r.toFixed(2)}
          </div>
          <div className="text-[10px] flex items-center gap-1" style={{ color: theme.muted }}>
            n = {c.n} ·
            <span
              style={{
                width: 6, height: 6, borderRadius: "50%", background: fuerzaColor(c.r),
                boxShadow: `0 0 5px ${fuerzaColor(c.r)}`, display: "inline-block",
              }}
            />
            <span style={{ color: fuerzaColor(c.r), letterSpacing: 0.5, textTransform: "uppercase" }}>{fuerza(c.r)}</span>
          </div>
        </div>
      ) : (
        <div className="text-xs" style={{ color: theme.muted }}>n insuf ({c.n})</div>
      )}
    </div>
  );
}

/** Encabezado de bloque con barrita de acento (mismo estilo HUD que el resto). */
function Titulo({ children }: { children: ReactNode }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span style={{ width: 3, height: 12, background: theme.accent, borderRadius: 2, opacity: 0.8 }} />
      <span className="text-[11px]" style={{ color: theme.accent, letterSpacing: 1.5, textTransform: "uppercase" }}>
        {children}
      </span>
    </div>
  );
}

export default function CorrelationHeatmap({ rows, onExpand }: { rows: DerivedRow[]; onExpand?: () => void }) {
  const cells = calcular(rows);
  const listos = cells.filter((c) => c.r !== null).length;
  // Cerrado: las 2 más representativas de cada bloque (2×2, una columna por bloque) →
  // panel a la altura de los demás. El detalle completo está al desplegar.
  return (
    <Panel title="Correlaciones" subtitle="Spearman" onExpand={onExpand}>
      <div className="grid grid-cols-2 gap-2">
        {BLOQUES.map((bl) => (
          <div key={bl.id} className="flex flex-col gap-2">
            <div className="text-[9px]" style={{ color: theme.accent, letterSpacing: 1.2, textTransform: "uppercase" }}>
              {bl.titulo}
            </div>
            {representativas(cells.filter((c) => c.par.bloque === bl.id), 2).map((c) => (
              <Celda key={c.par.label} c={c} />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-2 text-[10px]" style={{ color: theme.muted }}>
        {listos}/{cells.length} con ≥{MIN_N} días · abre para ver todas
      </div>
    </Panel>
  );
}

export function CorrelationExpanded({ rows }: { rows: DerivedRow[] }) {
  const cells = calcular(rows);
  const faltan = cells.filter((c) => c.r === null);
  return (
    <div className="flex flex-col gap-6">
      <div className="text-xs leading-relaxed" style={{ color: theme.muted }}>
        Correlación de Spearman sobre rangos: mide si dos variables suben y bajan juntas,
        aguantando los valores extremos mejor que Pearson. Solo cuentan los días en que
        <b style={{ color: theme.text }}> ambas</b> tienen dato. Por debajo de {MIN_N} pares
        no se muestra número: con tan pocos puntos, cualquier correlación es ruido.
        <b style={{ color: theme.text }}> Correlación no es causalidad.</b>
      </div>
      {BLOQUES.map((bl) => {
        const cs = cells.filter((c) => c.par.bloque === bl.id);
        return (
          <div key={bl.id}>
            <Titulo>{bl.titulo}</Titulo>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {cs.map((c) => <Celda key={c.par.label} c={c} grande />)}
            </div>
            <div className="mt-3 text-sm leading-relaxed">
              <Reflexion nombre={bl.nombre} cells={cs} />
            </div>
          </div>
        );
      })}
      {faltan.length > 0 && (
        <div className="text-xs" style={{ color: theme.muted }}>
          Faltan datos en: {faltan.map((c) => `${c.par.label} (${c.n}/${MIN_N})`).join(" · ")}.
          Se van rellenando solos según sigas registrando formularios.
        </div>
      )}
    </div>
  );
}
