import { useEffect, useMemo, useRef, useState } from "react";
import { theme } from "../lib/theme";

// Secuencia de arranque. Dos engranajes se lanzan uno contra otro acelerando,
// chocan a saco soltando una explosión de chispas, y engranan girando cada vez
// más rápido (y echando más chispas) hasta que los datos están listos y se
// separan dejando ver el panel.
//
// Para que los engranajes engranen DE VERDAD (y no sean dos ruedas girando cada
// una a su bola) hay tres condiciones, y las tres están cableadas aquí:
//
//   1. Mismo módulo: m = 2·r/n. Con m = 10 salen r=90 con 18 dientes y r=60 con
//      12. Dientes del mismo tamaño en los dos.
//   2. Distancia entre centros = rA + rB = 150 exactos. Ni se solapan ni queda hueco.
//   3. Medio diente de desfase en A, para que su diente caiga en el hueco de B.
//
// El giro va con la Web Animations API y NO con CSS, porque hace falta acelerar
// de forma continua: con `playbackRate` se sube la velocidad sin cortar ni
// reiniciar nada. Y como se aplica el MISMO factor a los dos, la razón 18/12
// entre sus vueltas se mantiene y siguen encajados por rápido que vayan.
// Las chispas van montadas igual, así que acelerar también las multiplica: más
// velocidad = más chispas, gratis.

// Tiempos: el CSS (index.css) repite ENTRADA_MS en sus delays. Si tocas uno, toca el otro.
const ENTRADA_MS = 750;
const GIRO_MIN_MS = 3250; // 750 + 3250 = 4s mínimo de secuencia antes de salir
const SALIDA_MS = 700;
// velocidad del giro = 1 + t/3 → al doble a los 3s, y sigue subiendo sin techo
const SEG_PARA_DOBLAR = 3;

const N_A = 18, R_A = 90;
const N_B = 12, R_B = 60;

// Los centros (215,240) y (365,240) los pone el CSS al colocarlos; aquí solo
// hace falta el punto donde se tocan los dientes, que es de donde salen chispas.
const CY = 240;
const CONTACTO_X = 215 + R_A; // 305

/**
 * Contorno de un engranaje centrado en el origen, como path SVG.
 *
 * Perfil trapezoidal (no involuta: a este tamaño no se nota y el path es la
 * décima parte de largo). Cada diente ocupa un ciclo de `360/n` grados: hueco,
 * flanco de subida, punta, flanco de bajada. La punta queda centrada en la
 * mitad del ciclo y el hueco a caballo entre dos ciclos.
 */
function perfil(n: number, rPaso: number, faseGrados = 0): string {
  const m = (2 * rPaso) / n;
  const rPie = rPaso - 1.15 * m;
  const rPunta = rPaso + 0.8 * m;
  const paso = 360 / n;
  const tramos: [number, number][] = [
    [0.0, rPie], [0.3, rPie], [0.38, rPunta], [0.62, rPunta], [0.7, rPie],
  ];
  const pts: string[] = [];
  for (let i = 0; i < n; i++) {
    for (const [f, r] of tramos) {
      const a = ((i + f) * paso + faseGrados) * (Math.PI / 180);
      pts.push(`${(Math.cos(a) * r).toFixed(2)},${(Math.sin(a) * r).toFixed(2)}`);
    }
  }
  return `M${pts.join("L")}Z`;
}

function Engranaje({ n, r, fase }: { n: number; r: number; fase: number }) {
  const rHub = r * 0.22;
  const rAro = r * 0.62;
  const radios = Array.from({ length: 5 }, (_, i) => {
    const a = ((i * 360) / 5) * (Math.PI / 180);
    return (
      <line
        key={i}
        x1={Math.cos(a) * rHub} y1={Math.sin(a) * rHub}
        x2={Math.cos(a) * rAro} y2={Math.sin(a) * rAro}
        stroke={theme.accent} strokeWidth={2} strokeOpacity={0.35}
      />
    );
  });
  return (
    <g>
      <path
        d={perfil(n, r, fase)}
        fill="rgba(0,212,255,0.05)" stroke={theme.accent}
        strokeWidth={2.5} strokeLinejoin="round"
      />
      <circle r={rAro} fill="none" stroke={theme.accent} strokeWidth={1.2} strokeOpacity={0.4} />
      {radios}
      <circle r={rHub} fill="rgba(0,212,255,0.1)" stroke={theme.accent} strokeWidth={2} />
    </g>
  );
}

