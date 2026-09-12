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
// Sesión FIJA y compartida, no una por navegador. El hilo de conversación vive en el
// backend (jarvis.db) y Hugo quiere una sola charla: lo que dice por micro al escuchador
// local (dashboard/escucha) y lo que escribe aquí tienen que ser la misma. Con un id
// aleatorio por navegador se partía en dos y Jarvis no recordaba lo hablado en voz.
const SESION_FIJA = "hugo";

function idSesion(): string {
  try {
    // Se respeta una sesión ya guardada solo si alguien la puso a mano (pruebas).
    return localStorage.getItem(KEY_SESION) || SESION_FIJA;
  } catch {
    return SESION_FIJA;
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

// El chat consume `/chat/stream` (SSE), no `/chat`. El endpoint sin streaming sigue
// existiendo en el backend para pruebas con curl.

// Turno de voz que el chat va alimentando (lo implementa voz.ts). Se declara aquí de
// forma estructural para no acoplar el chat a la capa de voz.
// El turno de voz (lo implementa voz.ts). Se declara de forma estructural para no
// acoplar el chat a la capa de voz. Qué muletilla toca lo decide Haiku en el backend y
// llega por SSE: una regex de palabras sueltas se equivocaba feo (un "hoy me encuentro
// jodido" acababa en 'consulta' por el "hoy" y le soltaba "voy a mirar tus datos").
type Habla = {
  muletilla: (texto: string, escrita?: boolean) => void;
  empujar: (frase: string) => void;
  cerrar: () => void;
};

// Corta el buffer por el ÚLTIMO final de frase y devuelve [listo, resto]. Se habla por
// frases completas: mandar trozos a medias al TTS destroza la entonación.
const FIN_FRASE = /^[\s\S]*[.!?…](?=\s|$)/;
const MIN_FRASE = 18; // por debajo de esto se espera a la siguiente: evita microclips

function cortarFrases(buf: string): [string, string] {
  const m = buf.match(FIN_FRASE);
  if (!m) return ["", buf];
  const listo = m[0];
  if (listo.trim().length < MIN_FRASE) return ["", buf];
  return [listo, buf.slice(listo.length)];
}

export type Chat = {
  mensajes: Mensaje[];
  enviando: boolean;
  error: string | null;
  enviar: (texto: string) => void;
  proveedor: string;
  setProveedor: (p: string) => void;
};

// Avisa al backend de que ya no hay nadie escuchando. Cerrar el socket NO basta: el
// turno corre en un hilo aparte que llegaría hasta el final, ejecutando por el camino
// las herramientas de escritura (`guardar_pm`…) sobre la hoja de Hugo.
// `keepalive` para que salga aunque la pestaña se esté cerrando; los fallos se ignoran a
// propósito: es un aviso de cortesía, no puede tumbar la petición nueva.
function cancelarTurno(sesion: string) {
  try {
    void fetch(`${API_BASE}/chat/cancelar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sesion }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* backend caído: no hay nada que cancelar */
  }
}

export function useChat(
  onAcciones?: (acciones: Accion[]) => void,
  // Abre un turno de voz al empezar la respuesta. El chat le va empujando cada frase
  // en cuanto está completa, así Jarvis empieza a hablar mientras aún redacta el resto.
  // Opcional: sin voz activa, `useChat` funciona igual.
  onHabla?: () => Habla,
): Chat {
  const sesion = useRef(idSesion());
  const [mensajes, setMensajes] = useState<Mensaje[]>(cargar);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proveedor, setProveedorState] = useState<string>(proveedorInicial);

  // Petición en vuelo, para poder abortarla cuando Hugo interrumpe.
  const abortRef = useRef<AbortController | null>(null);
  // Nº de envío. Sirve para que el desenlace de una petición abortada (que llega tarde)
  // no toque el estado de la que ya la ha sustituido.
  const genRef = useRef(0);

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
  const hablaRef = useRef(onHabla);
  useEffect(() => {
    accionesRef.current = onAcciones;
    hablaRef.current = onHabla;
  }, [onAcciones, onHabla]);

  useEffect(() => {
    try {
      localStorage.setItem(KEY_HIST, JSON.stringify(mensajes.slice(-MAX_HIST)));
    } catch {
      /* modo privado: se pierde el historial local, no pasa nada */
    }
  }, [mensajes]);

  // Sincronización con el hilo del backend. Hace falta porque el escuchador local
  // (dashboard/escucha) habla directamente con el backend: sus mensajes no pasan por
  // aquí y, sin esto, lo dicho por micro no aparecía nunca en pantalla.
  //
  // Se compara el ÚLTIMO id: si el backend va por delante, se adopta su hilo entero
  // (es la fuente de verdad de la conversación). No se toca mientras se está enviando,
  // para no pisar el texto que se está escribiendo en vivo.
  const ultimoIdRef = useRef(0);
  // Tras abortar, el backend tarda un poco en enterarse. Durante ese rato su hilo aún no
  // refleja la interrupción, y adoptarlo repintaría lo que Hugo acaba de cortar.
  const noSincronizarHastaRef = useRef(0);
  useEffect(() => {
    let vivo = true;
    const sincronizar = async () => {
      if (!vivo || enviando || document.hidden) return;
      if (Date.now() < noSincronizarHastaRef.current) return;
      try {
        const r = await fetch(`${API_BASE}/hilo?sesion=${encodeURIComponent(sesion.current)}`);
        if (!r.ok) return;
        const j = await r.json();
        const filas: any[] = Array.isArray(j.mensajes) ? j.mensajes : [];
        if (!filas.length) return;
        const ultimo = Number(filas[filas.length - 1].id) || 0;
        if (ultimo <= ultimoIdRef.current) return; // nada nuevo
        ultimoIdRef.current = ultimo;
        setMensajes(
          filas.map((f) => ({
            rol: f.rol === "usuario" ? "usuario" : "jarvis",
            texto: String(f.texto ?? ""),
            ts: Date.parse(f.ts) || Date.now(),
          })),
        );
      } catch {
        /* backend caído: se sigue con lo que haya en local */
      }
    };
    sincronizar();
    const t = window.setInterval(sincronizar, 3000);
    window.addEventListener("focus", sincronizar);
    document.addEventListener("visibilitychange", sincronizar);
    return () => {
      vivo = false;
      window.clearInterval(t);
      window.removeEventListener("focus", sincronizar);
      document.removeEventListener("visibilitychange", sincronizar);
    };
  }, [enviando]);

  const enviar = useCallback(
    async (texto: string) => {
      const limpio = texto.trim();
      if (!limpio) return;

      // Interrumpir: la petición en vuelo se ABORTA en vez de descartar la nueva. Antes
      // había aquí un `|| enviando` que tiraba en silencio lo que Hugo dijera mientras
      // Jarvis respondía: le cortaba la voz pero su aclaración no llegaba a ninguna
      // parte, y desde fuera parecía que a Jarvis no se le podía interrumpir.
      if (abortRef.current) {
        abortRef.current.abort();
        // Cerrar el socket no basta: el turno corre en un hilo aparte del backend que
        // seguiría hasta el final, ejecutando herramientas de ESCRITURA incluidas.
        cancelarTurno(sesion.current);
        noSincronizarHastaRef.current = Date.now() + 4000;
      }
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      // Cada envío lleva su número. El `finally` de una petición abortada llega TARDE,
      // cuando la nueva ya está en marcha: sin esto le apagaría el `enviando` y le
      // pisaría la burbuja.
      const gen = ++genRef.current;
      const vigente = () => genRef.current === gen;

      setError(null);
      setMensajes((prev) => [...prev, { rol: "usuario", texto: limpio, ts: Date.now() }]);
      setEnviando(true);

      // Turno de voz abierto YA: las frases se le empujan según llegan del modelo.
      const habla = hablaRef.current?.() ?? null;
      const ts = Date.now();
      let acumulado = "";   // todo lo dicho hasta ahora (para la burbuja)
      let pendiente = "";   // lo que aún no forma frase completa (para la voz)
      let hayBurbuja = false;

      // La burbuja se va reescribiendo en vivo: se ve escribir a Jarvis.
      const pintar = (t: string) => {
        if (!vigente()) return;
        setMensajes((prev) => {
          const copia = [...prev];
          const m: Mensaje = { rol: "jarvis", texto: t, ts };
          if (hayBurbuja) copia[copia.length - 1] = m;
          else copia.push(m);
          return copia;
        });
        hayBurbuja = true;
      };

      const vaciar = (final: boolean) => {
        if (!habla) return;
        if (final) {
          if (pendiente.trim()) habla.empujar(pendiente);
          pendiente = "";
          return;
        }
        const [listo, resto] = cortarFrases(pendiente);
        if (!listo) return;
        pendiente = resto;
        habla.empujar(listo);
      };

      try {
        const r = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sesion: sesion.current,
            mensaje: limpio,
            ...(provRef.current ? { proveedor: provRef.current } : {}),
          }),
          signal: ctrl.signal,
        });
        if (!r.ok || !r.body) throw new Error(`El chat respondió ${r.status}`);

        const lector = r.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        let fin: { texto: string; acciones: Accion[]; error?: string | null } | null = null;

        for (;;) {
          const { done, value } = await lector.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          // SSE: los eventos van separados por línea en blanco.
          const trozos = buf.split("\n\n");
          buf = trozos.pop() ?? "";
          for (const t of trozos) {
            const linea = t.split("\n").find((l) => l.startsWith("data: "));
            if (!linea) continue;
            const ev = JSON.parse(linea.slice(6));
            if (ev.tipo === "texto") {
              acumulado += ev.texto;
              pendiente += ev.texto;
              pintar(acumulado);
              vaciar(false);
            } else if (ev.tipo === "muletilla" || ev.tipo === "muletilla_texto") {
              // `muletilla_texto` = el backend la ha redactado a medida con el modelo
              // rápido y hay que sintetizarla aquí. `muletilla` a secas es el nombre de un
              // pool de frases ya grabadas, que es lo de siempre y lo que llega si no hay
              // modelo rápido o si ha fallado.
              habla?.muletilla(String(ev.texto ?? ""), ev.tipo === "muletilla_texto");
            } else {
              fin = {
                texto: String(ev.texto ?? ""),
                acciones: Array.isArray(ev.acciones) ? ev.acciones : [],
                error: ev.error,
              };
            }
          }
        }

        vaciar(true); // la última frase, aunque no cierre con punto
        if (fin?.error) setError(fin.error);
        // El texto del evento final manda: incluye lo de todas las vueltas de herramienta.
        if (fin?.texto && fin.texto !== acumulado) pintar(fin.texto);
        if (fin?.acciones.length && vigente()) accionesRef.current?.(fin.acciones);
      } catch (e) {
        // Abortar es lo que Hugo ha pedido al interrumpir, no un fallo: pintarlo en rojo
        // sería mentirle.
        if ((e as Error)?.name !== "AbortError" && vigente()) setError(String(e));
      } finally {
        habla?.cerrar(); // protegido por el contador de turno de voz.ts: es inocuo si ya cambió
        if (vigente()) {
          abortRef.current = null;
          setEnviando(false);
        }
      }
    },
    [],
  );

  return { mensajes, enviando, error, enviar, proveedor, setProveedor };
}
