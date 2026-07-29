import { useEffect, useRef } from "react";

// La "presencia" de Jarvis: un orbe en canvas que cambia de FORMA según el estado y
// morfea suave entre una y otra (fundido + escala + destello). Es la interfaz de voz
// —sustituye al botón de micro—: un clic enciende/apaga la escucha. El look se validó
// en maqueta con Hugo (2026-07-29): esfera / radar / giroscopio / barras.
//
// Estados (la FORMA y el COLOR los marca el estado, consistentes):
//   off        -> voz apagada (esfera gris tenue; clic para activar)
//   dormido    -> escuchando "Jarvis", en reposo (esfera cian apagada)
//   escuchando -> capturando el comando (HUD radar)
//   pensando   -> esperando a Claude (giroscopio) — lo deriva el panel de chat.enviando
//   hablando   -> leyendo la respuesta (barras de ecualizador)
//
// La POTENCIA (modelo activo: 0 Estándar / 1 Turbo / 2 Máxima) NO cambia el color: se
// expresa como energía (más rápido, más glow, más partículas), un aro-medidor tenue en
// el color del nivel, y un glow de fondo que brilla más con la potencia. Decidido así
// con Hugo para no perder la consistencia de color por estado.
export type EstadoPresencia = "off" | "dormido" | "escuchando" | "pensando" | "hablando";

const COL: Record<EstadoPresencia, [number, number, number]> = {
  off: [70, 80, 100],
  dormido: [70, 140, 165],
  escuchando: [0, 212, 255],
  pensando: [123, 97, 255],
  hablando: [0, 229, 192],
};

// Colores de nivel (los del selector de modelo): verde / naranja / rojo. Solo para el
// aro-medidor; el cuerpo del orbe nunca los usa.
const TIER: [number, number, number][] = [[52, 224, 122], [255, 159, 67], [255, 92, 92]];

// Multiplicadores de energía por potencia (0/1/2).
type Pw = { vel: number; glow: number; amp: number; part: number };
const pwDe = (pot: number): Pw => ({
  vel: 0.8 + pot * 0.5,
  glow: 0.8 + pot * 0.6,
  amp: 0.7 + pot * 0.7,
  part: 1 + pot * 0.9,
});

const rgba = (c: number[], a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const easeInOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);

function nucleo(ctx: CanvasRenderingContext2D, t: number, col: number[], rBase: number, glow: number, pw: Pw) {
  const r = rBase * (1 + 0.08 * Math.sin(t * 3));
  const g = ctx.createRadialGradient(-r * 0.3, -r * 0.3, 2, 0, 0, r);
  g.addColorStop(0, "rgba(230,253,255,0.95)");
  g.addColorStop(0.4, rgba(col, 0.95));
  g.addColorStop(1, rgba(col, 0.12));
  ctx.fillStyle = g;
  ctx.shadowColor = rgba(col, 0.9);
  ctx.shadowBlur = 22 * glow * pw.glow;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, 7);
  ctx.fill();
  ctx.shadowBlur = 0;
}

function esfera(ctx: CanvasRenderingContext2D, t: number, col: number[], vivo: number, pw: Pw) {
  const br = 1 + 0.05 * Math.sin(t * 1.6);
  let g = ctx.createRadialGradient(0, 0, 6, 0, 0, 120);
  g.addColorStop(0, rgba(col, 0.2 * vivo));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 120, 0, 7);
  ctx.fill();
  ctx.strokeStyle = rgba(col, 0.22 * vivo);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(0, 0, 76 * br, 0, 7);
  ctx.stroke();
  const r = 54 * br;
  g = ctx.createRadialGradient(-r * 0.3, -r * 0.35, 3, 0, 0, r);
  g.addColorStop(0, `rgba(220,245,255,${0.9 * vivo})`);
  g.addColorStop(0.45, rgba(col, 0.82 * vivo));
  g.addColorStop(1, rgba(col, 0.12 * vivo));
  ctx.fillStyle = g;
  ctx.shadowColor = rgba(col, 0.6 * vivo);
  ctx.shadowBlur = 26 * vivo * pw.glow;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, 7);
  ctx.fill();
  ctx.shadowBlur = 0;
}

