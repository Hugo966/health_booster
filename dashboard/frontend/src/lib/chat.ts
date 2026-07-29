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

// Los modelos que ofrece el selector, en escalera ascendente de potencia (y de
// precio): Estándar < Turbo < Máxima potencia. El orden del array ES el orden de
// los niveles, así que la posición marca las barras que pinta el selector. El
// `id` es lo que entiende el backend (`obtener` admite "proveedor:modelo").
// "Estándar" (Sonnet 5) es el diario y el default. El 3B local queda fuera: no
// guardaba hechos y el tono flojeaba; sigue disponible por .env si hace falta.
export const MODELOS = [
  { id: "anthropic:claude-sonnet-5", label: "Estándar" },
  { id: "anthropic:claude-opus-4-8", label: "Turbo" },
  { id: "anthropic:claude-fable-5", label: "Máxima potencia" },
] as const;
export const MODELO_DEF = MODELOS[0].id;

// Override de entorno (VITE_JARVIS_PROVEEDOR=falso desarrolla el frontend sin
// modelo). Sirve solo de valor inicial: manda la elección del selector.
const PROVEEDOR_ENV = import.meta.env.VITE_JARVIS_PROVEEDOR as string | undefined;

const KEY_SESION = "jarvis.chat.sesion";
const KEY_HIST = "jarvis.chat.historial";
const KEY_PROV = "jarvis.chat.proveedor";

function proveedorInicial(): string {
  try {
    // Solo se acepta lo guardado si sigue siendo una opción del selector: así una
    // elección vieja (p.ej. el 3B, ya retirado) no deja el chat en un modelo
    // fantasma sin pill que lo marque.
    const guardado = localStorage.getItem(KEY_PROV);
    if (guardado && MODELOS.some((m) => m.id === guardado)) return guardado;
  } catch {
    /* modo privado: no hay preferencia guardada */
  }
  return PROVEEDOR_ENV || MODELO_DEF;
}
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

async function pedir(sesion: string, mensaje: string, proveedor: string): Promise<Respuesta> {
  const r = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sesion, mensaje, ...(proveedor ? { proveedor } : {}) }),
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
  proveedor: string;
  setProveedor: (p: string) => void;
};

export function useChat(
  onAcciones?: (acciones: Accion[]) => void,
  // Se dispara con el texto de CADA respuesta nueva de Jarvis (no el historial al
  // recargar). Lo usa la capa de voz para leerlo en alto; opcional.
  onRespuesta?: (texto: string) => void,
): Chat {
  const sesion = useRef(idSesion());
  const [mensajes, setMensajes] = useState<Mensaje[]>(cargar);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proveedor, setProveedorState] = useState<string>(proveedorInicial);

  // El proveedor se lee en `enviar` desde una ref para no recrear el callback al
  // cambiar de modelo a media conversación.
  const provRef = useRef(proveedor);
  const setProveedor = useCallback((p: string) => {
    setProveedorState(p);
    provRef.current = p;
    try {
      localStorage.setItem(KEY_PROV, p);
    } catch {
      /* modo privado: no se recuerda el modelo entre recargas */
    }
  }, []);

  // El callback de acciones se guarda en una ref para que `enviar` no se recree
  // cuando App pase una función distinta en cada render.
  const accionesRef = useRef(onAcciones);
  const respuestaRef = useRef(onRespuesta);
  useEffect(() => {
    accionesRef.current = onAcciones;
    respuestaRef.current = onRespuesta;
  }, [onAcciones, onRespuesta]);

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
        const r = await pedir(sesion.current, limpio, provRef.current);
        if (r.texto) {
          setMensajes((prev) => [...prev, { rol: "jarvis", texto: r.texto, ts: Date.now() }]);
          respuestaRef.current?.(r.texto);   // que la voz lo lea (si está activa)
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

  return { mensajes, enviando, error, enviar, proveedor, setProveedor };
}
