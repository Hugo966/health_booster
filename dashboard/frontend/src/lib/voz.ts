import { useCallback, useEffect, useRef, useState } from "react";

// Capa de voz de Jarvis, manos libres: escucha pasiva la palabra "Jarvis", captura
// el comando, lo manda al chat, y lee en alto la respuesta. Desacoplada del chat:
// recibe `onComando` (qué hacer con lo que oye) y expone `decir` (para que el chat
// le pase la respuesta). Backends (wake word / TTS) a propósito simples y
// sustituibles: v1 con Web Speech del navegador (gratis, sin deps, Chrome). La voz
// "Jarvis" de verdad (XTTS/nube) se enchufa después cambiando solo `decir`.
//
// Máquina de estados (rediseñada a petición de Hugo — comportamiento tipo Jarvis):
//   off      -> voz apagada, micro cerrado. Solo el estado inicial; el orbe no vuelve aquí.
//   reposo   -> el micro sigue vivo pero SOLO reacciona a "Jarvis" (Hugo lo llama
//               "desactivado": no capta tu charla normal, pero te oye si lo llamas).
//   activo   -> conversación: capta TODO lo que dices sin decir "Jarvis", y tras
//               contestar SE QUEDA aquí (sigue escuchando).
//   hablando -> leyendo la respuesta (se ignora la escucha: anti-eco).
// El orbe alterna activo <-> reposo; "Jarvis" en reposo salta a activo.
export type EstadoVoz = "off" | "reposo" | "activo" | "hablando";

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

// WAV mudo (cabecera sin muestras): sirve para "estrenar" el elemento de audio dentro
// del clic que enciende la voz y que el navegador le dé permiso para sonar después.
const SILENCIO =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAgD4AAAB9AAACABAAZGF0YQAAAAA=";

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

// Trocea la respuesta en frases para generarlas y reproducirlas EN CADENA: así se oye
// la primera enseguida mientras se generan las siguientes, y cada trozo corto evita el
// precipicio de latencia del TTS (con textos largos la caché de atención se sale de los
// 6 GB de VRAM y Windows derrama a RAM → 10x más lento). Los fragmentos muy cortos se
// pegan a la frase anterior para no soltar microclips.
function partir(texto: string): string[] {
  const frases = texto.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g) ?? [texto];
  const out: string[] = [];
  for (const f of frases) {
    const s = f.trim();
    if (!s) continue;
    if (out.length && s.length < 25) out[out.length - 1] += " " + s;
    else out.push(s);
  }
  return out.length ? out : [texto];
}

// Habla "en directo": el chat va empujando frases según el modelo las escribe y aquí
// se generan y encadenan en orden. Cerrar avisa de que ya no vienen más.
// Qué muletilla pega con lo que acaba de decir Hugo; lo decide Haiku en el backend.
// "nada" = ninguna (saludos y frases sueltas: un "déjame que lo mire" ahí es ridículo).
export type TipoMuletilla = "consulta" | "neutra" | "nada" | "segunda";

// Silencio entre la primera muletilla y la de continuación. Pegadas sonaban a atropello.
// 2,5 s no es raro: quien dice "mmm, déjame pensar" se queda callado un rato. Y cuanto
// más larga, más veces llega la respuesta real mientras tanto y la segunda no hace falta.
const PAUSA_MULETILLA_MS = 2500;

export type Habla = {
  // Qué pool de muletillas toca ("consulta" / "neutra") lo decide el enrutado en el
  // backend y llega ~1 s después de abrir el turno, así que se arranca aquí, no al
  // abrir. Cadena vacía = ninguna (saludos, que ya vienen con respuesta propia).
  muletilla: (tipo: string) => void;
  empujar: (frase: string) => void;
  cerrar: () => void;
};

export type Voz = {
  soportado: boolean;
  vozActiva: boolean;
  estado: EstadoVoz;
  sonando: boolean;             // hay voz saliendo AHORA (no solo turno abierto)
  alternar: () => void;         // enciende / apaga el modo voz
  parar: () => void;            // corta lo que esté diciendo (barge-in)
  decir: (texto: string) => void; // lee un texto en alto (lo llama el chat)
  hablar: () => Habla;          // abre un turno al que ir empujando frases sueltas
};