function radar(ctx: CanvasRenderingContext2D, t: number, col: number[], env: number, pw: Pw) {
  ctx.lineCap = "round";
  let g = ctx.createRadialGradient(0, 0, 8, 0, 0, 150);
  g.addColorStop(0, rgba(col, 0.16));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 150, 0, 7);
  ctx.fill();
  ctx.save();
  ctx.rotate(t * 0.25);
  ctx.strokeStyle = rgba(col, 0.5);
  ctx.lineWidth = 1;
  for (let i = 0; i < 72; i++) {
    const a = (i / 72) * 6.283, r1 = i % 6 === 0 ? 116 : 122;
    ctx.beginPath();
    ctx.moveTo(Math.cos(a) * 128, Math.sin(a) * 128);
    ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1);
    ctx.stroke();
  }
  ctx.restore();
  ctx.save();
  ctx.rotate(-t * 0.7);
  ctx.strokeStyle = rgba(col, 0.9);
  ctx.lineWidth = 2.5;
  ctx.shadowColor = rgba(col, 0.9);
  ctx.shadowBlur = 10 * pw.glow;
  for (let k = 0; k < 3; k++) {
    const s = (k / 3) * 6.283;
    ctx.beginPath();
    ctx.arc(0, 0, 104, s, s + 0.9);
    ctx.stroke();
  }
  ctx.restore();
  ctx.shadowBlur = 0;
  ctx.save();
  ctx.rotate(-t * 1.4);
  const pasos = 26;
  for (let i = 0; i < pasos; i++) {
    const a0 = (i / pasos) * 1.1, a1 = ((i + 1) / pasos) * 1.1;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, 112, a0, a1);
    ctx.closePath();
    ctx.fillStyle = rgba(col, 0.14 * (i / pasos));
    ctx.fill();
  }
  ctx.restore();
  const N = 72, base = 58;
  ctx.strokeStyle = rgba(col, 0.9);
  ctx.lineWidth = 2;
  ctx.shadowColor = rgba(col, 0.8);
  ctx.shadowBlur = 5 * pw.glow;
  for (let i = 0; i < N; i++) {
    const a = (i / N) * 6.283 + t * 0.15, pb = 0.5 + 0.5 * Math.sin(i * 2.3 + t * 4), len = 8 + 8 * env * pb;
    ctx.beginPath();
    ctx.moveTo(Math.cos(a) * base, Math.sin(a) * base);
    ctx.lineTo(Math.cos(a) * (base + len), Math.sin(a) * (base + len));
    ctx.stroke();
  }
  ctx.shadowBlur = 0;
  for (let k = 0; k < 3; k++) {
    const f = (t * 0.5 + k / 3) % 1, r = 46 + f * 80, a = 0.5 * (1 - f);
    ctx.strokeStyle = rgba(col, a);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, 7);
    ctx.stroke();
  }
  const np = Math.round(20 * pw.part);
  for (let i = 0; i < np; i++) {
    const a = (i / np) * 6.283 + t * (0.2 + (i % 4) * 0.05), r = 92 + (i % 5) * 8;
    ctx.fillStyle = rgba(col, 0.5 + 0.4 * Math.sin(t * 3 + i));
    ctx.beginPath();
    ctx.arc(Math.cos(a) * r, Math.sin(a) * r, 1.4, 0, 7);
    ctx.fill();
  }
  nucleo(ctx, t, col, 30, 0.9, pw);
}

function giroscopio(ctx: CanvasRenderingContext2D, t: number, col: number[], pw: Pw) {
  const g = ctx.createRadialGradient(0, 0, 6, 0, 0, 120);
  g.addColorStop(0, rgba(col, 0.16));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 120, 0, 7);
  ctx.fill();
  ctx.strokeStyle = rgba(col, 0.85);
  ctx.lineWidth = 2;
  ctx.shadowColor = rgba(col, 0.8);
  ctx.shadowBlur = 8 * pw.glow;
  const R = 96;
  for (let k = 0; k < 3; k++) {
    ctx.save();
    ctx.rotate(t * (0.7 + 0.35 * k) + k * 1.05);
    ctx.beginPath();
    ctx.ellipse(0, 0, R, R * 0.34, 0, 0, 7);
    ctx.stroke();
    const a = t * 1.6 + k * 2.1, x = Math.cos(a) * R, y = Math.sin(a) * R * 0.34;
    ctx.fillStyle = rgba(col, 0.95);
    ctx.beginPath();
    ctx.arc(x, y, 3.2, 0, 7);
    ctx.fill();
    ctx.restore();
  }
  ctx.shadowBlur = 0;
  nucleo(ctx, t, col, 20, 0.7, pw);
}

