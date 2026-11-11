// Clasificación de ejercicios para el panel de Fuerza.
//
// El pipeline ya marca `tipo` = básico | accesorio leyéndolo del plan. Pero dentro
// de los básicos hay dos cosas distintas para un powerlifter: los tres levantamientos
// que compites y sus variantes de entrenamiento. Esta distinción no está en la hoja,
// vive aquí.
//
// Para cambiar qué cuenta como levantamiento de competición, edita COMPETICION.
// Las variantes NUNCA se fusionan con su básico: Banca comp ≠ Banca 3ct ≠ Banca mid grip.

export const COMPETICION = ["Sentadilla LB", "Banca comp", "Sumo dl"] as const;

export type Categoria = "basico" | "variante" | "accesorio";

export function categoria(ejercicio: string, tipo: string): Categoria {
  if (tipo !== "básico") return "accesorio";
  return (COMPETICION as readonly string[]).includes(ejercicio) ? "basico" : "variante";
}

export const CATEGORIA_LABEL: Record<Categoria, string> = {
  basico: "Básicos",
  variante: "Variantes",
  accesorio: "Accesorios",
};

// Patrón de movimiento, para agrupar accesorios (donde importa el volumen, no el
// e1RM). Se evalúa EN ORDEN: la primera regla que casa gana. Por eso "peck deck
// inverso" (deltoide posterior) va antes que "peck deck" (pectoral).
const PATRONES: [RegExp, string][] = [
  [/elevaciones lat|peck deck inverso|hombro posterior|w slides|y raises/i, "Hombro"],
  [/plancha|abd|core|crunch|pallof|hollow|copenhague/i, "Core"],
  [/femoral|hip thrust|pull through|hiperextens|reverse hyper|monster walk|glúteo|gluteo/i, "Cadena posterior"],
  [/sentadilla|squat|^sq |prensa|leg extension|split sq|step down|búlgara|bulgara|cuádriceps|cuadriceps/i, "Pierna"],
  [/banca|press militar|peck deck|floor press|fondo|tríceps|triceps|katana|cruce de poleas/i, "Empuje"],
  [/remo|jalón|jalon|dominada|pull over|face pull|retracc|curl/i, "Tracción"],
];

export function patron(ejercicio: string): string {
  for (const [rx, label] of PATRONES) if (rx.test(ejercicio)) return label;
  return "Otros";
}

// Etiqueta corta del microciclo: "P2B1S1" (plan, bloque, semana). La P desambigua
// porque el usuario reinicia bloque/semana con cada plan. Sin plani conocido, cae a "B4S2".
export function bloqueSemana(bloque: number, semana: number, plani?: number | null): string {
  return `${plani != null ? `P${plani}` : ""}B${bloque}S${semana}`;
}
export function bsOrden(bloque: number, semana: number): number {
  return bloque * 100 + semana;
}