export function useVoz({ onComando }: { onComando: (texto: string) => void }): Voz {
  const soportado =
    typeof window !== "undefined" && !!CtorRec() && typeof window.speechSynthesis !== "undefined";

  const [vozActiva, setVozActiva] = useState(false);
  const [estado, setEstado] = useState<EstadoVoz>("off");
  // ¿Está SONANDO audio ahora mismo? Va aparte de `estado` a propósito: el estado pasa
  // a "hablando" en cuanto se abre el turno (así el micro queda mudo durante toda la
  // generación y no se oye a sí mismo), pero el orbe no debe ponerse a "hablando" hasta
  // que de verdad salga voz — hasta entonces sigue "pensando".
  const [sonando, setSonando] = useState(false);

  const recRef = useRef<any>(null);
  const activaRef = useRef(false);
  const estadoRef = useRef<EstadoVoz>("off");
  const ignorarHastaRef = useRef(0);
  const comandoRef = useRef(onComando);
  useEffect(() => {
    comandoRef.current = onComando;
  }, [onComando]);

  // UN ÚNICO elemento de audio para toda la sesión, "desbloqueado" en el clic que
  // enciende la voz. Antes se creaba un `new Audio()` por frase y Chrome bloqueaba la
  // reproducción cuando no había un gesto del usuario reciente: dentro de un panel la
  // respuesta se generaba (el servicio devolvía 200) pero no sonaba hasta que Hugo
  // pulsaba para salir, y entonces soltaba lo pendiente de golpe. Reutilizar el elemento
  // que ya tiene permiso lo evita.
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const asegurarAudio = useCallback(() => {
    if (!audioRef.current) audioRef.current = new Audio();
    return audioRef.current;
  }, []);

  const soltarUrl = useCallback(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

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
      // En "activo" cualquier frase es un comando (sin wake word); en "reposo" solo
      // cuenta si oye "Jarvis" (con o sin comando detrás). Al captar algo, pasa a
      // activo y se queda ahí: la conversación sigue abierta.
      const { comando, despertar } = extraer(texto, estadoRef.current === "activo");
      if (comando) {
        irA("activo");
        comandoRef.current(comando);
      } else if (despertar) {
        irA("activo");
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

  // Encender = entrar directo en "activo": Hugo quiere que al activar el orbe le
  // escuche ya, sin tener que decir "Jarvis".
  const encender = useCallback(() => {
    if (!soportado) return;
    activaRef.current = true;
    setVozActiva(true);
    asegurarRec();
    // Este `encender` sale SIEMPRE de un clic en el orbe, así que es el único momento
    // garantizado con gesto del usuario: se reproduce un WAV mudo para que el navegador
    // dé permiso permanente a este elemento. Sin esto, las respuestas dentro de un panel
    // no sonaban hasta el siguiente clic.
    try {
      const a = asegurarAudio();
      a.src = SILENCIO;
      void a.play().catch(() => {});
    } catch {
      /* si el navegador no deja, quedará el respaldo de speechSynthesis */
    }
    // Carga perezosa del catálogo de voces (algunos navegadores lo traen vacío
    // hasta el primer acceso / evento onvoiceschanged).
    try {
      window.speechSynthesis.getVoices();
    } catch {
      /* sin síntesis: seguirá funcionando la escucha */
    }
    irA("activo");
    relanzar();
  }, [soportado, asegurarRec, irA, relanzar]);

  // Apagado total: micro cerrado, no oye ni "Jarvis". Hoy solo se llega aquí si el
  // navegador niega el permiso de micro (ver onerror) o al desmontar; el orbe alterna
  // activo/reposo y no vuelve nunca a "off".
  const apagar = useCallback(() => {
    activaRef.current = false;
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

  // El orbe alterna: off -> activo (encender), activo -> reposo (Hugo lo "desactiva":
  // deja de captar su charla pero sigue oyendo "Jarvis"), reposo -> activo. No vuelve a
  // "off": el reposo mantiene el micro vivo para el wake word, así "Jarvis" siempre le
  // despierta. Si algún día se quiere un mute duro, iría aquí (p.ej. pulsación larga).
  const alternar = useCallback(() => {
    if (!soportado) return;
    const e = estadoRef.current;
    if (e === "off") encender();
    else if (e === "activo") irA("reposo"); // no paramos el reconocedor: sigue oyendo "Jarvis"
    else {
      irA("activo");
      relanzar();
    }
  }, [soportado, encender, irA, relanzar]);

  const finHabla = useCallback(() => {
    ignorarHastaRef.current = Date.now() + GRACIA_MS;
    if (activaRef.current) {
      irA("activo"); // tras contestar se queda escuchando (Hugo)
      relanzar();
    } else {
      irA("off");
    }
  }, [irA, relanzar]);

  // Turno de habla: cada `decir` incrementa este contador. La tubería de frases lleva
  // su propio número y se aborta en cuanto deja de ser el turno vigente (barge-in,
  // apagado o una respuesta nueva). Así no se pisan dos respuestas.
  const turnoRef = useRef(0);
  // Corta lo que suene, pero CONSERVA el elemento (perdería el permiso de sonar).
  const pararAudio = useCallback(() => {
    setSonando(false);
    const a = audioRef.current;
    if (!a) return;
    a.onended = null;
    a.onerror = null;
    a.onpause = null; // se limpia antes de pausar: si no, dispara el fin del turno
    try {
      a.pause();
    } catch {
      /* ya parado */
    }
    soltarUrl();
  }, [soltarUrl]);

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

  // Pide al servicio TTS el audio de un trozo. Devuelve null si el turno ya caducó.
  const generar = useCallback(async (texto: string, turno: number,
                                     rapido = false): Promise<Blob | null> => {
    const r = await fetch(`${TTS_URL}/voz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto, rapido }),
    });
    if (!r.ok) throw new Error(String(r.status));
    const blob = await r.blob();
    return turnoRef.current === turno ? blob : null;
  }, []);

  // Reproduce un blob y resuelve cuando termina (o si se corta / falla). El `pause` de
  // barge-in también lo resuelve, para que la cadena no se quede colgada.
  const reproducir = useCallback(
    (blob: Blob, turno: number): Promise<void> => {
      return new Promise((resolve) => {
        if (turnoRef.current !== turno) return resolve();
        const a = asegurarAudio();
        soltarUrl(); // suelta el blob de la frase anterior
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        let hecho = false;
        const fin = () => {
          if (hecho) return;
          hecho = true;
          setSonando(false);
          resolve();
        };
        a.onplaying = () => setSonando(true); // ahora sí: el orbe pasa a "hablando"
        a.onended = fin;
        a.onerror = fin;
        a.onpause = fin; // barge-in: pararAudio() pausa -> resuelve y la cadena corta
        a.src = url;
        a.play().catch(fin);
      });
    },
    [asegurarAudio, soltarUrl],
  );

  const decir = useCallback(
    (texto: string) => {
      if (!activaRef.current || !soportado) return; // solo lee en voz alta con la voz activa
      const limpio = texto.replace(/\s+/g, " ").trim();
      if (!limpio) return;
      // Nuevo turno: invalida cualquier tubería anterior. Callar lo previo y pasar a
      // "hablando" YA, así el mic queda mudo durante toda la generación (anti-eco).
      const turno = ++turnoRef.current;
      try {
        window.speechSynthesis.cancel();
      } catch {
        /* nada que cancelar */
      }
      pararAudio();
      irA("hablando");

      // Tubería: se genera el primer trozo y, mientras suena, se va generando el
      // siguiente (el servidor procesa de uno en uno, así que basta con ir 1 por
      // delante). Cada trozo corto se mantiene en el régimen rápido del TTS.
      const trozos = partir(limpio);
      let siguiente = generar(trozos[0], turno);
      (async () => {
        for (let i = 0; i < trozos.length; i++) {
          let blob: Blob | null;
          try {
            blob = await siguiente;
          } catch {
            // Falla el servicio (apagado, otro equipo…): plan B, voz del
            // navegador, pero solo si aún es nuestro turno y no habíamos empezado a sonar.
            if (i === 0 && turnoRef.current === turno && activaRef.current) decirNavegador(limpio);
            return;
          }
          if (turnoRef.current !== turno || !activaRef.current || !blob) return;
          // Arranca la generación del siguiente ANTES de ponerse a reproducir este.
          siguiente =
            i + 1 < trozos.length
              ? generar(trozos[i + 1], turno).catch(() => null)
              : Promise.resolve(null);
          await reproducir(blob, turno);
          if (turnoRef.current !== turno) return; // barge-in mientras sonaba
        }
        finHabla();
      })();
    },
    [soportado, irA, finHabla, pararAudio, decirNavegador, generar, reproducir],
  );

  // Turno de habla incremental: el chat empuja frases conforme llegan del modelo. Cada
  // una se manda a generar EN CUANTO llega (así se solapa con lo que esté sonando) pero
  // se reproducen en orden, encadenadas. Es lo que permite que Jarvis empiece a hablar
  // con la primera frase en vez de esperar a que termine de redactar.
  const hablar = useCallback((): Habla => {
    const mudo: Habla = { muletilla: () => {}, empujar: () => {}, cerrar: () => {} };
    if (!activaRef.current || !soportado) return mudo;
    const turno = ++turnoRef.current;
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* nada que cancelar */
    }
    pararAudio();
    irA("hablando");

    // Muletilla ("déjame ver…"): ya generada y cacheada en el servicio, así que suena
    // al instante y tapa los ~9 s que v3 tarda en tener lista la primera frase de verdad.
    // Se encadena como una frase más: el orden se respeta y el barge-in la corta igual.
    let primeraLista = false; // ¿ya tenemos audio real esperando?
    let ultimaMuletilla = "";

    const pedirMuletilla = async (tipo: TipoMuletilla): Promise<Blob | null> => {
      try {
        const r = await fetch(
          `${TTS_URL}/muletilla?tipo=${tipo}&evitar=${encodeURIComponent(ultimaMuletilla)}`,
        );
        if (!r.ok || r.status === 204) return null;
        ultimaMuletilla = r.headers.get("X-Muletilla") ?? "";
        return await r.blob();
      } catch {
        return null;
      }
    };

    let cadena: Promise<void> = Promise.resolve();
    // Las generaciones también van en fila: como MUCHO una en vuelo. Lanzarlas todas a
    // la vez hacía que ElevenLabs las encolara por límite de concurrencia y la primera
    // —la única que importa para empezar a hablar— pasaba de 3,5 s a 5,8 s.
    let ultimaGen: Promise<Blob | null> = Promise.resolve(null);
    let vivas = 0;
    let cerrado = false;
    const quizaFin = () => {
      if (cerrado && vivas === 0 && turnoRef.current === turno) finHabla();
    };

    return {
      muletilla(tipo: string) {
        // Vacío (saludos, que ya llevan respuesta propia) o respuesta ya lista: callarse.
        if (!tipo || primeraLista || turnoRef.current !== turno) return;
        cadena = cadena.then(async () => {
          if (primeraLista || turnoRef.current !== turno) return;
          // Pregrabadas y generadas con v3: suenan al instante Y con la ironía del
          // personaje. Escribirlas a medida quedaba más pegado al contexto, pero había
          // que sintetizarlas en Flash para llegar a tiempo y salían planas.
          const b = await pedirMuletilla(tipo as TipoMuletilla);
          if (b && turnoRef.current === turno) await reproducir(b, turno);
          // Si al acabar aún no hay audio real, se encadena otra: el silencio es lo que
          // le hace creer a Hugo que ya ha terminado y ponerse a hablar encima. Pero va
          // del pool "segunda" (cortas, de continuación: "mmm… a ver") y tras una PAUSA
          // — pegadas y repitiendo el mismo "déjame que mire" sonaban redundantes.
          if (!primeraLista && turnoRef.current === turno) {
            await new Promise((r) => setTimeout(r, PAUSA_MULETILLA_MS));
            // La pausa además da margen: si la respuesta real llega mientras, no hace falta.
            if (!primeraLista && turnoRef.current === turno) {
              const b2 = await pedirMuletilla("segunda");
              if (b2 && !primeraLista && turnoRef.current === turno) {
                await reproducir(b2, turno);
              }
            }
          }
        });
      },
      empujar(frase: string) {
        const limpio = frase.replace(/\s+/g, " ").trim();
        if (!limpio || turnoRef.current !== turno) return;
        vivas++;
        const gen = ultimaGen
          .then(() => generar(limpio, turno))
          .then((b) => {
            primeraLista = true; // ya hay audio real: no encadenar más muletillas
            return b;
          })
          .catch(() => null);
        ultimaGen = gen;
        const seguir = async () => {
          const blob = await gen;
          if (turnoRef.current !== turno || !blob) return;
          await reproducir(blob, turno);
        };
        const contar = () => {
          vivas--;
          quizaFin();
        };
        cadena = cadena.then(seguir).then(contar, contar);
      },
      cerrar() {
        cerrado = true;
        quizaFin();
      },
    };
  }, [soportado, irA, pararAudio, finHabla, generar, reproducir]);

  const parar = useCallback(() => {
    turnoRef.current++; // invalida la tubería de frases en curso
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

  return { soportado, vozActiva, estado, sonando, alternar, parar, decir, hablar };
}
