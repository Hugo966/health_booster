import type { Accion } from "./chat";

// Reproductor de las acciones de UI que devuelve Jarvis. v1 MÍNIMO: solo navegación
// de paneles (abrir/cerrar), que es lo que hace falta para "muéstrame el sueño".
// `resaltar`, gráficos ad-hoc y tours guiados llegarán con el reproductor completo
// (interrumpible); aquí, si llega una acción que aún no soportamos, se ignora sin
// romper. Sirve tanto a la voz como al chat escrito.
//
// La navegación real la hace App (mismo mecanismo que el hash: useWidgetEnHash), así
// que este módulo no toca el DOM: recibe una API {abrir, cerrar} y solo traduce.

// Los paneles que el backend puede pedir abrir (HERRAMIENTAS_UI en chat.py). Se
// valida contra esta lista para no navegar a un hash inventado.
const PANELES = new Set([
  "readiness", "hrv", "sueno", "carga", "fuerza", "peso", "correlaciones",
  "formularios",
]);

export type ReproductorAPI = {
  abrir: (panel: string) => void;
  cerrar: () => void;
};

export function reproducir(acciones: Accion[], api: ReproductorAPI): void {
  for (const a of acciones) {
    if (a.tipo === "abrir_panel" && typeof a.panel === "string" && PANELES.has(a.panel)) {
      api.abrir(a.panel);
    } else if (a.tipo === "cerrar_panel") {
      api.cerrar();
    }
    // resaltar / grafico / tour: todavía no (no-op). No lanzar: que una acción futura
    // no reviente el turno; simplemente se ignora hasta que exista su reproductor.
  }
}
