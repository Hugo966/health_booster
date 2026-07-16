import {
  Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import Panel from "./Panel";
import { anim, theme, tooltipStyle } from "../lib/theme";

// Widget 3.2 — HRV con banda de normalidad (media móvil 7d ± 1σ).
//
// La banda gris es "tu rango normal". Cada medición se colorea según dónde cae:
//   · por ENCIMA de la banda  → verde: HRV alto para ti, buena recuperación.
//   · DENTRO de la banda       → cian: lo esperable, normal.
//   · por DEBAJO de la banda   → rojo: caída respecto a tu base, posible fatiga/estrés.
// El eje es de días naturales: los días sin medición existen (punto gris) y la
// línea se corta, para que un hueco se vea como hueco y no como una caída.
const WINDOW = 7;
const MIN_PTS = 3;

type Row = { fecha: string; hrv: number | null };
type Zona = "alto" | "normal" | "bajo";

const COLOR_ZONA: Record<Zona, string> = {
  alto: theme.good,
  normal: theme.accent,
  bajo: theme.alert,
};
const FLECHA: Record<Zona, string> = { alto: "▲", normal: "●", bajo: "▼" };
const ETIQUETA: Record<Zona, string> = {
  alto: "por encima de tu rango",
  normal: "en tu rango normal",
  bajo: "por debajo de tu rango",
};
const ETIQUETA_CORTA: Record<Zona, string> = {
  alto: "por encima",
  normal: "en rango",
  bajo: "por debajo",
};

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Rellena los días ausentes entre la primera y la última fecha con hrv = null. */
function toDaily(rows: Row[]): Row[] {
  if (rows.length === 0) return [];
  const byDate = new Map(rows.map((r) => [r.fecha, r.hrv]));
  const out: Row[] = [];
  const last = rows[rows.length - 1].fecha;
  for (let d = rows[0].fecha; d <= last; d = addDays(d, 1)) {
    out.push({ fecha: d, hrv: byDate.get(d) ?? null });
  }
  return out;
}

type Point = {
  fecha: string;
  hrv: number | null;
  ausente: number | null; // punto gris a la altura de la media, si no hubo medición
  lower: number | null;
  band: number | null;    // altura de la banda (upper - lower), apilada sobre lower
  _lower: number | null;
  _upper: number | null;
};

function build(rows: Row[]): Point[] {
  const daily = toDaily(rows);
  return daily.map((r, i) => {
    const w = daily
      .slice(Math.max(0, i - WINDOW + 1), i + 1)
      .map((x) => x.hrv)
      .filter((v): v is number => v !== null);

    if (w.length < MIN_PTS)
      return { ...r, ausente: null, lower: null, band: null, _lower: null, _upper: null };

    const m = w.reduce((s, x) => s + x, 0) / w.length;
    const sd = Math.sqrt(w.reduce((s, x) => s + (x - m) ** 2, 0) / w.length);
    const lower = m - sd;
    return { ...r, ausente: r.hrv === null ? m : null, lower, band: 2 * sd, _lower: lower, _upper: lower + 2 * sd };
  });
}

function zonaDe(p: Point): Zona | null {
  if (p.hrv === null || p._lower === null || p._upper === null) return null;
  if (p.hrv > p._upper) return "alto";
  if (p.hrv < p._lower) return "bajo";
  return "normal";
}

/** Última medición y su zona: el "estado de hoy". */
function estadoHoy(data: Point[]): { hrv: number; zona: Zona } | null {
  for (let i = data.length - 1; i >= 0; i--) {
    if (data[i].hrv !== null) return { hrv: data[i].hrv!, zona: zonaDe(data[i]) ?? "normal" };
  }
  return null;
}

// A partir de cuántos días seguidos por debajo se avisa.
const RACHA_AVISO = 3;

/** Días seguidos por debajo de la banda, contando desde la última medición hacia
 *  atrás. Los días sin medir se saltan (no cuentan ni rompen la racha): un día sin
 *  reloj no debería resetear la alerta. */
function rachaBajo(data: Point[]): number {
  let n = 0;
  for (let i = data.length - 1; i >= 0; i--) {
    if (data[i].hrv === null) continue;
    if (zonaDe(data[i]) === "bajo") n++;
    else break;
  }
  return n;
}

/** Cuántos días seguidos llevas en la MISMA zona que la última medición (saltando
 *  los días sin medir). Es la base del veredicto "llevas X días así". */
function rachaZonaActual(data: Point[]): { zona: Zona; dias: number } | null {
  let zona: Zona | null = null;
  let dias = 0;
  for (let i = data.length - 1; i >= 0; i--) {
    if (data[i].hrv === null) continue;
    const z = zonaDe(data[i]) ?? "normal";
    if (zona === null) { zona = z; dias = 1; }
    else if (z === zona) dias++;
    else break;
  }
  return zona ? { zona, dias } : null;
}

/** Veredicto breve del AHORA: "llevas X días [estado]" + consejo, coloreado. */
function veredicto(data: Point[]): { texto: string; color: string; icono: string } | null {
  const rz = rachaZonaActual(data);
  if (!rz) return null;
  const { zona, dias } = rz;
  const d = dias === 1 ? "1 día" : `${dias} días`;
  if (zona === "alto")
    return { color: theme.good, icono: "▲", texto: `Llevas ${d} por encima de tu rango — bien, recuperado.` };
  if (zona === "normal")
    return { color: theme.accent, icono: "●", texto: `Llevas ${d} en tu rango normal — todo en orden.` };
  if (dias >= RACHA_AVISO)
    return { color: theme.alert, icono: "⚠", texto: `Llevas ${d} seguidos por debajo — ten cuidado: prioriza sueño y baja la carga.` };
  return { color: theme.amber, icono: "▼", texto: `Llevas ${d} por debajo de tu rango — vigila si se repite.` };
}

const fmtDay = (f: string) => f.slice(8, 10) + "/" + f.slice(5, 7);

// Día de la semana + fecha, para el tooltip (ver en qué día se descansa mejor).
const DIAS = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const fechaConDia = (f: string) => {
  const d = new Date(f + "T00:00:00");
  return `${DIAS[d.getDay()]} · ${fmtDay(f)}`;
};

// Tooltip a medida. El de Recharts pintaba las series internas de la banda
// ("lower :" = borde inferior, "band :" = altura 2σ) como texto vacío. Aquí se
// muestra lo legible: día de la semana, HRV coloreado por zona y —lo que antes
// eran esos campos crípticos— tu rango normal de ESE día (inferior–superior).
function TooltipHrv({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const row: Point = payload[0]?.payload ?? {};
  const hrv = row.hrv;
  const z = zonaDe(row);
  const colorHrv = hrv == null ? theme.muted : z ? COLOR_ZONA[z] : theme.text;
  return (
    <div style={{ ...tooltipStyle.contentStyle, padding: "6px 10px" }}>
      <div style={tooltipStyle.labelStyle}>{fechaConDia(String(label))}</div>
      <div style={{ color: colorHrv, fontSize: 12, fontWeight: 600 }}>
        {hrv == null ? "sin medición" : `HRV ${Math.round(hrv)}`}
        {hrv != null && z && <span style={{ fontWeight: 400 }}> · {ETIQUETA_CORTA[z]}</span>}
      </div>
      {row._lower != null && row._upper != null && (
        <div style={{ color: theme.muted, fontSize: 11, marginTop: 2 }}>
          tu rango normal: {Math.round(row._lower)}–{Math.round(row._upper)}
        </div>
      )}
    </div>
  );
}

function Punto({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function Leyenda() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px]" style={{ color: theme.muted }}>
      <Punto color={theme.good} label="encima = bien" />
      <Punto color={theme.accent} label="dentro = normal" />
      <Punto color={theme.alert} label="debajo = ojo" />
      <span>· banda = tu rango normal (7d ± 1σ)</span>
    </div>
  );
}

function Chart({ data, height }: { data: Point[]; height: number | string }) {
  const lastIdx = data.length - 1;

  // El dominio se calcula sobre los HRV y los bordes de la banda. Si se deja en
  // "dataMin/dataMax", Recharts mete también `band` (la ALTURA de la banda, ~2σ)
  // en el cálculo y el eje baja hasta casi cero.
  const ys = data.flatMap((d) =>
    [d.hrv, d._lower, d._upper].filter((v): v is number => v !== null),
  );
  const dom: [number, number] = ys.length
    ? [Math.floor((Math.min(...ys) - 5) / 10) * 10, Math.ceil((Math.max(...ys) + 5) / 10) * 10]
    : [0, 100];

  // Cada punto se pinta según su zona; el último, más grande y con brillo.
  const renderDot = (props: any) => {
    const { cx, cy, payload, index } = props;
    if (cx == null || cy == null || payload.hrv === null) return <g key={`e${index}`} />;
    const z = zonaDe(payload);
    const color = z ? COLOR_ZONA[z] : theme.accent;
    const isLast = index === lastIdx;
    const r = isLast ? 4.5 : 2.4;
    return (
      <circle
        key={index} cx={cx} cy={cy} r={r} fill={color}
        stroke={theme.bg} strokeWidth={isLast ? 1.5 : 0}
        style={isLast ? { filter: `drop-shadow(0 0 6px ${color})` } : undefined}
      />
    );
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={theme.grid} vertical={false} />
        <XAxis
          dataKey="fecha" tickFormatter={fmtDay} minTickGap={28}
          tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid}
        />
        <YAxis
          width={34} domain={dom} allowDataOverflow
          tick={{ fill: theme.muted, fontSize: 10 }} stroke={theme.grid}
        />
        <Tooltip content={<TooltipHrv />} />
        {/* banda = dos áreas apiladas: la inferior invisible, la de altura visible */}
        <Area dataKey="lower" stackId="baseline" stroke="none" fill="transparent" isAnimationActive={false} />
        <Area
          dataKey="band" stackId="baseline" stroke="none" fill={theme.accent} fillOpacity={0.1}
          isAnimationActive={false}
        />
        {/* días sin medición: punto gris a la altura de la media */}
        <Line
          dataKey="ausente" stroke="none" isAnimationActive={false} activeDot={false}
          dot={{ r: 1.8, fill: theme.muted, stroke: "none" } as any}
        />
        <Line
          dataKey="hrv" stroke={theme.accent} strokeWidth={1.8} connectNulls={false}
          dot={renderDot} activeDot={{ r: 5 }} isAnimationActive={anim.on} animationDuration={anim.ms}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function HrvTrend({ rows, onExpand }: { rows: Row[]; onExpand?: () => void }) {
  const data = build(rows);
  const hoy = estadoHoy(data);
  const racha = rachaBajo(data);
  return (
    <Panel
      title="HRV"
      subtitle={
        racha >= RACHA_AVISO ? (
          <span style={{ color: theme.alert, fontWeight: 600 }}>
            ⚠ {racha} días seguidos por debajo
          </span>
        ) : (
          hoy && (
            <span style={{ color: COLOR_ZONA[hoy.zona] }}>
              hoy {Math.round(hoy.hrv)} {FLECHA[hoy.zona]} {ETIQUETA_CORTA[hoy.zona]}
            </span>
          )
        )
      }
      onExpand={onExpand}
    >
      <div style={{ height: 182 }}>
        {data.length === 0 ? (
          <div className="flex h-full items-center" style={{ color: theme.muted }}>—</div>
        ) : (
          <Chart data={data} height="100%" />
        )}
      </div>
      <div className="mt-1.5">
        <Leyenda />
      </div>
    </Panel>
  );
}

export function HrvExpanded({ rows }: { rows: Row[] }) {
  const data = build(rows);
  if (data.length === 0) return <div style={{ color: theme.muted }}>Sin datos de HRV en este rango.</div>;

  const alto = data.filter((d) => zonaDe(d) === "alto").length;
  const normal = data.filter((d) => zonaDe(d) === "normal").length;
  const bajo = data.filter((d) => zonaDe(d) === "bajo").length;
  const sinMedir = data.filter((d) => d.hrv === null).length;
  const hoy = estadoHoy(data);
  const vered = veredicto(data);
  const medidos = alto + normal + bajo;

  // Recuento del periodo: es un HISTÓRICO, no una alarma. Sin coletillas de aviso
  // ("ojo: posible fatiga") que hagan pensar que hay que actuar sobre días viejos.
  const Contador = ({ color, arrow, titulo, n }: { color: string; arrow: string; titulo: string; n: number }) => (
    <div
      className="flex items-baseline gap-2 rounded-lg px-3 py-2"
      style={{ background: `${color}14`, border: `1px solid ${color}33` }}
    >
      <span className="font-display text-xl" style={{ color }}>{n}</span>
      <span className="text-[11px]" style={{ color }}>{arrow} {titulo}</span>
    </div>
  );

  return (
    <div className="flex h-[72vh] flex-col">
      <p className="mb-3 max-w-3xl text-xs leading-relaxed" style={{ color: theme.muted }}>
        La <b style={{ color: theme.text }}>banda gris</b> es tu rango normal de HRV: la media de los
        últimos 7 días ± 1 desviación típica. El HRV alto suele indicar buena recuperación; una caída
        <b style={{ color: theme.alert }}> por debajo</b> de tu rango es señal de fatiga, estrés, mal
        sueño o algo incubándose. Presta atención si encadenas <b style={{ color: theme.text }}>3 o más</b> días
        seguidos por debajo.
        {hoy && (
          <>
            {" "}Hoy estás en <b style={{ color: COLOR_ZONA[hoy.zona] }}>{Math.round(hoy.hrv)}, {ETIQUETA[hoy.zona]}</b>.
          </>
        )}
      </p>

      {/* valoración breve del ahora, en su propia línea */}
      {vered && (
        <div
          className="mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
          style={{ background: `${vered.color}14`, border: `1px solid ${vered.color}44` }}
        >
          <span style={{ color: vered.color }}>{vered.icono}</span>
          <span style={{ color: vered.color }}><b>{vered.texto}</b></span>
        </div>
      )}

      <div className="mb-1 text-[10px] uppercase tracking-[0.15em]" style={{ color: theme.muted }}>
        Reparto de los {medidos} días medidos del periodo{sinMedir > 0 ? ` (+${sinMedir} sin medir)` : ""}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Contador color={theme.good} arrow="▲" titulo="por encima" n={alto} />
        <Contador color={theme.accent} arrow="●" titulo="en rango" n={normal} />
        <Contador color={theme.alert} arrow="▼" titulo="por debajo" n={bajo} />
        {sinMedir > 0 && <Contador color={theme.muted} arrow="·" titulo="sin medir" n={sinMedir} />}
      </div>

      <div className="min-h-0 flex-1">
        <Chart data={data} height="100%" />
      </div>
      <div className="mt-2">
        <Leyenda />
      </div>
    </div>
  );
}
