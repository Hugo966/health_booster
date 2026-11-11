// Detector de voz (VAD) por energía del micro. Existe para UNA cosa: saber que el usuario ha
// empezado a hablar MIENTRAS Jarvis habla, para poder callarle.
//
// Por qué no basta con el reconocedor de Chrome: tarda entre 300 ms y 1 s en soltar
// siquiera un parcial, y durante ese rato Jarvis sigue soltando su parrafada. Aquí se
// mira la energía del micro cada frame, así que el corte llega en cuanto hay voz.
//
// El problema difícil es el eco: si Jarvis sale por los altavoces, el micro le oye y se
// cortaría a sí mismo. Tres defensas, en orden de importancia:
//   1. `echoCancellation` del navegador, que resta de la señal del micro lo que Chrome
//      está sacando por el altavoz. Con cascos el problema ni existe.
//   2. Mientras Jarvis habla se exige MUCHA más energía (`MULT_HABLANDO`): lo que le
//      queda al eco tras la cancelación es flojo; la voz del usuario, de cerca, no.
//   3. Hay que superar el umbral de forma SOSTENIDA. Un golpe o una tos son un pico
//      corto; hablar, no. Fue decisión suya: prefiere que solo le calle la voz de verdad.

// Cuánto hay que estar por encima del umbral para dar la voz por buena.
// SUBIR si un ruido corto le corta a Jarvis; BAJAR si cortarle se siente lento.
// 300 se probó en vivo y le daba tiempo a terminar la frase; 220 sigue descartando un
// golpe o una tos (duran menos de 150 ms) pero corta a tiempo.
const SOSTENIDO_MS = 220;
// Fin de la voz: cuánto silencio para dar por terminado el tramo.
const FIN_MS = 250;
// Cuánto puede bajar del umbral SIN que la cuenta de `SOSTENIDO_MS` empiece de cero.
// Esto no existía y el reseteo compartía los 250 ms de `FIN_MS`, así que "voz sostenida
// 220 ms" no era sostenida: valía un cruce y otro 220 ms después con un hueco de hasta
// 250 ms en medio. Un ruido que fluctúa alrededor del umbral —la rodadura de un coche,
// los baches, un cambio de marcha— cumple eso todo el rato, y por eso en el coche le
// cortaba sin parar. Una voz de verdad no deja huecos de 80 ms por debajo del umbral.
const HUECO_MAX_MS = 80;
// Cuántas veces por encima del ruido de fondo cuenta como voz, con Jarvis callado.
const MULT = 3.0;
// Lo mismo mientras Jarvis habla. Es LA perilla del caso "altavoces": si Jarvis se corta
// a sí mismo, SUBIRLA; si cuesta que te oiga por encima de él, bajarla.
const MULT_HABLANDO = 6.5;
// Suelo absoluto: en una habitación en silencio el ruido de fondo es casi cero y
// cualquier multiplicador se dispararía con nada.
const MINIMO = 0.012;
// Y el suelo absoluto MIENTRAS Jarvis habla. Va aparte y mucho más alto porque el
// multiplicador no basta: con la sala en silencio el suelo aprendido es ~0.003, así que
// 6.5x seguía dando 0.02 y un eco de altavoz por encima de eso lo superaba — Jarvis se
// cortaba a sí mismo a media frase (lo destapó la prueba de `test_vad`, simulando el eco
// a 0.03; el valor real de esta sala habrá que leerlo en la traza). LA perilla del caso
// altavoces:
//   se corta solo  -> SUBIRLA
//   no te oye por encima de él -> bajarla (con cascos puede bajar mucho)
// 0.05 no llegó a autocortarle en vivo, así que había margen: a 0.038 le oye antes sin
// acercarse todavía al nivel de su propio eco.
const MINIMO_HABLANDO = 0.038;
// Y el TECHO del umbral mientras Jarvis habla. Existe desde que el suelo aprende de
// verdad (antes se borraba en cada frase y el multiplicador era inofensivo): con un
// ruido ambiente de coche, `suelo * 6.5` se va a 0,2-0,3, y los únicos números medidos
// de la voz del usuario son 0,0365-0,0755. Sin tope, el detector deja de cortarle a
// Jarvis... y el usuario tampoco puede cortarle, que es cambiar un fallo por otro.
//
// 0.10 deja sitio a una voz por encima del eco (0.038) sin llegar a donde ya no se
// alcanza. Es una estimación: el número bueno sale de leer la traza EN EL COCHE, viendo
// cuánto mide el ruido y cuánto mide él hablando por encima.
const TECHO_HABLANDO = 0.10;
// Con qué rapidez se aprende el ruido de fondo. Baja al instante (una habitación puede
// quedarse en silencio de golpe) y sube deprisa pero no de golpe.
//
// Era 0.0006, que a 60 fps son ~28 s de constante de tiempo. Sonaba prudente y era
// inútil: el suelo SOLO aprende mientras Jarvis calla, y en modo altavoz eso son los
// pocos segundos entre que se abre el micro y suena la primera nota del TTS. A 0.0006
// cada turno cerraba un 10 % de la distancia al ruido real, así que en un coche el suelo
// no llegaba nunca y el umbral se quedaba clavado en el mínimo absoluto.
//
// 0.004 son ~4 s, que sí caben en esa ventana. Es seguro porque justo ahí el usuario
// acaba de callarse y Jarvis todavía no ha empezado: no hay voz que aprender.
const SUBIDA_SUELO = 0.004;

