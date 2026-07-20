// Cliente del backend. El backend vive en :8099 en este entorno (el :8000 lo
// ocupa otra app). Se puede sobreescribir con VITE_API_BASE.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8099";

// Una fila de derived_diario. Solo tipamos lo que consumimos; los NaN de la
// hoja llegan como string vacío "".
export type DerivedRow = {
  fecha: string;
  readiness?: number | "";
  [key: string]: unknown;
};

// Una serie de entreno_sets: una línea del Keep ya parseada y cruzada con el plan.
export type SetRow = {
  bloque: number | "";
  semana: number | "";
  dia: number | "";
  fecha: string;
  ejercicio: string;
  tipo: "básico" | "accesorio" | "";
  n_series: number | "";
  kg: number | "";
  reps: number | "";
  e1rm: number | "";
  volumen: number | "";
  [key: string]: unknown;
};

export type SesionRow = {
  fecha: string;
  bloque: number | "";
  semana: number | "";
  dia: number | "";
  volumen_total: number | "";
  n_series_total: number | "";
  vol_basicos: number | "";
  vol_accesorios: number | "";
  [key: string]: unknown;
};

export type SheetData = {
  derived_diario: DerivedRow[];
  entreno_sesion: SesionRow[];
  rm1: Record<string, unknown>[];
  peso: Record<string, unknown>[];
  entreno_sets: SetRow[];
};

export async function fetchData(): Promise<SheetData> {
  const r = await fetch(`${API_BASE}/data`);
  if (!r.ok) throw new Error(`API respondió ${r.status}`);
  return r.json();
}

// Convierte un valor de la hoja a número o null (los "" -> null, nunca 0 falso).
export function num(v: unknown): number | null {
  if (v === "" || v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}
