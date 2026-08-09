import { useCallback, useEffect, useRef, useState } from "react";

// Capa de voz de Jarvis, manos libres: escucha pasiva la palabra "Jarvis", captura
// el comando, lo manda al chat, y lee en alto la respuesta. Desacoplada del chat:
// recibe `onComando` (qué hacer con lo que oye) y expone `decir` (para que el chat
// le pase la respuesta). Backends (wake word / TTS) a propósito simples y
// sustituibles: v1 con Web Speech del navegador (gratis, sin deps, Chrome). La voz
// "Jarvis" de verdad (XTTS/nube) se enchufa después cambiando solo `decir`.
//
// Máquina de estados:
//   off        -> voz apagada, no escucha nada
//   dormido    -> escucha pasiva, esperando oír "Jarvis"
//   escuchando -> oyó "Jarvis", capturando el comando
//   hablando   -> leyendo la respuesta (se ignora la escucha: anti-eco)
export type EstadoVoz = "off" | "dormido" | "escuchando" | "hablando";

// Abanico de cómo puede sonar/transcribirse "Jarvis" en español: la J suena "y"/"ll"
// (jarvis, yarvis, llarvis) y el reconocedor confunde v/b, y a veces se come la "s"
// final. Esta regex cubre jarvis/yarvis/llarvis/jarvi/yarvi/llarvi y sus versiones con
// "b" (jarbis…). Si ves que se le escapa alguna grafía, amplía el prefijo o el núcleo.
const WAKE = /\b(?:ll|j|y|h)?ar[vb]i[sz]?\b/gi;
// Tras terminar de hablar, ignora lo que llegue este rato: descarta la cola de
// reconocimiento que pudiera traer la propia voz de Jarvis (evita auto-disparo).
const GRACIA_MS = 700;

// Servicio TTS local con la voz CLONADA de Jarvis (dashboard/tts/servidor.py, solo
// portátil con GPU). Si no responde —otro equipo, o servicio apagado— la voz
// cae al `speechSynthesis` del navegador. Se puede apuntar a otro host con VITE_TTS_URL.
const TTS_URL = (import.meta.env.VITE_TTS_URL as string | undefined) ?? "http://localhost:8123";

function CtorRec(): any {
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
}

// Separa "jarvis, muéstrame el sueño" en su comando, aceptando cualquier variante de
// la palabra clave (usa la ÚLTIMA aparición). Si solo se dijo el nombre, marca que hay
// que despertar y esperar el comando en la siguiente frase.
function extraer(texto: string, despierto: boolean): { comando: string | null; despertar: boolean } {
  WAKE.lastIndex = 0;
  let m: RegExpExecArray | null, ultimo: RegExpExecArray | null = null;
  while ((m = WAKE.exec(texto)) !== null) ultimo = m;
  if (ultimo) {
    const resto = texto.slice(ultimo.index + ultimo[0].length).replace(/^[\s,.:;!?¡¿-]+/, "").trim();
    return resto ? { comando: resto, despertar: false } : { comando: null, despertar: true };
  }
  if (despierto) {
    const c = texto.trim();
    if (c) return { comando: c, despertar: false };
  }
  return { comando: null, despertar: despierto };
}

function vozEspanola(): SpeechSynthesisVoice | null {
  try {
    const vs = window.speechSynthesis.getVoices();
    // v1: la primera voz en español disponible. El timbre "Jarvis" a medida es
    // etapa 2 (XTTS/nube); aquí solo importa que suene en español.
    return vs.find((v) => /^es(-|_)/i.test(v.lang)) ?? null;
  } catch {
    return null;
  }
}

export type Voz = {
  soportado: boolean;
  vozActiva: boolean;
  estado: EstadoVoz;
  alternar: () => void;         // enciende / apaga el modo voz
  parar: () => void;            // corta lo que esté diciendo (barge-in)
  decir: (texto: string) => void; // lee un texto en alto (lo llama el chat)
};

