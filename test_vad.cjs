#!/usr/bin/env node
/* Comprobaciones del detector de voz.  `node test_vad.cjs`
 *
 * Los umbrales del VAD se afinaron de oído, con el usuario delante, y la tabla de
 * perillas del HANDOFF §13 pide expresamente rehacer esta prueba cada vez que se
 * muevan. Hasta ahora vivía en `scratchpad/` y no entraba al repo, así que en la
 * práctica no existía.
 *
 * Lo que se vigila es el falso positivo, que es el fallo que NO se ve: Jarvis se calla
 * a media frase y desde fuera parece que va lento o que se corta solo.
 *
 * Se transpila `vad.ts` con esbuild (ya está como dependencia de vite). Las funciones
 * que se prueban son puras y no tocan el navegador, así que no hace falta simular nada
 * — ésa era la otra trampa: en Node `navigator` y `performance` son globales nativos y
 * asignarlos no toma efecto.
 */
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const FRENTE = path.join(__dirname, "dashboard", "frontend");
const salida = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "vad-")), "vad.cjs");
execFileSync("npx", ["esbuild", "src/lib/vad.ts", "--format=cjs", "--platform=node",
                     "--log-level=warning", "--outfile=" + salida],
             { cwd: FRENTE, stdio: "inherit" });
const vad = require(salida);

const FRAME = 1000 / 60;   // el bucle va en requestAnimationFrame
const ok = (c, m) => { if (!c) { console.error("FALLO:", m); process.exit(1); } };

/** Pasa una señal por la máquina de corte. `señal` es una lista de [rms, cuántos ms]. */
function correr(senal, { hablando = false, suelo = 0.003 } = {}) {
  const st = { desde: 0, hastaCalla: 0, avisado: false };
  let t = 0, cortes = 0;
  for (const [rms, ms] of senal) {
    for (let i = 0; i < Math.round(ms / FRAME); i++) {
      const u = vad.umbralDe(suelo, hablando);
      if (vad.pasoCorte(st, rms, u, t) === "corta") cortes++;
      t += FRAME;
    }
  }
  return cortes;
}

// --- lo que NO debe cortar ---------------------------------------------------
ok(correr([[0.002, 3000]]) === 0, "el silencio no corta");
ok(correr([[0.0, 500], [0.25, 140], [0.0, 500]]) === 0,
   "un golpe (140 ms) no corta: dura menos que SOSTENIDO_MS");
ok(correr([[0.004, 400], [0.008, 300], [0.004, 400]]) === 0,
   "una respiración por debajo del umbral no corta");
// Y lo que NO hace: una respiración FUERTE cerca del micro (0.02) sí cruza el umbral de
// una sala en silencio (0.012) y corta. Es un riesgo conocido y sin resolver —§13 lo
// lista entre lo que nunca se probó— y se deja escrito aquí para que quede medido y no
// se descubra otra vez de oído. El VAD mide energía, no timbre.
ok(correr([[0.02, 400]]) === 1, "una respiración fuerte SÍ corta: limitación conocida");
ok(correr([[0.030, 4000]], { hablando: true }) === 0,
   "el eco de Jarvis a 0.030 no supera MINIMO_HABLANDO (0.038)");

// EL CASO DEL COCHE: ruido que fluctúa alrededor del umbral. Cruza, baja 150 ms, vuelve
// a cruzar. Antes esto cortaba, porque el reseteo de la cuenta exigía 250 ms seguidos
// por debajo y aquí no los hay nunca.
const coche = [];
for (let i = 0; i < 12; i++) { coche.push([0.055, 120]); coche.push([0.030, 150]); }
ok(correr(coche, { hablando: true }) === 0,
   "ruido de coche fluctuante: cruza el umbral pero nunca 220 ms seguidos");

// --- lo que SÍ debe cortar ---------------------------------------------------
ok(correr([[0.0, 300], [0.08, 400], [0.0, 300]], { hablando: true }) === 1,
   "la voz del usuario por encima del eco corta, y una sola vez");
ok(correr([[0.06, 300]]) === 1, "con Jarvis callado también corta");
// Un hueco corto (50 ms) es una consonante sorda, no un ruido nuevo: no reinicia.
ok(correr([[0.08, 150], [0.0, 50], [0.08, 150]], { hablando: true }) === 1,
   "un hueco de 50 ms dentro de una frase no reinicia la cuenta");

// --- el suelo de ruido -------------------------------------------------------
// Sube hacia el ruido ambiente en unos segundos. Con el 0.0006 de antes, en 4 s solo
// recorría un 1,4 % y en un coche no llegaba nunca.
let suelo = 0.003;
for (let i = 0; i < Math.round(4000 / FRAME); i++) suelo = vad.sueloSiguiente(suelo, 0.05, false);
ok(suelo > 0.030, `en 4 s el suelo debe acercarse al ruido real, y va por ${suelo.toFixed(4)}`);

// Pero NO mientras Jarvis habla: ahí aprendería su propio eco, el umbral subiría con él
// y el corte por voz moriría poco a poco y sin síntoma.
let congelado = 0.003;
for (let i = 0; i < 600; i++) congelado = vad.sueloSiguiente(congelado, 0.05, true);
ok(congelado === 0.003, "el suelo se congela mientras Jarvis habla");

// Y baja al instante: una sala puede quedarse en silencio de golpe.
ok(vad.sueloSiguiente(0.05, 0.001, false) === 0.001, "el suelo baja de golpe");

// --- el umbral ---------------------------------------------------------------
ok(vad.umbralDe(0.003, true) === 0.038, "con la sala en silencio manda el mínimo absoluto");
ok(vad.umbralDe(0.008, true) > 0.038, "con algo de ruido manda el relativo al suelo");

// El TECHO: sin él, un suelo de coche daba un umbral de 0,2-0,3 y la voz del usuario
// (medida en 0,0365-0,0755) no lo alcanzaba nunca. Jarvis dejaría de cortarse, pero
// tampoco se le podría cortar.
ok(vad.umbralDe(0.05, true) <= 0.10, "el umbral no se dispara con ruido alto");
ok(vad.umbralDe(0.50, true) <= 0.10, "por mucho ruido que haya, el techo aguanta");
// Y con el techo puesto, una voz normal por encima del ruido sigue cortando.
ok(correr([[0.0, 300], [0.15, 400]], { hablando: true, suelo: 0.05 }) === 1,
   "en un sitio ruidoso el usuario todavía puede cortarle");

console.log("OK");
