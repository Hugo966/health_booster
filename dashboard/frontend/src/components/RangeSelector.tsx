import { theme } from "../lib/theme";

export type Range = 7 | 14 | 30 | 90 | 365 | 0; // 0 = todo el histórico

export const RANGES: { v: Range; label: string }[] = [
  { v: 7, label: "7D" },
  { v: 14, label: "14D" },
  { v: 30, label: "30D" },
  { v: 90, label: "90D" },
  { v: 365, label: "1A" },
  { v: 0, label: "TODO" },
];

// Devuelve la fecha ISO mínima (inclusive) para un rango, o null si es "todo".
export function rangeStart(range: Range): string | null {
  if (range === 0) return null;
  const d = new Date();
  d.setDate(d.getDate() - range + 1);
  return d.toISOString().slice(0, 10);
}

export function inRange(fecha: string, start: string | null): boolean {
  return start === null || fecha >= start;
}

export default function RangeSelector({
  value,
  onChange,
}: {
  value: Range;
  onChange: (r: Range) => void;
}) {
  return (
    <div
      className="inline-flex rounded-lg p-0.5"
      style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.14)" }}
    >
      {RANGES.map((r) => {
        const on = r.v === value;
        return (
          <button
            key={r.v}
            onClick={() => onChange(r.v)}
            className="jarvis-seg font-display text-[10px] tracking-[0.2em]"
            style={{
              color: on ? theme.bg : theme.muted,
              background: on ? theme.accent : "transparent",
              boxShadow: on ? `0 0 14px rgba(0,212,255,0.45)` : "none",
            }}
          >
            {r.label}
          </button>
        );
      })}
    </div>
  );
}
