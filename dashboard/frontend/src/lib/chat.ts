import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "./api";

// Cliente del chat de Jarvis + el estado de la conversación. Vive aquí (no en el
// componente) porque compacto y ampliado comparten el mismo hilo, así que el
// estado se iza a App con este hook, igual que el objetivo de peso en lib/goal.ts.

// Una acción de UI que devuelve el backend (abrir_panel, resaltar…). Aquí solo se
// tipa y se pasa hacia arriba; el reproductor que las ejecuta es lib/acciones.ts.
export type Accion = { tipo: string; [k: string]: unknown };
export type Mensaje = { rol: "usuario" | "jarvis"; texto: string; ts: number };
export type Respuesta = { texto: string; acciones: Accion[] };

// Proveedor forzado desde el entorno: con VITE_JARVIS_PROVEEDOR=falso se
// desarrolla el frontend entero sin un modelo detrás. Sin definir, el backend
// usa su propia configuración (JARVIS_PROVEEDOR).
const PROVEEDOR = import.meta.env.VITE_JARVIS_PROVEEDOR as string | undefined;

const KEY_SESION = "jarvis.chat.sesion";
const KEY_HIST = "jarvis.chat.historial";
// Recorta lo que se guarda en el navegador; el contexto real lo lleva el backend
// (memoria.hilo_reciente), así que aquí basta con lo que se pinta en pantalla.
const MAX_HIST = 100;

// Id de sesión estable entre recargas: el backend agrupa el hilo por sesión, así
// que si cambiara en cada arranque se perdería la continuidad de la conversación.
// Los hechos de la vida de Hugo son globales y sobreviven igual.
function idSesion(): string {
  try {
    let s = localStorage.getItem(KEY_SESION);
    if (!s) {
      s = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      localStorage.setItem(KEY_SESION, s);
    }
    return s;
  } catch {
    return "web";
  }
}

function cargar(): Mensaje[] {
  try {
    const raw = localStorage.getItem(KEY_HIST);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.filter(
      (m): m is Mensaje =>
        m && (m.rol === "usuario" || m.rol === "jarvis") && typeof m.texto === "string",
    );
  } catch {
    return [];
  }
}

async function pedir(sesion: string, mensaje: string): Promise<Respuesta> {
  const r = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sesion, mensaje, ...(PROVEEDOR ? { proveedor: PROVEEDOR } : {}) }),
  });
  if (!r.ok) throw new Error(`El chat respondió ${r.status}`);
  const j = await r.json();
  return {
    texto: String(j.texto ?? ""),
    acciones: Array.isArray(j.acciones) ? j.acciones : [],
  };
}

export type Chat = {
  mensajes: Mensaje[];
  enviando: boolean;
  error: string | null;
  enviar: (texto: string) => void;
};

export function useChat(onAcciones?: (acciones: Accion[]) => void): Chat {
  const sesion = useRef(idSesion());
  const [mensajes, setMensajes] = useState<Mensaje[]>(cargar);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // El callback de acciones se guarda en una ref para que `enviar` no se recree
  // cuando App pase una función distinta en cada render.
  const accionesRef = useRef(onAcciones);
  useEffect(() => {
    accionesRef.current = onAcciones;
  }, [onAcciones]);

  useEffect(() => {
    try {
      localStorage.setItem(KEY_HIST, JSON.stringify(mensajes.slice(-MAX_HIST)));
    } catch {
      /* modo privado: se pierde el historial local, no pasa nada */
    }
  }, [mensajes]);

  const enviar = useCallback(
    async (texto: string) => {
      const limpio = texto.trim();
      if (!limpio || enviando) return;
      setError(null);
      setMensajes((prev) => [...prev, { rol: "usuario", texto: limpio, ts: Date.now() }]);
      setEnviando(true);
      try {
        const r = await pedir(sesion.current, limpio);
        if (r.texto) {
          setMensajes((prev) => [...prev, { rol: "jarvis", texto: r.texto, ts: Date.now() }]);
        }
        if (r.acciones.length) accionesRef.current?.(r.acciones);
      } catch (e) {
        setError(String(e));
      } finally {
        setEnviando(false);
      }
    },
    [enviando],
  );

  return { mensajes, enviando, error, enviar };
}