// Las tres decisiones del detector, aparte y sin tocar el navegador, para que
// `test_vad.cjs` pueda meterles números. Hasta ahora los umbrales solo se podían
// comprobar de oído, y la tabla de perillas del HANDOFF §13 pedía expresamente una
// prueba cada vez que se movieran.

/** El suelo de ruido después de ver `rms`. Congelado mientras Jarvis habla: si no,
 *  aprende su propio eco, el umbral sube con él y el corte por voz deja de funcionar
 *  poco a poco y sin ningún síntoma. */
export function sueloSiguiente(suelo: number, rms: number, hablandoJarvis: boolean): number {
  if (hablandoJarvis) return suelo;
  return rms < suelo ? rms : suelo + (rms - suelo) * SUBIDA_SUELO;
}

/** Umbral de voz: el mayor entre el mínimo absoluto y el relativo al ruido de fondo. */
export function umbralDe(suelo: number, hablandoJarvis: boolean): number {
  const relativo = suelo * (hablandoJarvis ? MULT_HABLANDO : MULT);
  // El techo solo aplica mientras Jarvis habla, que es cuando el umbral decide si le
  // cortan. Con Jarvis callado nadie consume esta decisión (`voz.ts` ignora `alHablar`
  // si no está hablando), así que ahí se deja como estaba.
  const topado = hablandoJarvis ? Math.min(relativo, TECHO_HABLANDO) : relativo;
  return Math.max(hablandoJarvis ? MINIMO_HABLANDO : MINIMO, topado);
}

export type EstadoCorte = { desde: number; hastaCalla: number; avisado: boolean };

/** Un paso de la máquina de "¿esto es voz sostenida?". Muta `st` y dice qué ha pasado. */
export function pasoCorte(
  st: EstadoCorte, rms: number, umbral: number, ahora: number,
): "nada" | "corta" | "calla" {
  if (rms > umbral) {
    // Si el hueco por debajo del umbral ha sido largo, esto es un ruido nuevo y no la
    // continuación del anterior: la cuenta empieza de cero.
    if (st.desde && ahora - st.hastaCalla > HUECO_MAX_MS) {
      st.desde = 0;
      st.avisado = false;
    }
    if (!st.desde) st.desde = ahora;
    st.hastaCalla = ahora;
    if (!st.avisado && ahora - st.desde >= SOSTENIDO_MS) {
      st.avisado = true;
      return "corta";
    }
    return "nada";
  }
  if (st.desde && ahora - st.hastaCalla > FIN_MS) {
    const habia = st.avisado;
    st.desde = 0;
    st.avisado = false;
    return habia ? "calla" : "nada";
  }
  return "nada";
}

export type Vad = {
  /** Enciende el micro. Hay que llamarlo DENTRO de un gesto del usuario. */
  arrancar: () => Promise<boolean>;
  /** Suelta el micro. La promesa se cumple cuando está libre de verdad. */
  parar: () => Promise<void>;
  /** Energía actual, 0-1 aprox. Para pintarla y para depurar. */
  nivel: () => number;
  /** Ruido de fondo aprendido, para depurar. */
  suelo: () => number;
};

