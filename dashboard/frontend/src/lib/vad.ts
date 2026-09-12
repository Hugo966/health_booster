// Detector de voz (VAD) por energía del micro. Existe para UNA cosa: saber que Hugo ha
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
//      queda al eco tras la cancelación es flojo; la voz de Hugo, de cerca, no.
//   3. Hay que superar el umbral de forma SOSTENIDA. Un golpe o una tos son un pico
//      corto; hablar, no. Fue decisión suya: prefiere que solo le calle la voz de verdad.

// Cuánto hay que estar por encima del umbral para dar la voz por buena.
// SUBIR si un ruido corto le corta a Jarvis; BAJAR si cortarle se siente lento.
// 300 se probó en vivo y le daba tiempo a terminar la frase; 220 sigue descartando un
// golpe o una tos (duran menos de 150 ms) pero corta a tiempo.
const SOSTENIDO_MS = 220;
// Fin de la voz: cuánto silencio para dar por terminado el tramo.
const FIN_MS = 250;
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
// Con qué rapidez se aprende el ruido de fondo. Baja al instante (una habitación puede
// quedarse en silencio de golpe) y sube muy despacio, para que una frase larga no se
// confunda con ruido ambiente.
const SUBIDA_SUELO = 0.0006;

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
  /** Se llama cuando Hugo lleva `SOSTENIDO_MS` hablando. */
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
  let desde = 0;      // cuándo empezó el tramo por encima del umbral
  let hastaCalla = 0; // cuándo se vio energía por última vez
  let avisado = false;
  let ultimaTraza = 0;

  const medir = () => {
    if (!vivo || !analizador || !buf) return;
    analizador.getFloatTimeDomainData(buf);
    let suma = 0;
    for (let i = 0; i < buf.length; i++) suma += buf[i] * buf[i];
    const rms = Math.sqrt(suma / buf.length);
    nivelActual = rms;

    const hablando = opciones.hablandoJarvis();
    // Congelado mientras Jarvis habla: si no, el suelo aprende SU voz, el umbral sube
    // con ella y el corte por voz deja de funcionar poco a poco y sin ningún síntoma.
    if (!hablando) {
      if (rms < suelo) suelo = rms;
      else suelo += (rms - suelo) * SUBIDA_SUELO;
    }

    const umbral = Math.max(
      hablando ? MINIMO_HABLANDO : MINIMO,
      suelo * (hablando ? MULT_HABLANDO : MULT),
    );
    const ahora = performance.now();

    // Cada ~1 s, mientras Jarvis habla, se deja el nivel en la traza: es el único modo de
    // afinar `MINIMO_HABLANDO` con números en vez de a oído (cuánto mide su eco, cuánto
    // mides tú por encima de él).
    if (hablando && ahora - ultimaTraza > 1000) {
      ultimaTraza = ahora;
      opciones.traza?.(
        `VAD mientras habla: nivel ${rms.toFixed(4)} / umbral ${umbral.toFixed(4)}`,
      );
    }

    if (rms > umbral) {
      if (!desde) desde = ahora;
      hastaCalla = ahora;
      if (!avisado && ahora - desde >= SOSTENIDO_MS) {
        avisado = true;
        opciones.traza?.(
          `VAD: voz sostenida ${SOSTENIDO_MS}ms`,
          { rms: +rms.toFixed(4), umbral: +umbral.toFixed(4), suelo: +suelo.toFixed(4), hablando },
        );
        opciones.alHablar();
      }
    } else if (desde && ahora - hastaCalla > FIN_MS) {
      if (avisado) opciones.alCallar?.();
      desde = 0;
      avisado = false;
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
        suelo = MINIMO;
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
