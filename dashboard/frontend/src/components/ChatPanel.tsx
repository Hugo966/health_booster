import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Panel from "./Panel";
import { theme } from "../lib/theme";
import { MODELOS } from "../lib/chat";
import type { Chat, Mensaje } from "../lib/chat";
import type { Voz } from "../lib/voz";
import Presencia, { type EstadoPresencia } from "./Presencia";

// El chat de Jarvis: compacto (ChatPanel, una tarjeta más del grid) y ampliado
// (ChatExpanded, la conversación entera en el overlay). Los dos leen el mismo
// hilo desde el hook useChat, que vive en App — así escribir en uno se ve en el
// otro. Texto plano con saltos de línea; no hay markdown en la v1.

const SALUDO = "Pregúntame cómo te ve hoy, pídele que te abra un panel, o cuéntale algo.";

// --- burbujas ---------------------------------------------------------------

// Jarvis marca la intención con etiquetas tipo [sarcastic] para que el TTS (ElevenLabs
// v3) no lea la ironía en plano. Son instrucciones para la voz, no texto: se mandan al
// servicio de voz tal cual, pero aquí se quitan al pintar. Solo minúsculas ASCII entre
// corchetes, para no cargarse nada que Hugo o Jarvis escriban entre corchetes de verdad.
const ETIQUETAS_VOZ = /\[[a-z][a-z ]{1,20}\]\s*/g;
const sinEtiquetas = (t: string) => t.replace(ETIQUETAS_VOZ, "").trim();

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
        {mio ? m.texto : sinEtiquetas(m.texto)}
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

// Las burbujas sin contenedor de scroll propio: así el ampliado puede meterlas dentro
// de SU scroll (el que hace encoger el orbe) sin anidar dos áreas desplazables.
function Mensajes({
  mensajes,
  enviando,
  error,
  vacio,
  autoScroll = true,
}: {
  mensajes: Mensaje[];
  enviando: boolean;
  error: string | null;
  vacio: string;
  autoScroll?: boolean;
}) {
  const finRef = useRef<HTMLDivElement>(null);
  // Pegado abajo al llegar mensajes nuevos o mientras "piensa". En el ampliado se
  // desactiva: ahí el scroll lo manda Hugo (arriba está el estado, abajo el chat) y
  // saltar al final solo le arrancaría la vista del orbe.
  useLayoutEffect(() => {
    if (autoScroll) finRef.current?.scrollIntoView({ block: "end" });
  }, [mensajes.length, enviando, autoScroll]);

  return (
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
  );
}

// Un color por nivel (verde → naranja → rojo), como un medidor de potencia: cada
// escalón "cuesta" más. El activo se pinta con su color; el inactivo, apagado.
const NIVELES = [
  { c: "#34e07a", bg: "rgba(52,224,122,0.12)", glow: "0 0 12px rgba(52,224,122,0.45)" },
  { c: "#ff9f43", bg: "rgba(255,159,67,0.12)", glow: "0 0 12px rgba(255,159,67,0.45)" },
  { c: "#ff5c5c", bg: "rgba(255,92,92,0.12)", glow: "0 0 12px rgba(255,92,92,0.45)" },
];

// Barras de "potencia" tipo señal: el nivel (posición en MODELOS) enciende las N
// primeras de tres, para que el selector se lea como una escalera, no como sabores.
function Barras({ nivel, color }: { nivel: number; color: string }) {
  return (
    <span className="inline-flex items-end gap-[2px]" style={{ height: 8 }}>
      {[3, 5, 7].map((h, i) => (
        <span
          key={i}
          style={{ width: 2, height: h, borderRadius: 1, background: color, opacity: i < nivel ? 1 : 0.25 }}
        />
      ))}
    </span>
  );
}

// Selector de modelo: pills segmentadas con barras de nivel a la izquierda; el
// activo se ilumina con el color de su nivel. data-no-expand: tocarlo no debe
// ampliar la tarjeta. El backend entiende el `id` tal cual (obtener admite
// "proveedor:modelo"), así que cambiar de modelo es solo mandar otro string.
function SelectorModelo({ valor, onChange }: { valor: string; onChange: (p: string) => void }) {
  return (
    <div data-no-expand className="mb-2 flex flex-wrap justify-end gap-1.5">
      {MODELOS.map((m, i) => {
        const activo = m.id === valor;
        const n = NIVELES[i] ?? NIVELES[NIVELES.length - 1];
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            title={`Cambiar a ${m.label}`}
            className="font-display flex items-center gap-1.5 rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.12em] transition-all duration-200"
            style={
              activo
                ? { color: n.c, border: `1px solid ${n.c}`, background: n.bg, boxShadow: n.glow }
                : { color: theme.muted, border: "1px solid rgba(255,255,255,0.10)", background: "transparent" }
            }
          >
            <Barras nivel={i + 1} color={activo ? n.c : theme.muted} />
            {m.label}
          </button>
        );
      })}
    </div>
  );
}