export function crearVad(opciones: {
  /** Se llama cuando el usuario lleva `SOSTENIDO_MS` hablando. */
  alHablar: () => void;
  /** Se llama al acabar el tramo de voz. */
  alCallar?: () => void;
  /** ¿Está sonando Jarvis ahora? Endurece el umbral y congela el suelo. */
  hablandoJarvis: () => boolean;
  traza?: (que: string, detalle?: unknown) => void;
}): Vad {
  let ctx: AudioContext | null = null;
  let stream: MediaStream | null = null;
  let analizador: AnalyserNode | null = null;
  // `Float32Array<ArrayBuffer>` explícito: el tipo por defecto admite SharedArrayBuffer y
  // `getFloatTimeDomainData` no lo acepta.
  let buf: Float32Array<ArrayBuffer> | null = null;
  let raf = 0;
  let vivo = false;

  let nivelActual = 0;
  let suelo = MINIMO;
  const estadoCorte: EstadoCorte = { desde: 0, hastaCalla: 0, avisado: false };
  let ultimaTraza = 0;

  const medir = () => {
    if (!vivo || !analizador || !buf) return;
    analizador.getFloatTimeDomainData(buf);
    let suma = 0;
    for (let i = 0; i < buf.length; i++) suma += buf[i] * buf[i];
    const rms = Math.sqrt(suma / buf.length);
    nivelActual = rms;

    const hablando = opciones.hablandoJarvis();
    suelo = sueloSiguiente(suelo, rms, hablando);
    const umbral = umbralDe(suelo, hablando);
    const ahora = performance.now();

    // Cada ~2 s, HABLE O NO Jarvis, se deja el nivel en la traza. Antes solo se trazaba
    // mientras hablaba, y eso dejaba ciego justo lo que hay que mirar en un sitio
    // ruidoso: si el suelo está subiendo hacia el ruido real o se ha quedado clavado.
    // Cada 2 s y no cada 1 porque la traza es un anillo de 80 líneas y lo de antes se
    // pierde.
    if (ahora - ultimaTraza > 2000) {
      ultimaTraza = ahora;
      opciones.traza?.(
        `VAD: nivel ${rms.toFixed(4)} / umbral ${umbral.toFixed(4)} / suelo ` +
        `${suelo.toFixed(4)}${hablando ? " (jarvis hablando)" : ""}`,
      );
    }

    const paso = pasoCorte(estadoCorte, rms, umbral, ahora);
    if (paso === "corta") {
      opciones.traza?.(
        `VAD: voz sostenida ${SOSTENIDO_MS}ms`,
        { rms: +rms.toFixed(4), umbral: +umbral.toFixed(4), suelo: +suelo.toFixed(4), hablando },
      );
      opciones.alHablar();
    } else if (paso === "calla") {
      opciones.alCallar?.();
    }

    raf = requestAnimationFrame(medir);
  };

  return {
    async arrancar() {
      if (vivo) return true;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            // A false a propósito: el control automático de ganancia sube el volumen en
            // los silencios hasta acercar el ruido al umbral, y destroza la escala sobre
            // la que se mide aquí.
            autoGainControl: false,
          },
        });
        ctx = new AudioContext();
        // El navegador crea el contexto suspendido si no viene de un gesto del usuario;
        // sin esto el analizador devolvería ceros y no se detectaría voz JAMÁS.
        if (ctx.state === "suspended") await ctx.resume();
        analizador = ctx.createAnalyser();
        analizador.fftSize = 1024;
        analizador.smoothingTimeConstant = 0;
        ctx.createMediaStreamSource(stream).connect(analizador);
        buf = new Float32Array(analizador.fftSize);
        // Si cambia de altavoces a cascos, la pista muere: sin esto el detector se
        // quedaría mudo para siempre sin avisar.
        stream.getAudioTracks().forEach((t) => {
          t.onended = () => opciones.traza?.("VAD: el micro se ha desconectado");
        });
        vivo = true;
        // El suelo NO se reinicia aquí. En modo altavoz este micro se abre y se cierra
        // una vez por frase de Jarvis, así que ponerlo a `MINIMO` borraba lo aprendido
        // constantemente: el umbral se quedaba clavado en el mínimo absoluto turno tras
        // turno, y en un sitio ruidoso el ruido lo superaba siempre. Es lo que hacía que
        // esperar a que "subiera la media" no sirviera de nada: no subía despacio, se
        // borraba. Vive en el closure y solo muere al apagar la voz del todo.
        opciones.traza?.("VAD: micro abierto");
        raf = requestAnimationFrame(medir);
        return true;
      } catch (e) {
        // Sin permiso o sin micro: se sigue sin corte por voz, que es lo de antes. El
        // botón del orbe sigue cortando, así que no se pierde el control.
        opciones.traza?.("VAD: no se pudo abrir el micro", String(e));
        this.parar();
        return false;
      }
    },
    // Devuelve una promesa que se cumple cuando el micro está SOLTADO DE VERDAD. Importa
    // en Android, donde el reconocedor y esto se pelean por el único micro: si se reabre
    // el reconocedor antes de que esto haya soltado, arranca sordo y se come el principio
    // de la frase. Quien lo reabra debe esperar a esta promesa (ver `finHabla`).
    parar(): Promise<void> {
      vivo = false;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      // `stop()` de la pista es lo que libera el micro, y es síncrono.
      try {
        stream?.getTracks().forEach((t) => t.stop());
      } catch {
        /* ya estaba cerrado */
      }
      // `close()` no lo es: devuelve promesa y hasta que no resuelve el contexto sigue
      // enganchado al dispositivo.
      const cerrado = (async () => {
        try {
          await ctx?.close();
        } catch {
          /* ya estaba cerrado */
        }
      })();
      stream = null;
      ctx = null;
      analizador = null;
      buf = null;
      return cerrado;
    },
    nivel: () => nivelActual,
    suelo: () => suelo,
  };
}