function barras(ctx: CanvasRenderingContext2D, t: number, col: number[], pot: number, pw: Pw) {
  const g = ctx.createRadialGradient(0, 0, 6, 0, 0, 120);
  g.addColorStop(0, rgba(col, 0.18));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 120, 0, 7);
  ctx.fill();
  // Amplitud propia y COMPRIMIDA por potencia (no la energía general): con la energía
  // normal el salto entre niveles al hablar era enorme y el alto chillaba. Progresión
  // suave 0.7 -> 0.92 -> 1.14.
  const ampHab = 0.7 + pot * 0.22;
  const osc = 0.55 + 0.45 * (0.6 * Math.sin(t * 8) + 0.4 * Math.sin(t * 13.3 + 1)), envH = osc * ampHab;
  const n = 9, w = 7, gap = 11, total = n * w + (n - 1) * gap;
  let x = -total / 2;
  ctx.fillStyle = rgba(col, 0.95);
  ctx.shadowColor = rgba(col, 0.85);
  ctx.shadowBlur = 14 * pw.glow;
  for (let i = 0; i < n; i++) {
    const centro = 1 - Math.abs(i - (n - 1) / 2) / ((n - 1) / 2);
    const pb = 0.5 + 0.5 * Math.sin(i * 1.7 + t * 7);
    const h = 16 + envH * (26 + 66 * pb) * (0.5 + 0.5 * centro);
    ctx.beginPath();
    ctx.roundRect(x, -h / 2, w, h, w / 2);
    ctx.fill();
    x += w + gap;
  }
  ctx.shadowBlur = 0;
}