// --- presencia (orbe de voz) ------------------------------------------------

// Qué forma muestra el orbe: manda la voz y, mientras se espera la respuesta del
// backend, "pensando" (venga de voz o de teclado). El estado de voz "activo"
// (conversación, escucha todo) se pinta como el radar "escuchando"; "reposo" (solo
// wake word) como la esfera tenue "dormido".
function estadoPresencia(voz: Voz | undefined, enviando: boolean): EstadoPresencia {
  // "hablando" solo cuando SALE voz, no cuando se abre el turno: entre medias todavía
  // está generando, y ahí lo honesto es seguir mostrando "pensando".
  if (voz?.soportado && voz.sonando) return "hablando";
  if (enviando || voz?.estado === "hablando") return "pensando";
  if (voz?.soportado && voz.estado === "activo") return "escuchando";
  if (voz?.soportado && voz.estado === "reposo") return "dormido";
  return "off";
}

const LEYENDA: Record<EstadoPresencia, string> = {
  off: "Toca el orbe para activar la voz",
  dormido: "En reposo · di «Jarvis» para hablar",
  escuchando: "Te escucho, habla",
  pensando: "Pensando…",
  hablando: "Hablando…",
};

// Nivel de potencia (0/1/2) = posición del modelo activo en MODELOS (Estándar/Turbo/Máx).
// Tiñe la energía y el aro del orbe, no su color de estado.
function potenciaDe(proveedor: string): number {
  const i = MODELOS.findIndex((m) => m.id === proveedor);
  return i < 0 ? 0 : i;
}

// El orbe + su leyenda. Un clic enciende/apaga la escucha (o corta si está hablando).
function Orbe({ voz, enviando, potencia, size }: { voz?: Voz; enviando: boolean; potencia: number; size: number }) {
  const est = estadoPresencia(voz, enviando);
  const onToggle = voz?.soportado
    ? () => (voz.estado === "hablando" ? voz.parar() : voz.alternar())
    : undefined;
  return (
    <div className="flex flex-col items-center gap-1">
      <Presencia estado={est} potencia={potencia} onToggle={onToggle} size={size} />
      <div className="text-[11px]" style={{ color: theme.muted }}>
        {voz?.soportado === false ? "Voz no disponible (usa Chrome)" : LEYENDA[est]}
      </div>
    </div>
  );
}

// --- entrada ----------------------------------------------------------------

