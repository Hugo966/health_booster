// Cliente de los formularios diarios (AM, PM, peso). Hasta la Fase 2 el dashboard solo
// LEÍA la hoja; estos son los primeros endpoints que escriben en ella.
//
// Los rangos de cada campo NO se declaran aquí: vienen del backend (`/formularios/esquema`,
// que los saca de `formularios.ESQUEMA`). Duplicarlos en el frontend es justo cómo se
// acaba ofreciendo un 1-10 en una escala que es 1-9, y eso rompe el readiness en silencio.
import { API_BASE } from "./api";

export type TipoFormulario = "am" | "pm" | "peso";

export type Campo = {
  nombre: string;
  etiqueta: string;
  tipo: "entero" | "decimal" | "hora" | "texto" | "zonas";
  minimo: number | null;
  maximo: number | null;
  ayuda: string;
};

export type Esquema = {
  am: { titulo: string; campos: Campo[] };
  pm: { titulo: string; campos: Campo[] };
  peso: { titulo: string; campos: Campo[] };
  zonas: string[];
};

export type Fuente = {
  etiqueta: string;
  estado: "ok" | "pendiente" | "falta" | "aviso" | "no_disponible";
  detalle: string;
  faltan?: string[];
  ultima?: string | null;
};

export type EstadoFormularios = {
  hoy: string;
  color: "verde" | "ambar" | "rojo";
  resumen: string;
  fuentes: Record<string, Fuente>;
  dias: { fecha: string; am: boolean; pm: boolean; entreno: boolean; sin_keep: boolean; cerrado: boolean }[];
};

export type Valores = Record<string, string | number>;

export async function fetchEsquema(): Promise<Esquema> {
  const r = await fetch(`${API_BASE}/formularios/esquema`);
  if (!r.ok) throw new Error("no pude leer el esquema de formularios");
  return r.json();
}

export async function fetchEstado(dias = 14): Promise<EstadoFormularios> {
  const r = await fetch(`${API_BASE}/formularios/estado?dias=${dias}`);
  if (!r.ok) throw new Error("no pude leer el estado de los formularios");
  return r.json();
}

export async function fetchValores(tipo: TipoFormulario, fecha: string): Promise<Valores> {
  const r = await fetch(`${API_BASE}/formulario/${tipo}?fecha=${fecha}`);
  if (!r.ok) throw new Error("no pude leer ese día");
  return (await r.json()).valores ?? {};
}

/** Guarda o corrige. Solo se mandan los campos con valor: lo demás no se toca. */
export async function guardar(
  tipo: TipoFormulario,
  fecha: string,
  valores: Valores,
): Promise<{ valores: Valores; avisos: string[] }> {
  const r = await fetch(`${API_BASE}/formulario/${tipo}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fecha, ...valores }),
  });
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    // El backend manda el mensaje ya en español y apuntando al campo concreto.
    throw new Error(cuerpo.detail ?? "no pude guardar");
  }
  return cuerpo;
}

export const hoyISO = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
