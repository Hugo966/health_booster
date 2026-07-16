// Paleta Jarvis: fondo oscuro, acento cian. El acento fuerte se reserva para los
// datos; el marco se queda en cianes muy diluidos.
export const theme = {
  bg: "#0a0e1a",
  panel: "#0e1424",
  accent: "#00d4ff",
  alert: "#ff4757",
  amber: "#ffa502",
  good: "#2ed573",
  text: "#e6edf3",
  muted: "#7a8699",
  grid: "rgba(0,212,255,0.07)",
} as const;

// Serie de colores para múltiples series (fuerza, patrones de accesorios). El
// orden importa: los primeros se usan más y en barras apiladas quedan adyacentes,
// así que ningún par consecutivo puede compartir tono. Cian y violeta abren, y el
// resto se separa por matiz, no por luminosidad.
export const PALETTE = [
  "#00d4ff", "#7b61ff", "#2ed573", "#ffa502",
  "#ff6b81", "#ffdd59", "#00e5c0", "#c56cf0",
  "#4bcffa", "#ff7f50", "#a4b0be", "#f8a5c2",
] as const;

// Estilo de tarjeta compartido (Panel + hero Readiness).
export const panelStyle = {
  background: "linear-gradient(180deg, #101a2e 0%, #0c1220 100%)",
  border: "1px solid rgba(0,212,255,0.12)",
  boxShadow:
    "0 0 24px rgba(0,212,255,0.05), 0 10px 30px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.03)",
} as const;

// Estilo de tooltip compartido en todos los gráficos.
export const tooltipStyle = {
  contentStyle: {
    background: "rgba(10,16,30,0.94)",
    border: "1px solid rgba(0,212,255,0.28)",
    borderRadius: 8,
    boxShadow: "0 0 24px rgba(0,212,255,0.12)",
    fontSize: 12,
  },
  labelStyle: { color: theme.accent, fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: theme.text },
} as const;

// Animación de los gráficos. Recharts anima con JS (un clip-path que se abre), así
// que no basta con la @media de CSS: hay que apagarla desde aquí. Quien tenga
// activado "reducir movimiento" en su sistema ve los datos al instante.
const sinMovimiento =
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const anim = {
  on: !sinMovimiento,
  ms: sinMovimiento ? 0 : 2000,
  msBar: sinMovimiento ? 0 : 1500,
} as const;

// Bandas de readiness (0-100): rojo <40, ámbar 40-65, verde >65.
export function readinessBand(v: number): { color: string; label: string } {
  if (v < 40) return { color: theme.alert, label: "COOKED" };
  if (v <= 65) return { color: theme.amber, label: "CAUTION" };
  return { color: theme.good, label: "READY" };
}
