import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Panel from "./Panel";
import { theme } from "../lib/theme";
import { MODELOS } from "../lib/chat";
import type { Chat, Mensaje } from "../lib/chat";

// El chat de Jarvis: compacto (ChatPanel, una tarjeta más del grid) y ampliado
// (ChatExpanded, la conversación entera en el overlay). Los dos leen el mismo
// hilo desde el hook useChat, que vive en App — así escribir en uno se ve en el
// otro. Texto plano con saltos de línea; no hay markdown en la v1.

const SALUDO = "Pregúntame cómo te ve hoy, pídele que te abra un panel, o cuéntale algo.";

// --- burbujas ---------------------------------------------------------------

function Burbuja({ m }: { m: Mensaje }) {
  const mio = m.rol === "usuario";
  return (
    <div className={`flex ${mio ? "justify-end" : "justify-start"}`}>
      <div
        className="max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed"
        style={
          mio
            ? { background: "rgba(0,212,255,0.14)", border: "1px solid rgba(0,212,255,0.28)", color: theme.text }
            : { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", color: theme.text }
        }
      >
        {m.texto}
      </div>
    </div>
  );
}

// "…" mientras el modelo piensa: se muestra tras el mensaje del usuario y antes
// de que llegue la respuesta.
function Pensando() {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl px-3.5 py-2 text-[13px]"
        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", color: theme.muted }}
      >
        Jarvis está pensando…
      </div>
    </div>
  );
}

function ListaMensajes({
  mensajes,
  enviando,
  error,
  vacio,
}: {
  mensajes: Mensaje[];
  enviando: boolean;
  error: string | null;
  vacio: string;
}) {
  const finRef = useRef<HTMLDivElement>(null);
  // Pegado abajo al llegar mensajes nuevos o mientras "piensa".
  useLayoutEffect(() => {
    finRef.current?.scrollIntoView({ block: "end" });
  }, [mensajes.length, enviando]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      <div className="flex flex-col gap-2.5">
        {mensajes.length === 0 && !enviando && (
          <div className="text-[13px]" style={{ color: theme.muted }}>
            {vacio}
          </div>
        )}
        {mensajes.map((m, i) => (
          <Burbuja key={m.ts + "-" + i} m={m} />
        ))}
        {enviando && <Pensando />}
        {error && (
          <div className="text-[12px]" style={{ color: theme.alert }}>
            {error}
          </div>
        )}
        <div ref={finRef} />
      </div>
    </div>
  );
}

// Selector de modelo: pills segmentadas con el glow cian del tema (el activo se
// ilumina). data-no-expand: tocarlo no debe ampliar la tarjeta. El backend
// entiende el `id` tal cual (obtener admite "proveedor:modelo"), así que cambiar
// de modelo es solo mandar otro string en el siguiente mensaje.
function SelectorModelo({ valor, onChange }: { valor: string; onChange: (p: string) => void }) {
  return (
    <div data-no-expand className="mb-2 flex flex-wrap justify-end gap-1.5">
      {MODELOS.map((m) => {
        const activo = m.id === valor;
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            title={`Cambiar a ${m.label}`}
            className="font-display rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.12em] transition-all duration-200"
            style={
              activo
                ? {
                    color: theme.accent,
                    border: `1px solid ${theme.accent}`,
                    background: "rgba(0,212,255,0.10)",
                    boxShadow: "0 0 12px rgba(0,212,255,0.35)",
                  }
                : {
                    color: theme.muted,
                    border: "1px solid rgba(255,255,255,0.10)",
                    background: "transparent",
                  }
            }
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}

// --- entrada ----------------------------------------------------------------

// data-no-expand: pinchar o escribir aquí no debe ampliar la tarjeta (trampa 1
// del plan: el Panel amplía al clicar su fondo).
function Entrada({ enviando, onEnviar, autofocus }: { enviando: boolean; onEnviar: (t: string) => void; autofocus?: boolean }) {
  const [texto, setTexto] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autofocus) ref.current?.focus();
  }, [autofocus]);

  const mandar = () => {
    const t = texto.trim();
    if (!t || enviando) return;
    onEnviar(t);
    setTexto("");
  };

  return (
    <div data-no-expand className="mt-3 flex items-end gap-2">
      <textarea
        ref={ref}
        rows={1}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          // Enter envía; Mayús+Enter hace salto de línea, como todo chat.
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            mandar();
          }
        }}
        placeholder="Escribe a Jarvis…"
        className="jarvis-input max-h-28 min-h-[38px] flex-1 resize-none"
        style={{ fontSize: 13, padding: "9px 12px", lineHeight: 1.4 }}
      />
      <button
        onClick={mandar}
        disabled={enviando || !texto.trim()}
        aria-label="Enviar mensaje"
        title="Enviar"
        className="jarvis-back flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-lg disabled:opacity-40"
      >
        <FlechaEnviar />
      </button>
    </div>
  );
}

function FlechaEnviar() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 13V3M8 3 3.5 7.5M8 3l4.5 4.5" />
    </svg>
  );
}

// --- las dos vistas ---------------------------------------------------------

export default function ChatPanel({ chat, onExpand }: { chat: Chat; onExpand: (origin?: DOMRect) => void }) {
  return (
    <Panel title="Jarvis" onExpand={onExpand}>
      {/* Altura fija en px, como el resto de paneles compactos (ver §8): aquí no
          hay ResponsiveContainer, pero conviene que la tarjeta case en altura
          con Fuerza/Peso/Correlaciones de su fila. */}
      <div className="flex flex-col" style={{ height: 263 }}>
        <SelectorModelo valor={chat.proveedor} onChange={chat.setProveedor} />
        <ListaMensajes mensajes={chat.mensajes} enviando={chat.enviando} error={chat.error} vacio={SALUDO} />
        <Entrada enviando={chat.enviando} onEnviar={chat.enviar} />
      </div>
    </Panel>
  );
}

// Altura de viewport fija (no h-full en %): dentro del flex-1 de Expanded, un
// height:100% no resuelve y la entrada se pegaría arriba. min-h-0 en la lista le
// da su propio contexto de scroll (trampa 2 del plan: Expanded es overflow-y-auto).
export function ChatExpanded({ chat }: { chat: Chat }) {
  return (
    <div className="mx-auto flex h-[72vh] min-h-0 w-full max-w-3xl flex-col">
      <SelectorModelo valor={chat.proveedor} onChange={chat.setProveedor} />
      <ListaMensajes mensajes={chat.mensajes} enviando={chat.enviando} error={chat.error} vacio={SALUDO} />
      <Entrada enviando={chat.enviando} onEnviar={chat.enviar} autofocus />
    </div>
  );
}
