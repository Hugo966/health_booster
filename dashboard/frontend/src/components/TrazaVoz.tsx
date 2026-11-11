import { useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

import { theme } from "../lib/theme";
import { trazaVoz } from "../lib/voz";

// Visor de la traza de voz, en pantalla. Existe por el móvil: los fallos de escucha solo
// se explican viendo QUÉ oyó el reconocedor y CUÁNDO, y en el móvil no hay consola a la
// que asomarse (en el portátil basta con la de Chrome). Se enciende con
//   localStorage.setItem("jarvis.voz.debug", "1")
// y una recarga; apagado no se monta nada.
//
// Va por portal a `document.body` a propósito: `position: fixed` deja de anclarse a la
// ventana si algún antepasado tiene `transform`, y los paneles se amplían justo con
// transformaciones — dentro del árbol acabaría clavado en un sitio cualquiera.
export default function TrazaVoz() {
  const lineas = useSyncExternalStore(trazaVoz.suscribir, trazaVoz.lineas);
  // Plegable, y esto no es un adorno: en el móvil ocupaba la franja de abajo entera y
  // tapaba el chat y su campo de escribir, así que depurar la voz impedía usar a Jarvis.
  const [abierto, setAbierto] = useState(true);
  if (!trazaVoz.activa) return null;

  const texto = lineas.join("\n");

  return createPortal(
    <div
      style={{
        position: "fixed",
        left: 8,
        right: 8,
        bottom: 8,
        maxHeight: abierto ? "32vh" : undefined,
        zIndex: 9999,
        background: "rgba(0,0,0,0.86)",
        border: `1px solid ${theme.muted}`,
        borderRadius: 8,
        padding: "6px 8px",
        font: "11px/1.35 ui-monospace, SFMono-Regular, Menlo, monospace",
        color: "#d7e3ea",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <strong style={{ color: theme.muted }}>traza de voz</strong>
        <span style={{ color: theme.muted }}>{lineas.length}</span>
        <button
          type="button"
          data-no-expand
          onClick={() => void navigator.clipboard?.writeText(texto)}
          style={{
            marginLeft: "auto", border: `1px solid ${theme.muted}`, borderRadius: 6,
            padding: "2px 8px", background: "transparent", color: "#d7e3ea", font: "inherit",
          }}
        >
          copiar
        </button>
        <button
          type="button"
          data-no-expand
          onClick={() => setAbierto((v) => !v)}
          style={{
            border: `1px solid ${theme.muted}`, borderRadius: 6,
            padding: "2px 8px", background: "transparent", color: "#d7e3ea", font: "inherit",
          }}
        >
          {abierto ? "ocultar" : "ver"}
        </button>
        {/* Apagarla DESDE AQUÍ, y no solo con `?vozdebug=0`. La traza se guarda en el
            navegador, así que encenderla una vez para medir algo dejaba este cuadro
            para siempre; y en el móvil, con la app añadida a la pantalla de inicio, no
            hay barra de direcciones donde escribir el parámetro. O sea que se podía
            encender sin poder apagar. */}
        <button
          type="button"
          data-no-expand
          title="Apagar la traza"
          aria-label="Apagar la traza"
          onClick={() => {
            try { localStorage.removeItem("jarvis.voz.debug"); } catch { /* en privado */ }
            location.reload();
          }}
          style={{
            border: `1px solid ${theme.muted}`, borderRadius: 6,
            padding: "2px 8px", background: "transparent", color: "#d7e3ea", font: "inherit",
          }}
        >
          apagar
        </button>
      </div>
      {/* `column-reverse` mantiene lo último a la vista sin tener que medir el scroll. */}
      {abierto && (
        <div style={{ overflowY: "auto", display: "flex", flexDirection: "column-reverse" }}>
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {texto || "(sin nada todavía — toca el orbe y habla)"}
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}
