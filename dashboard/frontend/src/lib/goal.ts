import { useCallback, useEffect, useState } from "react";

// Objetivo de peso. Vive en el navegador (localStorage): el dashboard solo LEE de
// la hoja, nunca escribe, así que las preferencias no pueden ir allí.
export type Direccion = "subir" | "bajar";
export type Objetivo = { direccion: Direccion; meta: number | null };

const KEY = "jarvis.peso.objetivo";
const DEFAULT: Objetivo = { direccion: "subir", meta: null };

function load(): Objetivo {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const o = JSON.parse(raw);
    return {
      direccion: o.direccion === "bajar" ? "bajar" : "subir",
      meta: typeof o.meta === "number" && Number.isFinite(o.meta) ? o.meta : null,
    };
  } catch {
    return DEFAULT;
  }
}

export function useObjetivoPeso(): [Objetivo, (o: Objetivo) => void] {
  const [obj, setObj] = useState<Objetivo>(load);
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch { /* modo privado */ }
  }, [obj]);
  return [obj, useCallback((o: Objetivo) => setObj(o), [])];
}

/** Verde si el cambio va en la dirección deseada, rojo si va al revés. */
export function colorDelta(delta: number, direccion: Direccion, good: string, bad: string, neutral: string): string {
  if (Math.abs(delta) < 0.05) return neutral;
  const bien = direccion === "subir" ? delta > 0 : delta < 0;
  return bien ? good : bad;
}