// Aro-medidor exterior: 3 segmentos, encendidos = potencia+1, en el color del nivel.
// Tenue a propósito (no debe destacar más que el orbe); la sensación de potencia la da
// sobre todo el glow de fondo y la energía.
function medidor(ctx: CanvasRenderingContext2D, pot: number) {
  const tc = TIER[Math.max(0, Math.min(2, pot))], R = 134, gap = 0.18, span = (6.283 - 3 * gap) / 3;
  for (let i = 0; i < 3; i++) {
    const on = i <= pot, a0 = -1.5708 + i * (span + gap);
    ctx.beginPath();
    ctx.arc(0, 0, R, a0, a0 + span);
    ctx.strokeStyle = on ? rgba(tc, 0.5) : "rgba(255,255,255,0.07)";
    ctx.lineWidth = on ? 3 : 2.5;
    ctx.lineCap = "round";
    if (on) {
      ctx.shadowColor = rgba(tc, 0.45);
      ctx.shadowBlur = 5;
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
}

// Dibuja la forma de un estado + el aro-medidor. El canvas ya está trasladado al centro.
function forma(ctx: CanvasRenderingContext2D, nombre: EstadoPresencia, t: number, env: number, pot: number, pw: Pw) {
  const col = COL[nombre];
  if (nombre === "off") esfera(ctx, t, col, 0.4, pw);
  else if (nombre === "dormido") esfera(ctx, t, col, 1, pw);
  else if (nombre === "escuchando") radar(ctx, t, col, env, pw);
  else if (nombre === "pensando") giroscopio(ctx, t, col, pw);
  else barras(ctx, t, col, pot, pw);
  medidor(ctx, pot);
}

export default function Presencia({
  estado,
  potencia = 0,
  onToggle,
  size = 168,
}: {
  estado: EstadoPresencia;
  potencia?: number; // 0 Estándar / 1 Turbo / 2 Máxima
  onToggle?: () => void;
  size?: number;
}) {
  const cvRef = useRef<HTMLCanvasElement>(null);
  // Estado de la transición vive en refs para que el bucle no se reinicie por render.
  const estRef = useRef<EstadoPresencia>(estado);
  const prevRef = useRef<EstadoPresencia | null>(null);
  const mezclaRef = useRef(1);
  const flashRef = useRef(-9);
  const potRef = useRef(potencia);
  potRef.current = potencia;

  // Al cambiar el estado: arranca una transición (la forma anterior sale, la nueva entra).
  useEffect(() => {
    if (estado === estRef.current) return;
    prevRef.current = estRef.current;
    estRef.current = estado;
    mezclaRef.current = 0;
    flashRef.current = performance.now();
  }, [estado]);

  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    // Lienzo lógico 400 (no 340): más margen alrededor de las formas (radio ~150) para
    // que el glow de fondo se apague DENTRO del lienzo y salga circular, no recortado en
    // cuadrado. Se escala al `size` pedido, así el mismo código sirve a cualquier tamaño.
    const BASE = 400, C = BASE / 2;
    cv.width = size * dpr;
    cv.height = size * dpr;
    const escala = (size * dpr) / BASE;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const DUR = 0.75;
    let raf = 0, last = 0, tVis = 0;

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000 || 0, 0.05);
      last = now;
      const pot = potRef.current;
      const pw = pwDe(pot);
      tVis += dt * pw.vel; // la potencia acelera el tiempo visible
      const t = tVis;
      if (mezclaRef.current < 1) mezclaRef.current = Math.min(1, mezclaRef.current + dt / DUR);
      const m = easeInOut(mezclaRef.current);
      // envolvente base (oscilación) por la energía general; el radar la usa para su anillo.
      const env = (0.55 + 0.45 * (0.6 * Math.sin(t * 8) + 0.4 * Math.sin(t * 13.3 + 1))) * pw.amp;

      ctx.setTransform(escala, 0, 0, escala, 0, 0);
      ctx.clearRect(0, 0, BASE, BASE);

      // Glow de fondo ambiental: brilla más con la potencia. Da sensación de "power" sin
      // cambiar el color (usa el del estado) ni competir con la forma. fr < C(200): se
      // apaga antes del borde -> círculo limpio con margen.
      {
        ctx.save();
        ctx.translate(C, C);
        const fc = COL[estRef.current], fr = 172 + pot * 16, fa = 0.09 + pot * 0.06;
        const fg = ctx.createRadialGradient(0, 0, 10, 0, 0, fr);
        fg.addColorStop(0, rgba(fc, fa));
        fg.addColorStop(0.5, rgba(fc, fa * 0.55));
        fg.addColorStop(1, rgba(fc, 0));
        ctx.fillStyle = fg;
        ctx.beginPath();
        ctx.arc(0, 0, fr, 0, 7);
        ctx.fill();
        ctx.restore();
      }

      if (prevRef.current && m < 1) {
        ctx.save();
        ctx.translate(C, C);
        ctx.scale(1 + 0.28 * m, 1 + 0.28 * m);
        ctx.globalAlpha = 1 - m;
        forma(ctx, prevRef.current, t, env, pot, pw);
        ctx.restore();
      }
      ctx.save();
      ctx.translate(C, C);
      const s = 0.82 + 0.18 * m;
      ctx.scale(s, s);
      ctx.globalAlpha = m < 1 ? m : 1;
      forma(ctx, estRef.current, t, env, pot, pw);
      ctx.restore();

      const fe = (now - flashRef.current) / 520;
      if (fe >= 0 && fe < 1) {
        ctx.save();
        ctx.translate(C, C);
        ctx.globalAlpha = 1 - fe;
        ctx.strokeStyle = rgba(COL[estRef.current], 0.6);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(0, 0, 30 + fe * 120, 0, 7);
        ctx.stroke();
        ctx.restore();
      }

      if (!reduce) raf = requestAnimationFrame(frame);
    };

    if (reduce) {
      last = performance.now();
      frame(last + 16);
    } else {
      raf = requestAnimationFrame(frame);
    }
    return () => cancelAnimationFrame(raf);
  }, [size]);

  return (
    <canvas
      ref={cvRef}
      onClick={onToggle}
      role="button"
      aria-label={estado === "off" ? "Activar la voz de Jarvis" : "Voz de Jarvis activa (toca para apagar)"}
      title={estado === "off" ? "Toca para activar la voz — luego llámalo diciendo «Jarvis»" : "Voz activa · di «Jarvis»"}
      style={{ width: size, height: size, cursor: onToggle ? "pointer" : "default", display: "block" }}
    />
  );
}