type Chispa = {
  dx: number; dy: number; caida: number;
  dur: number; retardo: number; r: number; color: string;
};

const COLOR_CHISPA = ["#ffffff", "#ffffff", "#9beeff", "#7fe0ff", "#ffd08a", "#ffb347"];

/**
 * Chispas del punto de engrane. `fuerza` estira el alcance y `apertura` abre el
 * abanico: el chorro continuo sale en dos penachos (arriba y abajo del engrane),
 * mientras que el estallido del choque sale en todas direcciones y mucho más lejos.
 * Semilla fija: no queremos que bailen entre renders.
 */
function generarChispas(
  n: number,
  { semilla, fuerza, apertura, retardoMax }: {
    semilla: number; fuerza: number; apertura: number; retardoMax: number;
  },
): Chispa[] {
  let s = semilla;
  const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
  return Array.from({ length: n }, () => {
    const ang = ((rnd() < 0.5 ? -90 : 90) + (rnd() - 0.5) * apertura) * (Math.PI / 180);
    const v = fuerza * (0.45 + rnd() * 0.85);
    const dy = Math.sin(ang) * v;
    return {
      dx: Math.round(Math.cos(ang) * v),
      dy: Math.round(dy),
      // la gravedad siempre acaba tirando hacia abajo, suba o baje al salir
      caida: Math.round(dy + 90 + rnd() * 130),
      dur: 450 + rnd() * 450,
      retardo: rnd() * retardoMax,
      r: Number((1 + rnd() * 2.2).toFixed(1)),
      color: COLOR_CHISPA[Math.floor(rnd() * COLOR_CHISPA.length)],
    };
  });
}

function Chispas({ lista, innerRef }: { lista: Chispa[]; innerRef: React.Ref<SVGGElement> }) {
  return (
    <g ref={innerRef} transform={`translate(${CONTACTO_X}, ${CY})`}
       style={{ filter: "drop-shadow(0 0 5px rgba(155,238,255,0.9))" }}>
      {lista.map((c, i) => (
        <g key={i}>
          <g>
            <circle r={c.r} fill={c.color} />
          </g>
        </g>
      ))}
    </g>
  );
}

// Retícula: anillos discontinuos que giran a distinto ritmo y sentido.
function Reticula() {
  const ticks = Array.from({ length: 48 }, (_, i) => {
    const a = ((i * 360) / 48) * (Math.PI / 180);
    const largo = i % 4 === 0 ? 12 : 6;
    return (
      <line
        key={i}
        x1={Math.cos(a) * 196} y1={Math.sin(a) * 196}
        x2={Math.cos(a) * (196 + largo)} y2={Math.sin(a) * (196 + largo)}
        stroke={theme.accent} strokeWidth={i % 4 === 0 ? 1.6 : 1}
        strokeOpacity={i % 4 === 0 ? 0.5 : 0.25}
      />
    );
  });
  return (
    <g transform="translate(280, 240)" className="ar-reticula">
      <circle className="ar-anillo-1" r={150} fill="none" stroke={theme.accent}
              strokeWidth={1} strokeOpacity={0.18} strokeDasharray="18 12" />
      <circle className="ar-anillo-2" r={178} fill="none" stroke={theme.accent}
              strokeWidth={2} strokeOpacity={0.22} strokeDasharray="60 26 8 26" />
      <g className="ar-anillo-3">{ticks}</g>
      <circle className="ar-anillo-1" r={228} fill="none" stroke={theme.accent}
              strokeWidth={1} strokeOpacity={0.12} strokeDasharray="4 14" />
    </g>
  );
}

const LOG = [
  "Conectando con el núcleo de datos",
  "Leyendo métricas biométricas",
  "Cargando histórico de entreno",
  "Sincronizando bloques de fuerza",
];

