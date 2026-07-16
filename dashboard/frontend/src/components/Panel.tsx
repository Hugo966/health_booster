import { useRef } from "react";
import type { MouseEvent, ReactNode } from "react";
import { panelStyle, theme } from "../lib/theme";

/** ¿El clic cayó en el fondo de la tarjeta, y no en un control?
 *
 *  Toda la tarjeta amplía al pincharla, pero los botones, el selector de objetivo
 *  de peso y su input tienen que seguir funcionando. Marca con `data-no-expand`
 *  cualquier zona interactiva que no sea un control HTML nativo. También se
 *  ignora el clic que termina una selección de texto.
 */
export function esFondo(e: MouseEvent): boolean {
  const el = e.target as HTMLElement | null;
  if (el?.closest("button, a, input, select, textarea, label, [data-no-expand]")) return false;
  return !window.getSelection()?.toString();
}

// Tarjeta contenedora con el look Jarvis. La reutilizan los widgets de gráfico
// (HRV, sueño, carga, …). Si recibe `onExpand`, toda ella amplía al pincharla.
export default function Panel({
  title,
  subtitle,
  children,
  onExpand,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  onExpand?: (origin?: DOMRect) => void;
  actions?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const abrir = () => onExpand?.(ref.current?.getBoundingClientRect());
  return (
    <div
      ref={ref}
      className="jarvis-panel group relative flex flex-col rounded-2xl p-5"
      style={{ ...panelStyle, cursor: onExpand ? "pointer" : undefined }}
      onClick={onExpand && ((e) => esFondo(e) && abrir())}
    >
      <div className="mb-3 flex items-center gap-2">
        <span
          className="inline-block h-3 w-[2px] shrink-0 rounded"
          style={{ background: theme.accent, boxShadow: `0 0 6px ${theme.accent}` }}
        />
        <div
          className="font-display text-[11px] uppercase tracking-[0.3em]"
          style={{ color: theme.muted }}
        >
          {title}
        </div>
        {subtitle && (
          <div className="truncate text-[11px]" style={{ color: theme.muted }}>
            {subtitle}
          </div>
        )}
        <div className="ml-auto flex items-center gap-1">
          {actions}
          {onExpand && (
            <button
              onClick={() => abrir()}
              aria-label={`Ampliar ${title}`}
              title="Ampliar"
              className="jarvis-expand rounded-md p-1.5 opacity-0 transition group-hover:opacity-100 focus:opacity-100"
            >
              <ExpandIcon />
            </button>
          )}
        </div>
      </div>
      {/* Los hijos deben fijar la altura de sus gráficos en píxeles. Un
          ResponsiveContainer con height="100%" dentro de un flex-1 sin altura
          definida entra en bucle: mide, crece el SVG, crece el contenedor, remide. */}
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

export function ExpandIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M9.5 1.5h5v5M14.5 1.5 9 7M6.5 14.5h-5v-5M1.5 14.5 7 9" />
    </svg>
  );
}

export function BackIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 2 4 8l6 6" />
    </svg>
  );
}