export function useVoz({ onComando }: { onComando: (texto: string) => void }): Voz {
  const soportado =
    typeof window !== "undefined" && !!CtorRec() && typeof window.speechSynthesis !== "undefined";

  const [vozActiva, setVozActiva] = useState(false);
  const [estado, setEstado] = useState<EstadoVoz>("off");

  const recRef = useRef<any>(null);
  const activaRef = useRef(false);
  const estadoRef = useRef<EstadoVoz>("off");
  const despiertoRef = useRef(false);
  const ignorarHastaRef = useRef(0);
  const comandoRef = useRef(onComando);
  useEffect(() => {
    comandoRef.current = onComando;
  }, [onComando]);

  const irA = useCallback((e: EstadoVoz) => {
    estadoRef.current = e;
    setEstado(e);
  }, []);

  // Relanza el reconocedor si toca (Chrome corta la escucha continua cada ~1 min).
  const relanzar = useCallback(() => {
    if (!activaRef.current) return;
    try {
      recRef.current?.start();
    } catch {
      /* ya estaba en marcha: start() lanza si la sesión sigue viva; no pasa nada */
    }
  }, []);

  // Se crea el reconocedor una sola vez, la primera que se enciende la voz.
  const asegurarRec = useCallback(() => {
    if (recRef.current || !soportado) return recRef.current;
    const r = new (CtorRec())();
    r.lang = "es-ES";
    r.continuous = true;
    r.interimResults = false; // solo frases finales: más simple para sacar el comando
    r.maxAlternatives = 1;

    r.onresult = (ev: any) => {
      // Mientras habla (o justo después), se ignora TODO: así no se oye a sí mismo.
      if (estadoRef.current === "hablando" || Date.now() < ignorarHastaRef.current) return;
      const res = ev.results?.[ev.results.length - 1];
      if (!res || !res.isFinal) return;
      const texto = String(res[0]?.transcript ?? "").trim();
      if (!texto) return;
      const { comando, despertar } = extraer(texto, despiertoRef.current);
      if (comando) {
        despiertoRef.current = false;
        irA("dormido");
        comandoRef.current(comando);
      } else if (despertar) {
        despiertoRef.current = true;
        irA("escuchando");
      }
    };

    r.onend = () => {
      // Reanuda la escucha continua salvo que estemos hablando o apagados.
      if (activaRef.current && estadoRef.current !== "hablando") {
        setTimeout(relanzar, 250); // pequeño respiro: evita bucles de start/stop
      }
    };

    r.onerror = (ev: any) => {
      if (ev?.error === "not-allowed" || ev?.error === "service-not-allowed") {
        apagarRef.current(); // sin permiso de micro: apaga el modo voz
      }
      // "no-speech" / "network" / "aborted": onend se encarga de reanudar.
    };

    recRef.current = r;
    return r;
  }, [soportado, irA, relanzar]);

  const encender = useCallback(() => {
    if (!soportado) return;
    activaRef.current = true;
    despiertoRef.current = false;
    setVozActiva(true);
    asegurarRec();
    // Carga perezosa del catálogo de voces (algunos navegadores lo traen vacío
    // hasta el primer acceso / evento onvoiceschanged).
    try {
      window.speechSynthesis.getVoices();
    } catch {
      /* sin síntesis: seguirá funcionando la escucha */
    }
    irA("dormido");
    relanzar();
  }, [soportado, asegurarRec, irA, relanzar]);

  const apagar = useCallback(() => {
    activaRef.current = false;
    despiertoRef.current = false;
    setVozActiva(false);
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* nada que cancelar */
    }
    try {
      recRef.current?.stop();
    } catch {
      /* ya estaba parado */
    }
    irA("off");
  }, [irA]);

  // `onerror` (dentro del reconocedor creado una vez) necesita la versión actual de
  // `apagar` sin recrear el reconocedor: se guarda en una ref.
  const apagarRef = useRef(apagar);
  useEffect(() => {
    apagarRef.current = apagar;
  }, [apagar]);

  const alternar = useCallback(() => {
    if (activaRef.current) apagar();
    else encender();
  }, [apagar, encender]);

  const finHabla = useCallback(() => {
    ignorarHastaRef.current = Date.now() + GRACIA_MS;
    if (activaRef.current) {
      irA("dormido");
      relanzar();
    } else {
      irA("off");
    }
  }, [irA, relanzar]);

  // El audio de la voz clonada que esté sonando (para poder cortarlo en barge-in).
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pararAudio = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    audioRef.current = null;
    try {
      a.pause();
    } catch {
      /* ya parado */
    }
    if (a.src.startsWith("blob:")) URL.revokeObjectURL(a.src);
  }, []);

  // Respaldo: la voz del navegador (speechSynthesis). Se usa si el servicio TTS no
  // está disponible. Es la de antes; ahora es el plan B, no la principal.
  const decirNavegador = useCallback(
    (limpio: string) => {
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* nada que cancelar */
      }
      const u = new SpeechSynthesisUtterance(limpio);
      u.lang = "es-ES";
      const v = vozEspanola();
      if (v) u.voice = v;
      u.onend = finHabla;
      u.onerror = finHabla;
      try {
        window.speechSynthesis.speak(u);
      } catch {
        finHabla();
      }
    },
    [finHabla],
  );

  const decir = useCallback(
    (texto: string) => {
      if (!activaRef.current || !soportado) return; // solo lee en voz alta con la voz activa
      const limpio = texto.replace(/\s+/g, " ").trim();
      if (!limpio) return;
      // Callar lo anterior y pasar a "hablando" YA: así el mic queda mudo durante la
      // generación (que tarda unos segundos), no solo mientras suena (anti-eco).
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* nada que cancelar */
      }
      pararAudio();
      irA("hablando");
      // Voz clonada del servicio; si falla (no está levantado), voz del navegador.
      fetch(`${TTS_URL}/voz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: limpio }),
      })
        .then((r) => {
          if (!r.ok) throw new Error(String(r.status));
          return r.blob();
        })
        .then((blob) => {
          // Si mientras generaba se canceló (barge-in) o se apagó, no reproducir.
          if (estadoRef.current !== "hablando" || !activaRef.current) return;
          const a = new Audio(URL.createObjectURL(blob));
          audioRef.current = a;
          a.onended = finHabla;
          a.onerror = () => finHabla();
          a.play().catch(() => finHabla());
        })
        .catch(() => {
          if (estadoRef.current === "hablando" && activaRef.current) decirNavegador(limpio);
        });
    },
    [soportado, irA, finHabla, pararAudio, decirNavegador],
  );

  const parar = useCallback(() => {
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* nada que cancelar */
    }
    pararAudio();
    finHabla();
  }, [finHabla, pararAudio]);

  // Al desmontar: soltar micro, síntesis y el audio clonado que estuviera sonando.
  useEffect(() => {
    return () => {
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* */
      }
      pararAudio();
      try {
        recRef.current?.stop();
      } catch {
        /* */
      }
    };
  }, [pararAudio]);

  return { soportado, vozActiva, estado, alternar, parar, decir };
}