export default function Arranque({
  cargado,
  onRevelar,
  onFin,
}: {
  cargado: boolean;
  onRevelar: () => void; // al empezar a separarse: el panel ya puede montarse debajo
  onFin: () => void;     // al terminar: este overlay sobra
}) {
  const [saliendo, setSaliendo] = useState(false);
  const t0 = useRef(Date.now());

  const bucle = useMemo(
    () => generarChispas(64, { semilla: 7, fuerza: 130, apertura: 120, retardoMax: 900 }),
    [],
  );
  const estallido = useMemo(
    () => generarChispas(70, { semilla: 91, fuerza: 300, apertura: 300, retardoMax: 90 }),
    [],
  );
  const refGiroA = useRef<SVGGElement>(null);
  const refGiroB = useRef<SVGGElement>(null);
  const refBucle = useRef<SVGGElement>(null);
  const refEstallido = useRef<SVGGElement>(null);

  // Giro y chispas con la Web Animations API para poder acelerarlos en marcha.
  // El cleanup cancela: bajo StrictMode el effect corre dos veces y si no
  // quedarían dos juegos de animaciones peleándose sobre los mismos nodos.
  useEffect(() => {
    const a = refGiroA.current, b = refGiroB.current;
    const gBucle = refBucle.current, gEst = refEstallido.current;
    if (!a || !b || !gBucle || !gEst) return;

    const acelerables: Animation[] = [];

    // A da 2 vueltas por cada 3 de B: razón inversa de sus dientes (18/12).
    const girar = (el: SVGGElement, grados: number, ms: number) =>
      el.animate(
        [{ transform: "rotate(0deg)" }, { transform: `rotate(${grados}deg)` }],
        { duration: ms, iterations: Infinity, easing: "linear", delay: ENTRADA_MS },
      );
    acelerables.push(girar(a, 360, 4500), girar(b, -360, 3000));

    const sueltos: Animation[] = [];
    const lanzar = (grupo: SVGGElement, lista: Chispa[], enBucle: boolean) => {
      const nodos = grupo.children;
      for (let i = 0; i < lista.length; i++) {
        const c = lista[i];
        const fuera = nodos[i] as SVGGElement;
        const dentro = fuera.firstElementChild as SVGGElement;
        const opts: KeyframeAnimationOptions = {
          duration: c.dur,
          delay: ENTRADA_MS + c.retardo,
          iterations: enBucle ? Infinity : 1,
        };
        // la X va lineal y se desvanece al final
        const ax = fuera.animate([
          { transform: "translateX(0px)", opacity: 0 },
          { transform: `translateX(${c.dx * 0.08}px)`, opacity: 1, offset: 0.08 },
          { transform: `translateX(${c.dx * 0.7}px)`, opacity: 0.85, offset: 0.7 },
          { transform: `translateX(${c.dx}px)`, opacity: 0 },
        ], { ...opts, easing: "linear" });
        // la Y hace parábola: sube frenando y cae acelerando
        const ay = dentro.animate([
          { transform: "translateY(0px)", easing: "cubic-bezier(0.2,0.7,0.5,1)" },
          { transform: `translateY(${c.dy}px)`, offset: 0.45, easing: "cubic-bezier(0.5,0,0.9,0.6)" },
          { transform: `translateY(${c.caida}px)` },
        ], opts);
        (enBucle ? acelerables : sueltos).push(ax, ay);
      }
    };
    lanzar(gBucle, bucle, true);
    lanzar(gEst, estallido, false);

    // Rampa de velocidad. Se refresca a 12 Hz en vez de cada frame: cambiar
    // playbackRate recalcula el arranque de cada animación y son muchas; a este
    // ritmo la aceleración ya se percibe continua.
    const desde = performance.now();
    const id = setInterval(() => {
      const t = (performance.now() - desde - ENTRADA_MS) / 1000;
      const v = t <= 0 ? 1 : 1 + t / SEG_PARA_DOBLAR;
      for (const an of acelerables) an.playbackRate = v;
    }, 80);

    return () => {
      clearInterval(id);
      for (const an of [...acelerables, ...sueltos]) an.cancel();
    };
  }, [bucle, estallido]);

  // Los datos ya están, pero no cortamos en seco: se completa el mínimo de
  // secuencia para que no dé un fogonazo si la carga fue instantánea.
  useEffect(() => {
    if (!cargado || saliendo) return;
    const faltan = Math.max(0, ENTRADA_MS + GIRO_MIN_MS - (Date.now() - t0.current));
    const t = setTimeout(() => {
      setSaliendo(true);
      // el panel se monta AHORA, no al acabar: si esperase, entre el overlay ya
      // transparente y el panel aún sin montar se colaría un fotograma en negro
      onRevelar();
    }, faltan);
    return () => clearTimeout(t);
  }, [cargado, saliendo, onRevelar]);

  useEffect(() => {
    if (!saliendo) return;
    const t = setTimeout(onFin, SALIDA_MS);
    return () => clearTimeout(t);
  }, [saliendo, onFin]);

  return (
    <div
      className={saliendo ? "ar ar-sale" : "ar"}
      style={{
        position: "fixed", inset: 0, zIndex: 60, overflow: "hidden",
        background:
          "radial-gradient(900px 620px at 50% 44%, rgba(0,212,255,0.1), transparent 72%), " + theme.bg,
      }}
    >
      {/* esquinas de HUD: fuera de la sacudida, son el marco fijo */}
      <span className="ar-esq ar-esq-si" /><span className="ar-esq ar-esq-sd" />
      <span className="ar-esq ar-esq-ii" /><span className="ar-esq ar-esq-id" />
      {/* fogonazo blanco del impacto, a pantalla completa */}
      <div className="ar-flash" />

      {/* todo lo demás va aquí dentro para que el choque sacuda el conjunto */}
      <div className="ar-mundo flex h-full w-full flex-col items-center justify-center">
        <div className="ar-halo" />
        <div className="ar-barrido" />

        {/* En pantallas anchas quien manda es el ALTO, no el ancho: debajo van el
            título y el log, así que se reserva su hueco y el resto se lo queda el
            dibujo. El viewBox es 560×480, de ahí el 1.1667 para pasar alto a ancho. */}
        <svg
          viewBox="0 0 560 480"
          width="min(94vw, 1150px, calc((100vh - 215px) * 1.1667))"
          style={{ filter: "drop-shadow(0 0 12px rgba(0,212,255,0.45))", overflow: "visible" }}
          aria-hidden
        >
          <Reticula />

          <defs>
            <radialGradient id="arGlow">
              <stop offset="0%" stopColor={theme.accent} stopOpacity={0.55} />
              <stop offset="100%" stopColor={theme.accent} stopOpacity={0} />
            </radialGradient>
          </defs>
          {/* fogonazo en el punto de contacto, latiendo al ritmo del engrane */}
          <circle className="ar-fogonazo" cx={CONTACTO_X} cy={CY} r={80} fill="url(#arGlow)" />

          {/* dos ondas de choque encadenadas, para que el golpe pese */}
          <circle className="ar-onda ar-onda-1" cx={CONTACTO_X} cy={CY} r={150}
                  fill="none" stroke="#ffffff" strokeWidth={3} />
          <circle className="ar-onda ar-onda-2" cx={CONTACTO_X} cy={CY} r={240}
                  fill="none" stroke={theme.accent} strokeWidth={2} />

          <g className="ar-pos-a"><g ref={refGiroA}>
            <Engranaje n={N_A} r={R_A} fase={180 / N_A} />
          </g></g>
          <g className="ar-pos-b"><g ref={refGiroB}>
            <Engranaje n={N_B} r={R_B} fase={0} />
          </g></g>

          {/* chispas encima de los engranajes: el chorro continuo y el estallido */}
          <Chispas lista={bucle} innerRef={refBucle} />
          <Chispas lista={estallido} innerRef={refEstallido} />
        </svg>

        {/* título + log suben juntos, dejando los engranajes en su sitio */}
        <div className="ar-texto flex flex-col items-center">
        <div className="flex flex-col items-center gap-2.5">
          <div
            className="font-display text-4xl tracking-[0.5em] ar-titulo"
            style={{ color: theme.accent, textShadow: "0 0 28px rgba(0,212,255,0.6)" }}
          >
            JARVIS
          </div>
          <div
            className="font-display text-xs uppercase tracking-[0.35em]"
            style={{ color: cargado ? theme.good : theme.muted }}
          >
            {cargado ? "Sistemas en línea" : "Iniciando sistemas"}
          </div>
        </div>

        {/* log de arranque: se va escribiendo mientras carga */}
        <div className="mt-6 flex w-[min(92vw,660px)] flex-col gap-2">
          {LOG.map((linea, i) => (
            <div
              key={linea}
              className="ar-log flex items-baseline gap-3 text-[11px] uppercase tracking-[0.18em]"
              style={{ animationDelay: `${0.85 + i * 0.5}s`, color: theme.muted }}
            >
              <span className="shrink-0">{linea}</span>
              {/* los puntos rellenan el hueco que sobre, sin empujar a los lados */}
              <span
                className="min-w-0 flex-1 overflow-hidden whitespace-nowrap"
                style={{ color: "rgba(0,212,255,0.25)" }}
              >
                ··············································
              </span>
              <span className="shrink-0" style={{ color: theme.good }}>OK</span>
            </div>
          ))}
        </div>
        </div>
      </div>
    </div>
  );
}
