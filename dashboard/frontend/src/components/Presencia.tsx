import { useEffect, useRef } from "react";

// La "presencia" de Jarvis: un orbe en canvas que cambia de FORMA según el estado y
// morfea suave entre una y otra (fundido + escala + destello). Es la interfaz de voz
// —sustituye al botón de micro—: un clic enciende/apaga la escucha. El look se validó
// en maqueta con Hugo (2026-07-29): esfera / radar / giroscopio / barras.
//
// Estados:
//   off        -> voz apagada (esfera gris tenue; clic para activar)
//   dormido    -> escuchando "Jarvis", en reposo (esfera cian apagada)
//   escuchando -> capturando el comando (HUD radar)
//   pensando   -> esperando a Claude (giroscopio) — lo deriva el panel de chat.enviando
//   hablando   -> leyendo la respuesta (barras de ecualizador)
export type EstadoPresencia = "off" | "dormido" | "escuchando" | "pensando" | "hablando";

const COL: Record<EstadoPresencia, [number, number, number]> = {
  off: [70, 80, 100],
  dormido: [70, 140, 165],
  escuchando: [0, 212, 255],
  pensando: [123, 97, 255],
  hablando: [0, 229, 192],
};

const rgba = (c: number[], a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const easeInOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);

function nucleo(ctx: CanvasRenderingContext2D, t: number, col: number[], rBase: number, glow: number) {
  const r = rBase * (1 + 0.08 * Math.sin(t * 3));
  const g = ctx.createRadialGradient(-r * 0.3, -r * 0.3, 2, 0, 0, r);
  g.addColorStop(0, "rgba(230,253,255,0.95)");
  g.addColorStop(0.4, rgba(col, 0.95));
  g.addColorStop(1, rgba(col, 0.12));
  ctx.fillStyle = g;
  ctx.shadowColor = rgba(col, 0.9);
  ctx.shadowBlur = 22 * glow;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, 7);
  ctx.fill();
  ctx.shadowBlur = 0;
}

function esfera(ctx: CanvasRenderingContext2D, t: number, col: number[], vivo: number) {
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
  ctx.shadowBlur = 26 * vivo;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, 7);
  ctx.fill();
  ctx.shadowBlur = 0;
}

function radar(ctx: CanvasRenderingContext2D, t: number, col: number[], env: number) {
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
  ctx.shadowBlur = 10;
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
  ctx.shadowBlur = 5;
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
  for (let i = 0; i < 20; i++) {
    const a = (i / 20) * 6.283 + t * (0.2 + (i % 4) * 0.05), r = 92 + (i % 5) * 8;
    ctx.fillStyle = rgba(col, 0.5 + 0.4 * Math.sin(t * 3 + i));
    ctx.beginPath();
    ctx.arc(Math.cos(a) * r, Math.sin(a) * r, 1.4, 0, 7);
    ctx.fill();
  }
  nucleo(ctx, t, col, 30, 0.9);
}

function giroscopio(ctx: CanvasRenderingContext2D, t: number, col: number[]) {
  let g = ctx.createRadialGradient(0, 0, 6, 0, 0, 120);
  g.addColorStop(0, rgba(col, 0.16));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 120, 0, 7);
  ctx.fill();
  ctx.strokeStyle = rgba(col, 0.85);
  ctx.lineWidth = 2;
  ctx.shadowColor = rgba(col, 0.8);
  ctx.shadowBlur = 8;
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
  nucleo(ctx, t, col, 20, 0.7);
}

function barras(ctx: CanvasRenderingContext2D, t: number, col: number[], env: number) {
  const g = ctx.createRadialGradient(0, 0, 6, 0, 0, 120);
  g.addColorStop(0, rgba(col, 0.18));
  g.addColorStop(1, rgba(col, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, 120, 0, 7);
  ctx.fill();
  const n = 9, w = 7, gap = 11, total = n * w + (n - 1) * gap;
  let x = -total / 2;
  ctx.fillStyle = rgba(col, 0.95);
  ctx.shadowColor = rgba(col, 0.85);
  ctx.shadowBlur = 14;
  for (let i = 0; i < n; i++) {
    const centro = 1 - Math.abs(i - (n - 1) / 2) / ((n - 1) / 2);
    const pb = 0.5 + 0.5 * Math.sin(i * 1.7 + t * 7);
    const h = 16 + env * (26 + 66 * pb) * (0.5 + 0.5 * centro);
    ctx.beginPath();
    ctx.roundRect(x, -h / 2, w, h, w / 2);
    ctx.fill();
    x += w + gap;
  }
  ctx.shadowBlur = 0;
}

// Dibuja la forma de un estado, centrada. El canvas ya está trasladado al centro.
function forma(ctx: CanvasRenderingContext2D, nombre: EstadoPresencia, t: number, env: number) {
  const col = COL[nombre];
  if (nombre === "off") esfera(ctx, t, col, 0.4);
  else if (nombre === "dormido") esfera(ctx, t, col, 1);
  else if (nombre === "escuchando") radar(ctx, t, col, env);
  else if (nombre === "pensando") giroscopio(ctx, t, col);
  else barras(ctx, t, col, env);
}

export default function Presencia({
  estado,
  onToggle,
  size = 168,
}: {
  estado: EstadoPresencia;
  onToggle?: () => void;
  size?: number;
}) {
  const cvRef = useRef<HTMLCanvasElement>(null);
  // Estado de la transición vive en refs para que el bucle no se reinicie por render.
  const estRef = useRef<EstadoPresencia>(estado);
  const prevRef = useRef<EstadoPresencia | null>(null);
  const mezclaRef = useRef(1);
  const flashRef = useRef(-9);

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
    // El canvas dibuja en un lienzo lógico de 340 (donde se calibraron las formas) y
    // se escala al tamaño pedido, así el mismo código sirve a cualquier `size`.
    const BASE = 340, C = BASE / 2;
    cv.width = size * dpr;
    cv.height = size * dpr;
    const escala = (size * dpr) / BASE;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const DUR = 0.75;
    let raf = 0, last = 0, tAcc = 0;

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000 || 0, 0.05);
      last = now;
      tAcc += dt;
      if (mezclaRef.current < 1) mezclaRef.current = Math.min(1, mezclaRef.current + dt / DUR);
      const m = easeInOut(mezclaRef.current);
      const env = 0.55 + 0.45 * (0.6 * Math.sin(tAcc * 8) + 0.4 * Math.sin(tAcc * 13.3 + 1));

      ctx.setTransform(escala, 0, 0, escala, 0, 0);
      ctx.clearRect(0, 0, BASE, BASE);

      if (prevRef.current && m < 1) {
        ctx.save();
        ctx.translate(C, C);
        ctx.scale(1 + 0.28 * m, 1 + 0.28 * m);
        ctx.globalAlpha = 1 - m;
        forma(ctx, prevRef.current, tAcc, env);
        ctx.restore();
      }
      ctx.save();
      ctx.translate(C, C);
      const s = 0.82 + 0.18 * m;
      ctx.scale(s, s);
      ctx.globalAlpha = m < 1 ? m : 1;
      forma(ctx, estRef.current, tAcc, env);
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
