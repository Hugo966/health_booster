import { useEffect, useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";
import { anim, theme } from "../lib/theme";
import { BackIcon } from "./Panel";

// Vista ampliada de un panel. Al abrir crece DESDE la tarjeta que pinchaste
// (técnica FLIP: parte de la posición/tamaño del panel origen y anima hasta
// pantalla completa); al cerrar hace el camino inverso.
//
// Se usa la Web Animations API (element.animate) en vez de transiciones CSS al
// montar: bajo StrictMode el effect se invoca dos veces (monta/desmonta/remonta)
// y el patrón reflow+rAF de las transiciones no dispara. animate() sí, y además
// siempre actúa sobre el nodo actual.
const ENTER_MS = 340;
const EXIT_MS = 300;
const EASE_IN = "cubic-bezier(0.22, 1, 0.36, 1)";   // entrada: arranca rápido
const EASE_OUT = "cubic-bezier(0.4, 0, 1, 1)";      // salida: acelera al final

export default function Expanded({
  title,
  onClose,
  children,
  actions,
  origin,
  sinCaja = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
  origin?: DOMRect | null;
  // El chat monta su propia caja: el orbe tiene que quedar FUERA del recuadro azul,
  // presidiendo, y solo el hilo escrito va dentro. Ver ChatExpanded.
  sinCaja?: boolean;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const cerradoRef = useRef(false);

  // Transform que lleva el overlay (a tamaño completo) hasta encajar en el panel
  // origen. transform-origin es la esquina superior-izquierda del overlay.
  const transformDesdeOrigen = () => {
    const el = boxRef.current;
    if (!el || !origin) return "";
    const F = el.getBoundingClientRect();
    if (F.width === 0 || F.height === 0) return "";
    const tx = origin.left - F.left;
    const ty = origin.top - F.top;
    const sx = origin.width / F.width;
    const sy = origin.height / F.height;
    return `translate(${tx}px, ${ty}px) scale(${sx}, ${sy})`;
  };

  // Entrada: del panel origen a pantalla completa.
  useLayoutEffect(() => {
    const ov = overlayRef.current, el = boxRef.current;
    if (!ov || !el) return;
    const from = anim.on ? transformDesdeOrigen() : "";
    if (!from) return; // sin zoom (reduced-motion o deep-link): overlay ya opaco
    el.style.transformOrigin = "0 0";
    // se anima antes del primer pintado: el primer frame ya sale en `from`. El
    // cleanup cancela las animaciones: bajo StrictMode el effect corre dos veces
    // (effect→cleanup→effect), y sin cancelar quedarían dos animaciones peleándose.
    const a1 = el.animate(
      [{ transform: from, opacity: 0.6 }, { transform: "none", opacity: 1 }],
      { duration: ENTER_MS, easing: EASE_IN },
    );
    const a2 = ov.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ENTER_MS, easing: "ease" });
    return () => { a1.cancel(); a2.cancel(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Salida: encoge de vuelta al panel origen y luego desmonta.
  const cerrar = () => {
    if (cerradoRef.current) return;
    cerradoRef.current = true;
    const ov = overlayRef.current, el = boxRef.current;
    const to = anim.on ? transformDesdeOrigen() : "";
    if (!to || !el || !ov) {
      onClose();
      return;
    }
    let hecho = false;
    const fin = () => { if (!hecho) { hecho = true; onClose(); } };
    el.style.transformOrigin = "0 0";
    ov.animate([{ opacity: 1 }, { opacity: 0 }], { duration: EXIT_MS, easing: "ease", fill: "forwards" });
    const a = el.animate(
      [{ transform: "none", opacity: 1 }, { transform: to, opacity: 0 }],
      { duration: EXIT_MS, easing: EASE_OUT, fill: "forwards" },
    );
    a.onfinish = fin;
    window.setTimeout(fin, EXIT_MS + 80); // por si onfinish no dispara
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && cerrar();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={overlayRef}
      onClick={(e) => e.target === e.currentTarget && cerrar()}
      className="fixed inset-0 z-50 overflow-y-auto"
      style={{
        background: "rgba(6,10,20,0.86)",
        backdropFilter: "blur(6px)",
        // estado final; la animación de entrada (WAA, sin fill) parte de 0 y
        // revierte aquí, así que no hay parpadeo al terminar.
        opacity: 1,
      }}
    >
      <div ref={boxRef} className="mx-auto flex min-h-screen max-w-7xl flex-col p-5 md:p-8">
        <div className="mb-5 flex items-center gap-4">
          <button
            onClick={cerrar}
            aria-label="Volver al panel"
            className="jarvis-back flex h-9 w-9 items-center justify-center rounded-lg"
          >
            <BackIcon />
          </button>
          <h2
            className="font-display text-sm uppercase tracking-[0.35em]"
            style={{ color: theme.accent, textShadow: "0 0 14px rgba(0,212,255,0.4)" }}
          >
            {title}
          </h2>
          <div className="ml-auto">{actions}</div>
        </div>
        {sinCaja ? (
          <div className="flex flex-1 flex-col">{children}</div>
        ) : (
          <div
            className="flex-1 rounded-2xl p-5 md:p-6"
            style={{
              background: "linear-gradient(180deg, #101a2e 0%, #0c1220 100%)",
              border: "1px solid rgba(0,212,255,0.16)",
              boxShadow: "0 0 50px rgba(0,212,255,0.07), 0 20px 60px rgba(0,0,0,0.6)",
            }}
          >
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