// data-no-expand: pinchar o escribir aquí no debe ampliar la tarjeta (trampa 1
// del plan: el Panel amplía al clicar su fondo).
function Entrada({ enviando, onEnviar, voz, autofocus }: { enviando: boolean; onEnviar: (t: string) => void; voz?: Voz; autofocus?: boolean }) {
  const [texto, setTexto] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autofocus) ref.current?.focus();
  }, [autofocus]);

  const mandar = () => {
    const t = texto.trim();
    if (!t || enviando) return;
    if (voz?.estado === "hablando") voz.parar(); // barge-in: al escribir, córtale
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

export default function ChatPanel({ chat, voz, onExpand }: { chat: Chat; voz?: Voz; onExpand: (origin?: DOMRect) => void }) {
  return (
    <Panel title="Jarvis" onExpand={onExpand}>
      {/* Altura fija en px, como el resto de paneles compactos (ver §8). Voz-first: el
          orbe es el protagonista; la caja de texto queda de respaldo. El historial se
          ve en la vista ampliada. */}
      <div className="flex flex-col" style={{ height: 263 }}>
        <SelectorModelo valor={chat.proveedor} onChange={chat.setProveedor} />
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <Orbe voz={voz} enviando={chat.enviando} potencia={potenciaDe(chat.proveedor)} size={150} />
        </div>
        {chat.error && <div className="mb-1 text-center text-[11px]" style={{ color: theme.alert }}>{chat.error}</div>}
        <Entrada enviando={chat.enviando} onEnviar={chat.enviar} voz={voz} />
      </div>
    </Panel>
  );
}

// Vista ampliada, "voz primero": px de scroll en los que el orbe pasa de presidir la
// pantalla a quedarse arriba, sus dos tamaños y la altura (en vh) de su zona. El orbe
// NO va dentro del recuadro azul: preside fuera, y solo el hilo escrito va en la caja.
const RECORRIDO = 260;
const ORBE_GRANDE = 260;
const ORBE_CHICO = 168;
// % del alto que ocupa la zona del orbe. Las dos zonas SE REPARTEN el alto (no se
// superponen): al entrar el orbe se lo queda todo y la caja mide 0 —el chat ni se ve—;
// al bajar, el orbe cede hasta ~1/3 y la caja crece con el resto.
const ZONA_GRANDE = 100;
const ZONA_CHICA = 38;

// Altura de viewport fija (no h-full en %): dentro del flex-1 de Expanded, un
// height:100% no resuelve y la entrada se pegaría arriba. min-h-0 en la lista le
// da su propio contexto de scroll (trampa 2 del plan: Expanded es overflow-y-auto).
export function ChatExpanded({ chat, voz }: { chat: Chat; voz?: Voz }) {
  // Al entrar NO se ve el chat escrito: solo el estado del agente, a lo grande y
  // centrado (hablar con él es lo normal; leer el hilo es lo excepcional). Al bajar,
  // el orbe encoge y el historial sube. `p` es el progreso 0→1 de ese scroll.
  const contRef = useRef<HTMLDivElement>(null);
  const cajaRef = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(0);
  const pRef = useRef(0);

  // La rueda gobierna el reparto: primero encoge el orbe y despliega la caja, y solo
  // cuando ya está desplegada (p=1) el hilo scrollea por su cuenta. Al revés, si la
  // caja está arriba del todo, seguir subiendo devuelve el orbe a pantalla completa.
  // Hace falta listener manual con {passive:false} para poder frenar el scroll nativo.
  useEffect(() => {
    const cont = contRef.current;
    if (!cont) return;
    const alRodar = (e: WheelEvent) => {
      const caja = cajaRef.current;
      const arriba = !caja || caja.scrollTop <= 0;
      const bajando = e.deltaY > 0;
      if ((bajando && pRef.current < 1) || (!bajando && pRef.current > 0 && arriba)) {
        e.preventDefault();
        const nuevo = Math.min(1, Math.max(0, pRef.current + e.deltaY / RECORRIDO));
        pRef.current = nuevo;
        setP(nuevo);
      }
    };
    cont.addEventListener("wheel", alRodar, { passive: false });
    return () => cont.removeEventListener("wheel", alRodar);
  }, []);

  const tam = Math.round(ORBE_GRANDE + (ORBE_CHICO - ORBE_GRANDE) * p);
  const zona = ZONA_GRANDE + (ZONA_CHICA - ZONA_GRANDE) * p;

  return (
    <div ref={contRef} className="mx-auto flex h-[80vh] min-h-0 w-full max-w-3xl flex-col">
      {/* Zona del orbe: FUERA de la caja azul y con su propio espacio reservado. */}
      <div
        className="flex shrink-0 flex-col items-center justify-center overflow-hidden"
        style={{ height: `${zona}%` }}
      >
        <Orbe voz={voz} enviando={chat.enviando} potencia={potenciaDe(chat.proveedor)} size={tam} />
        <div style={{ opacity: p }} className="mt-2 w-full max-w-md">
          <SelectorModelo valor={chat.proveedor} onChange={chat.setProveedor} />
        </div>
      </div>
      {/* La caja azul: solo el hilo escrito. Mide 0 al entrar, así el chat ni asoma. */}
      <div
        ref={cajaRef}
        className="min-h-0 flex-1 overflow-y-auto rounded-2xl"
        style={{
          background: "linear-gradient(180deg, #101a2e 0%, #0c1220 100%)",
          border: p > 0.02 ? "1px solid rgba(0,212,255,0.16)" : "none",
          boxShadow: p > 0.02 ? "0 0 50px rgba(0,212,255,0.07), 0 20px 60px rgba(0,0,0,0.6)" : "none",
          padding: p > 0.02 ? "20px" : 0,
          opacity: p,
        }}
      >
        <Mensajes
          mensajes={chat.mensajes}
          enviando={chat.enviando}
          error={chat.error}
          vacio={SALUDO}
          // Solo se baja solo cuando el hilo ya está desplegado. Con el orbe presidiendo
          // no se toca el scroll (arrancaría la vista), pero si Hugo está mirando el
          // chat, un mensaje nuevo tiene que entrar en pantalla: si no, escribe o habla
          // y parece que su burbuja no ha llegado.
          autoScroll={p > 0.9}
        />
      </div>
      <Entrada enviando={chat.enviando} onEnviar={chat.enviar} voz={voz} />
    </div>
  );
}
