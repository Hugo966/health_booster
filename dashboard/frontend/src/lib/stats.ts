// Utilidades numéricas para los widgets (correlaciones, medias móviles).

// Rangos con promedio en empates (para Spearman).
export function rank(xs: number[]): number[] {
  const idx = xs.map((v, i) => [v, i] as [number, number]).sort((a, b) => a[0] - b[0]);
  const r = new Array(xs.length).fill(0);
  let i = 0;
  while (i < idx.length) {
    let j = i;
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
    const avg = (i + j) / 2 + 1; // rango medio (1-based)
    for (let k = i; k <= j; k++) r[idx[k][1]] = avg;
    i = j + 1;
  }
  return r;
}

export function pearson(a: number[], b: number[]): number {
  const n = a.length;
  if (n < 2) return NaN;
  const ma = a.reduce((s, x) => s + x, 0) / n;
  const mb = b.reduce((s, x) => s + x, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) {
    const x = a[i] - ma, y = b[i] - mb;
    num += x * y; da += x * x; db += y * y;
  }
  const den = Math.sqrt(da * db);
  return den === 0 ? NaN : num / den;
}

// Correlación de Spearman = Pearson sobre los rangos.
export function spearman(a: number[], b: number[]): number {
  return pearson(rank(a), rank(b));
}

// Media móvil de ventana fija; null donde no hay valor de entrada.
export function movingAverage(vals: (number | null)[], win: number): (number | null)[] {
  return vals.map((_, i) => {
    const w = vals
      .slice(Math.max(0, i - win + 1), i + 1)
      .filter((v): v is number => v !== null);
    if (w.length === 0) return null;
    return w.reduce((s, x) => s + x, 0) / w.length;
  });
}

// Percentil por interpolación lineal (p en [0,1]). Base de las bandas de carga,
// que se calculan sobre el histórico propio en vez de umbrales de manual.
export function percentile(vals: number[], p: number): number {
  if (vals.length === 0) return NaN;
  const s = [...vals].sort((a, b) => a - b);
  if (s.length === 1) return s[0];
  const i = p * (s.length - 1);
  const lo = Math.floor(i), hi = Math.ceil(i);
  return lo === hi ? s[lo] : s[lo] + (s[hi] - s[lo]) * (i - lo);
}

export function mean(vals: number[]): number {
  return vals.length ? vals.reduce((s, x) => s + x, 0) / vals.length : NaN;
}

// Suma móvil de los últimos `days` días naturales terminando en cada fecha.
// A diferencia de una ventana de N filas, respeta los días sin entreno.
export function rollingSumByDate(
  rows: { fecha: string; v: number }[],
  days: number,
): { fecha: string; v: number }[] {
  const ms = days * 86400000;
  return rows.map((r) => {
    const end = Date.parse(r.fecha);
    const start = end - ms + 86400000; // ventana inclusiva de `days` días
    const v = rows
      .filter((o) => {
        const t = Date.parse(o.fecha);
        return t >= start && t <= end;
      })
      .reduce((s, o) => s + o.v, 0);
    return { fecha: r.fecha, v };
  });
}
