// Ajustes: lo que configura QUIEN USA la app, no quien la instala.
//
// Existe porque un dato que solo se puede poner el primer día es un dato que no se puede
// corregir: si te equivocas de ciudad al teclearla, o te mudas, no había forma de volver
// atrás salvo tocar la hoja a mano.
//
// De momento vive aquí una sola cosa, la ubicación. Se queda en la cabecera y no como un
// panel más del dashboard a propósito: los paneles son para mirar datos, y esto se abre
// dos veces al año.
import { useEffect, useRef, useState } from "react";

import { theme } from "../lib/theme";
import { CampoUbicacion, useUbicacion } from "./Ubicacion";

export default function Ajustes() {
  const [abierto, setAbierto] = useState(false);
  const { lugar, tiempo, aplicar } = useUbicacion();
  const caja = useRef<HTMLDivElement>(null);

  // Cerrar al tocar fuera. `pointerdown` y no `click` porque en táctil el click llega
  // tarde y se queda el panel abierto bajo el dedo.
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: PointerEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("pointerdown", fuera);
    return () => document.removeEventListener("pointerdown", fuera);
  }, [abierto]);

  return (
    <div className="relative" ref={caja} data-no-expand>
      <button
        type="button"
        aria-label="Ajustes"
        aria-expanded={abierto}
        className="jarvis-chip px-2 py-1 text-[13px] leading-none"
        style={{ color: abierto ? theme.accent : theme.muted }}
        onClick={() => setAbierto((v) => !v)}
      >
        ⚙
      </button>

      {abierto && (
        <div
          className="absolute right-0 z-30 mt-2 w-[19rem] rounded-lg p-3 shadow-xl"
          style={{ background: theme.panel, border: "1px solid rgba(0,212,255,0.25)" }}
        >
          <div className="mb-2 font-display text-[10px] uppercase tracking-[0.3em]"
               style={{ color: theme.accent }}>
            Ajustes
          </div>

          <div className="text-[11px]" style={{ color: theme.text }}>Tu ubicación</div>
          <div className="mb-2 text-[10px]" style={{ color: theme.muted }}>
            Dirección, ciudad o código postal. Se usa para el tiempo.
          </div>

          <div className="mb-2 text-[10px]" style={{ color: theme.muted }}>
            {lugar
              ? <>Ahora: <span style={{ color: theme.text }}>{lugar.direccion || lugar.nombre}</span>
                  {tiempo && <> · {tiempo.cielo}, {tiempo.temp}°</>}</>
              : "Todavía sin poner."}
          </div>

          <CampoUbicacion onGuardado={aplicar} autoFoco />
        </div>
      )}
    </div>
  );
}
