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
  // Si viene, el campo se pinta como RUEDA con este salto (0,1 kg el peso; 50 mg la
  // cafeína). Lo decide el backend, igual que los rangos.
  paso: number | null;
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

/** Lo guardado de ese día + dónde arranca la rueda (el último peso, la última cafeína).
 *  Las sugerencias van APARTE de los valores a propósito: no están guardadas y no se
 *  mandan si el usuario no toca la rueda, o darle a Guardar sin pesarse apuntaría el peso de
 *  la semana pasada como el de hoy.
 *
 *  `precargados` va al revés: tampoco está guardado, pero sale escrito y SÍ se manda sin
 *  tocarlo (el dolor que él mismo apuntó en el keep ese día). */
export async function fetchValores(
  tipo: TipoFormulario, fecha: string,
): Promise<{ valores: Valores; sugerencias: Valores; precargados: Valores }> {
  const r = await fetch(`${API_BASE}/formulario/${tipo}?fecha=${fecha}`);
  if (!r.ok) throw new Error("no pude leer ese día");
  const c = await r.json();
  return { valores: c.valores ?? {}, sugerencias: c.sugerencias ?? {},
           precargados: c.precargados ?? {} };
}

export type PlanPendientes = {
  pendientes: string[];
  /** Dónde arrancan las ruedas: la semana siguiente a la que acaba de entrenar. */
  sugerencia: { plani: number; bloque: number; semana: number };
  /** Los rangos de P/B/S los manda el backend, como los de los formularios. */
  campos: Campo[];
};

export async function fetchPlanPendientes(): Promise<PlanPendientes> {
  const r = await fetch(`${API_BASE}/plan/pendientes`);
  if (!r.ok) throw new Error("no pude leer las pestañas del plan");
  return r.json();
}

/** Dice qué semana es una pestaña del plan que el pipeline no supo colocar.
 *  `codigo` va de un tirón, P2B4S3, porque lo parsea el mismo `route_tab` del pipeline
 *  y así el panel no se inventa una sintaxis propia. Devuelve la confirmación en
 *  castellano para pintarla tal cual. */
export async function enrutarPestana(pestana: string, codigo: string): Promise<string> {
  const r = await fetch(`${API_BASE}/plan/enrutar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pestana, codigo }),
  });
  const c = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(c.detail ?? "no pude guardar esa pestaña");
  return c.ok ?? "Guardado.";
}

/** Guarda, corrige o VACÍA. Solo se mandan los campos con valor, y `borrar` nombra los
 *  que hay que dejar en blanco. Van por separado porque un campo vacío significa "no lo
 *  he contestado, déjalo como estaba": si las dos cosas viajaran igual, abrir el
 *  formulario y guardar borraría todo lo que no hubieras rellenado. */
export async function guardar(
  tipo: TipoFormulario,
  fecha: string,
  valores: Valores,
  borrar: string[] = [],
): Promise<{ valores: Valores; avisos: string[] }> {
  const r = await fetch(`${API_BASE}/formulario/${tipo}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fecha, ...valores, borrar }),
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
