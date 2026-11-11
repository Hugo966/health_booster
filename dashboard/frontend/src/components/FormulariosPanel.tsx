import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Panel from "./Panel";
import { theme } from "../lib/theme";
import {
  enrutarPestana, fetchEsquema, fetchEstado, fetchPlanPendientes, fetchValores, guardar, hoyISO,
  type Campo, type EstadoFormularios, type Esquema, type Fuente, type PlanPendientes,
  type TipoFormulario, type Valores,
} from "../lib/formularios";

// Semáforo + editor de los formularios diarios. Hasta ahora estos datos solo entraban
// por Google Forms: si a Hugo se le olvidaba un día, nadie se lo decía y el dato se
// perdía (y sin `rpd_sesion` la sesión entera se cae de la carga).
//
// Los campos y sus rangos los manda el backend, no se declaran aquí: la escala de
// sueño/ánimo/energía es 1-9, no 1-10, y ofrecer un 10 rompería el readiness.

const COLOR: Record<Fuente["estado"], string> = {
  ok: theme.good,
  pendiente: theme.amber,
  aviso: theme.amber,
  falta: theme.alert,
  no_disponible: theme.muted,
};

function Luz({ fuente }: { fuente: Fuente }) {
  const c = COLOR[fuente.estado];
  return (
    <div className="flex items-center gap-2">
      <span
        className="inline-block h-2 w-2 shrink-0 rounded-full"
        style={{ background: c, boxShadow: `0 0 8px ${c}` }}
      />
      <div className="min-w-0">
        <div className="truncate text-[11px]" style={{ color: theme.text }}>{fuente.etiqueta}</div>
        <div className="truncate text-[10px]" style={{ color: theme.muted }}>{fuente.detalle}</div>
      </div>
    </div>
  );
}

/** Los últimos días, uno por columna: AM arriba, PM abajo, y una marca si entrenó.
 *  Es la respuesta visual a "¿qué día se me pasó?", que las luces por fuente no dan. */
function Tira({ estado }: { estado: EstadoFormularios }) {
  const hoy = estado.hoy;
  // Con muchos días las etiquetas se pisan y quedan en un churro ilegible: a partir de
  // tres semanas solo se numeran algunas columnas (y hoy siempre).
  const n = estado.dias.length;
  const paso = n <= 21 ? 1 : Math.ceil(n / 12);
  const fino = n > 45;
  return (
    <div className={`flex items-end ${fino ? "gap-[1px]" : "gap-[3px]"}`}>
      {estado.dias.map((d, i) => {
        const esHoy = d.fecha === hoy;
        const etiqueta = esHoy || i % paso === 0 ? d.fecha.slice(8, 10) : "";
        const punto = (puesto: boolean) => (
          <span
            className="block h-[7px] w-full rounded-[2px]"
            // Pasada la ventana el registro sigue siendo rojo, pero MUY apagado: cuenta
            // que quedó sin completar sin reclamar nada, porque ya no se puede rellenar
            // de memoria. En gris se leería como "sin datos", que no es lo mismo.
            style={{ background: puesto ? COL.hecho
              : d.cerrado ? COL.cerrado
              : esHoy ? COL.hoy : COL.pendiente }}
          />
        );
        return (
          <div key={d.fecha} className="flex min-w-0 flex-1 flex-col items-center gap-[3px]"
               title={`${d.fecha} · AM ${d.am ? "✓" : "falta"} · PM ${d.pm ? "✓" : "falta"}${
                 d.sin_keep ? " · entreno SIN volcar al keep" : d.entreno ? " · entreno" : ""
               }${d.cerrado ? " · sin completar" : ""}`}>
            <span className="text-[8px]"
                  style={{ color: d.sin_keep ? theme.alert : d.entreno ? theme.accent : "transparent" }}>•</span>
            <div className="w-full">{punto(d.am)}</div>
            <div className="w-full">{punto(d.pm)}</div>
            <span className="text-[9px] leading-none"
                  style={{ color: esHoy ? theme.text : theme.muted }}>{etiqueta}</span>
          </div>
        );
      })}
    </div>
  );
}

function Muestra({ color, children }: { color: string; children: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="inline-block h-[7px] w-[10px] rounded-[2px]" style={{ background: color }} />
      {children}
    </span>
  );
}

function Leyenda() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px]"
         style={{ color: theme.muted }}>
      <span>Fila de arriba: AM · fila de abajo: PM</span>
      <Muestra color={COL.hecho}>registrado</Muestra>
      <Muestra color={COL.pendiente}>pendiente</Muestra>
      <Muestra color={COL.cerrado}>sin completar</Muestra>
      <span style={{ color: theme.accent }}>• día con entreno</span>
      <span style={{ color: theme.alert }}>• sin volcar al keep</span>
    </div>
  );
}

// Los cuatro estados de una casilla. Se declaran juntos porque la leyenda tiene que
// pintar exactamente los mismos colores que la tira.
const COL = {
  hecho: "rgba(46,213,115,0.85)",
  pendiente: "rgba(255,71,87,0.85)",
  cerrado: "rgba(255,71,87,0.22)",
  hoy: "rgba(255,165,2,0.7)",
};

function Semaforo({ estado }: { estado: EstadoFormularios | null }) {
  if (!estado) return <div className="text-[11px]" style={{ color: theme.muted }}>Cargando…</div>;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Object.entries(estado.fuentes).map(([k, f]) => <Luz key={k} fuente={f} />)}
    </div>
  );
}

/** Escala 1-9 / 0-9 como fila de botones: replicar la escala en la UI evita que Hugo
 *  tenga que acordarse de que el 5 es "normal" y de que el tope es 9, no 10. */
function Escala({ campo, valor, onChange }: {
  campo: Campo; valor: string | number | undefined; onChange: (v: string) => void;
}) {
  const min = campo.minimo ?? 0, max = campo.maximo ?? 9;
  const nums = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return (
    <div className="flex flex-wrap gap-1" data-no-expand>
      {nums.map((n) => {
        const activo = String(valor ?? "") === String(n);
        const normal = n === 5 && min === 1 && max === 9;
        return (
          <button
            key={n}
            type="button"
            onClick={() => onChange(activo ? "" : String(n))}
            className="h-6 w-6 rounded text-[11px] transition-colors"
            title={normal ? "lo normal" : undefined}
            style={{
              background: activo ? theme.accent : "rgba(255,255,255,0.04)",
              color: activo ? "#04121c" : theme.text,
              border: `1px solid ${activo ? theme.accent : normal ? "rgba(0,212,255,0.35)" : "rgba(0,212,255,0.16)"}`,
              fontWeight: activo ? 700 : 400,
            }}
          >
            {n}
          </button>
        );
      })}
    </div>
  );
}

function Zonas({ zonas, valor, onChange }: {
  zonas: string[]; valor: string | number | undefined; onChange: (v: string) => void;
}) {
  const puestas = String(valor ?? "").split(",").map((z) => z.trim()).filter(Boolean);
  const alternar = (z: string) => {
    const next = puestas.includes(z) ? puestas.filter((x) => x !== z) : [...puestas, z];
    onChange(next.join(", "));
  };
  return (
    // Sin data-no-expand, tocar un chip abriría el overlay: esFondo() solo exceptúa
    // los controles HTML nativos, y esto son divs.
    <div className="flex flex-wrap gap-1" data-no-expand>
      {zonas.map((z) => {
        const activo = puestas.includes(z);
        return (
          <button
            key={z} type="button" onClick={() => alternar(z)}
            className="rounded-full px-2 py-[2px] text-[10px] transition-colors"
            style={{
              background: activo ? "rgba(0,212,255,0.18)" : "rgba(255,255,255,0.04)",
              color: activo ? theme.accent : theme.muted,
              border: `1px solid ${activo ? theme.accent : "rgba(0,212,255,0.16)"}`,
            }}
          >
            {z}
          </button>
        );
      })}
    </div>
  );
}

// Rueda tipo Zepp: una columna que se desliza y se engancha al valor. Dos motivos para
// que exista, y el segundo pesa más que el primero: no se puede teclear un peso con dos
// decimales ni una cafeína a ojo (el formato es el que es), y de un gesto se mete el
// valor sin sacar el teclado del móvil.
//
// Va DESPLEGADA solo mientras se usa: abierta siempre, ocupa cinco filas de alto por
// campo y el formulario se vuelve una tira. El botón enseña lo que vale y nada más.
const ALTO = 32;       // alto de cada opción, en px
const VISIBLES = 5;    // cuántas se ven; la de en medio es la elegida
const VENTANA = 50;    // cuántos pasos se pintan a cada lado del de partida

function Rueda({ campo, valor, sugerencia, onChange }: {
  campo: Campo; valor: string | number | undefined;
  sugerencia: string | number | undefined; onChange: (v: string) => void;
}) {
  const [abierta, setAbierta] = useState(false);
  const paso = campo.paso ?? 1;
  const dec = (String(paso).split(".")[1] ?? "").length;
  const min = campo.minimo ?? 0;
  const max = campo.maximo ?? min + 100;
  const puesto = String(valor ?? "").trim() !== "";

  // De dónde arranca: lo que ya tuviera ese día y, si no hay nada, lo último que
  // registró (su peso de la semana pasada). Es la diferencia entre girar dos muescas y
  // girar cincuenta.
  const partida = Number(puesto ? valor : sugerencia);
  const total = Math.round((max - min) / paso) + 1;
  const centro = Number.isFinite(partida)
    ? Math.min(total - 1, Math.max(0, Math.round((partida - min) / paso)))
    : Math.round((total - 1) / 2);

  // Solo una ventana alrededor: el peso va de 30 a 300 kg, que a 0,1 son 2701 opciones.
  // Pintarlas todas es un scroll eterno en el móvil y DOM de sobra para nada; ±5 kg
  // cubre cualquier pesada real, y la ventana se recoloca al abrirla otro día.
  const { opciones, desde } = useMemo(() => {
    const i0 = Math.max(0, centro - VENTANA);
    const i1 = Math.min(total - 1, centro + VENTANA);
    return {
      desde: i0,
      opciones: Array.from({ length: i1 - i0 + 1 },
                           (_, k) => +(min + (i0 + k) * paso).toFixed(dec)),
    };
    // `centro` solo manda al abrir: si entrara en cada giro, la ventana se movería bajo
    // el dedo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campo.nombre, total, min, paso, dec, abierta]);

  const caja = useRef<HTMLDivElement>(null);
  const globo = useRef<HTMLDivElement>(null);
  const tocada = useRef(false);

  useEffect(() => {
    // Al abrirla, colocarse en el valor de partida. El scroll programado NO cuenta como
    // tocar la rueda: si contara, abrirla y darle a Guardar apuntaría la sugerencia como
    // si fuera la pesada de hoy.
    tocada.current = false;
    if (!abierta || !caja.current) return;
    caja.current.scrollTop = (centro - desde) * ALTO;
    // Si el campo cae al final del panel, la rueda se abriría medio tapada por el borde
    // del formulario, que tiene su propio scroll. `nearest` lo corrige y no mueve nada
    // cuando ya se ve entera.
    globo.current?.scrollIntoView({ block: "nearest" });
  }, [abierta, centro, desde]);

  const elegir = (v: number) => onChange(v.toFixed(dec));

  const alScroll = () => {
    if (!tocada.current || !caja.current) return;
    const i = Math.round(caja.current.scrollTop / ALTO);
    const v = opciones[Math.min(opciones.length - 1, Math.max(0, i))];
    if (v !== undefined) elegir(v);
  };

  const marcar = () => { tocada.current = true; };
  const relleno = ((VISIBLES - 1) / 2) * ALTO;

  return (
    <div className="relative" data-no-expand>
      <button
        type="button" onClick={() => setAbierta((a) => !a)}
        className="jarvis-input flex w-full items-center justify-between text-left"
      >
        <span style={{ color: puesto ? theme.text : theme.muted }}>
          {puesto ? Number(valor).toFixed(dec)
            : sugerencia !== undefined && sugerencia !== "" ? `— (última vez: ${sugerencia})`
            : "—"}
        </span>
        <span style={{ color: theme.muted }}>{abierta ? "▲" : "▼"}</span>
      </button>
      {abierta && (
        // Encima de lo que haya debajo, no empujándolo: si el formulario se recolocara al
        // abrirla, el campo saltaría bajo el dedo justo antes de girarlo.
        // `preventDefault` porque el campo entero va dentro de un <label>: al tocar una
        // opción, el label reenvía el clic a su control —el botón de la rueda—, que lo
        // vuelve a abrir. Se cerraba y se abría en el mismo toque, y parecía que el
        // toque no hacía nada.
        <div ref={globo} onClick={(e) => e.preventDefault()}
             className="absolute left-0 z-20 mt-1 overflow-hidden rounded"
             style={{ top: "100%", height: VISIBLES * ALTO, width: 120,
                      background: "#0b1a24",
                      border: `1px solid ${theme.accent}`,
                      boxShadow: "0 8px 24px rgba(0,0,0,0.5)" }}>
          {/* la banda de la elegida, como en la báscula */}
          <div className="pointer-events-none absolute inset-x-0 z-10"
               style={{ top: relleno, height: ALTO, background: "rgba(0,212,255,0.10)",
                        borderTop: "1px solid rgba(0,212,255,0.35)",
                        borderBottom: "1px solid rgba(0,212,255,0.35)" }} />
          <div
            ref={caja} onScroll={alScroll}
            onPointerDown={marcar} onWheel={marcar} onKeyDown={marcar} tabIndex={0}
            className="h-full overflow-y-auto"
            style={{ scrollSnapType: "y mandatory", paddingTop: relleno,
                     paddingBottom: relleno, scrollbarWidth: "none" }}
          >
            {opciones.map((o) => {
              const activo = puesto && Number(valor) === o;
              return (
                // Pinchable además de deslizable: con el ratón, acertar girando es un
                // incordio, y el valor que quieres suele estar a la vista.
                <div key={o} role="button"
                     onClick={() => { marcar(); elegir(o); setAbierta(false); }}
                     className="flex cursor-pointer items-center justify-center text-[13px]"
                     style={{ height: ALTO, scrollSnapAlign: "center",
                              color: activo ? theme.accent : theme.text,
                              fontWeight: activo ? 700 : 400 }}>
                  {o.toFixed(dec)}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function CampoUI({ campo, zonas, valor, sugerencia, onChange }: {
  campo: Campo; zonas: string[]; valor: string | number | undefined;
  sugerencia: string | number | undefined; onChange: (v: string) => void;
}) {
  const esEscala = campo.tipo === "entero" && campo.minimo !== null
    && campo.maximo !== null && campo.maximo - campo.minimo <= 9;
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px]" style={{ color: theme.text }}>
        {campo.etiqueta}
        {campo.ayuda && <span style={{ color: theme.muted }}> · {campo.ayuda}</span>}
      </span>
      {campo.tipo === "zonas" ? (
        <Zonas zonas={zonas} valor={valor} onChange={onChange} />
      ) : campo.paso ? (
        <Rueda campo={campo} valor={valor} sugerencia={sugerencia} onChange={onChange} />
      ) : esEscala ? (
        <Escala campo={campo} valor={valor} onChange={onChange} />
      ) : campo.tipo === "texto" ? (
        <textarea
          className="jarvis-input w-full" rows={2} value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        // Las horas, con el selector del propio móvil: en Android sale la ruleta de
        // reloj y no hay forma de escribir algo que no sea HH:MM, que es justo lo que
        // el backend exige. Escribiéndolas a mano, un "23.40" se lo comía el validador.
        <input
          className="jarvis-input w-full"
          type={campo.tipo === "hora" ? "time" : "number"}
          inputMode={campo.tipo === "hora" ? undefined : "decimal"}
          // Sin `step` en las horas: con step=1 el navegador entiende "un segundo" y
          // pinta un hueco de segundos (--:--:--) que no se usa para nada.
          step={campo.tipo === "hora" ? undefined : campo.tipo === "decimal" ? "0.1" : "1"}
          value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}

function Editor({ tipo, esquema, fecha, onGuardado }: {
  tipo: TipoFormulario; esquema: Esquema; fecha: string; onGuardado: () => void;
}) {
  const [valores, setValores] = useState<Valores>({});
  const [sugerencias, setSugerencias] = useState<Valores>({});
  // Qué ha tocado ÉL en esta visita. Lo precargado no se reenvía: el editor abre con lo
  // que ya hay guardado, así que mandarlo todo convertía un "Guardar" sin tocar nada en
  // una pesada de hoy que nadie se hizo.
  const tocados = useRef<Set<string>>(new Set());
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let vivo = true;
    setCargando(true); setError(null); setOk(false);
    tocados.current = new Set();
    // Precargar lo que ya hay es lo que permite CORREGIR y no solo añadir.
    fetchValores(tipo, fecha)
      .then((r) => { if (vivo) { setValores(r.valores); setSugerencias(r.sugerencias); } })
      .catch((e) => vivo && setError(String(e.message ?? e)))
      .finally(() => vivo && setCargando(false));
    return () => { vivo = false; };
  }, [tipo, fecha]);

  const cambiar = (n: string, v: string) => {
    setValores((p) => ({ ...p, [n]: v }));
    tocados.current.add(n);
    setOk(false);
  };

  const enviar = async () => {
    setGuardando(true); setError(null);
    try {
      // Solo lo que ha tocado y tiene valor: un campo vacío significa "no lo toques",
      // no "bórralo", y uno sin tocar ya está como estaba.
      const utiles = Object.fromEntries(
        Object.entries(valores).filter(([k, v]) =>
          k !== "fecha" && tocados.current.has(k) && String(v).trim() !== ""),
      );
      const res = await guardar(tipo, fecha, utiles);
      tocados.current = new Set();
      setValores(res.valores ?? {});
      setOk(true);
      onGuardado();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <div className="text-[11px]" style={{ color: theme.muted }}>Cargando el día…</div>;

  return (
    <div className="flex flex-col gap-3" data-no-expand>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {esquema[tipo].campos.map((c) => (
          <CampoUI key={c.nombre} campo={c} zonas={esquema.zonas}
                   valor={valores[c.nombre]} sugerencia={sugerencias[c.nombre]}
                   onChange={(v) => cambiar(c.nombre, v)} />
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button" onClick={enviar} disabled={guardando}
          className="jarvis-chip px-3 py-1 text-[11px]"
          style={{ opacity: guardando ? 0.5 : 1 }}
        >
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        {ok && <span className="text-[11px]" style={{ color: theme.good }}>Guardado</span>}
        {error && <span className="text-[11px]" style={{ color: theme.alert }}>{error}</span>}
      </div>
      <div className="text-[10px]" style={{ color: theme.muted }}>
        Se guarda en la misma hoja que los formularios de Google, así que puedes corregir
        lo que ya metiste. Los paneles (readiness, carga…) no cambian hasta que vuelva a
        pasar el pipeline.
      </div>
    </div>
  );
}

// `dias` viene del selector de rango del dashboard: si Hugo mira 7 días, el semáforo y
// la tira tienen que hablar de esos 7 días, no de otros catorce por su cuenta.
function usarEstado(dias: number) {
  const [estado, setEstado] = useState<EstadoFormularios | null>(null);
  const recargar = useCallback(() => {
    fetchEstado(dias).then(setEstado).catch(() => {});
  }, [dias]);
  useEffect(() => { recargar(); }, [recargar]);
  return { estado, recargar };
}

/** Contestar, sin pasar por el chat, qué semana es una pestaña del plan que el pipeline
 *  no supo colocar (el entrenador la ha bautizado de una forma nueva y sin número).
 *
 *  Las letras P/B/S van FIJAS y los tres números se eligen con la misma rueda que el
 *  resto del panel: no hay nada que teclear ni formato que recordar. Y arrancan ya
 *  puestas en la semana siguiente a la que acaba de entrenar (`/plan/pendientes`), que
 *  es casi siempre la buena, así que lo normal es mirar que cuadra y darle a Guardar.
 *
 *  OJO, esto va al revés que el peso: allí la sugerencia NO se manda si no se toca la
 *  rueda, porque un Guardar de más apuntaría una pesada que nadie se hizo. Aquí sí se
 *  manda tal cual, porque no existe el "no contesto": la pestaña está esperando
 *  respuesta y lo que se guarda es justo lo que se está viendo en pantalla.
 *
 *  Lo mismo se puede decir hablando con Jarvis; esto existe porque dictarle tres números
 *  sueltos a un reconocedor de voz es donde más se equivoca. */
function PestanasSinEnrutar({ estado, onGuardado }: {
  estado: EstadoFormularios | null; onGuardado: () => void;
}) {
  const pendientes = estado?.fuentes?.plan?.faltan ?? [];
  const clave = pendientes.join("|");
  const [info, setInfo] = useState<PlanPendientes | null>(null);
  const [tocados, setTocados] = useState<Record<string, Record<string, number>>>({});
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    if (!clave) return;
    fetchPlanPendientes().then(setInfo).catch(() => {});
  }, [clave]);

  if (!clave || !info) return null;

  const valor = (p: string, campo: string) =>
    tocados[p]?.[campo] ?? (info.sugerencia as Record<string, number>)[campo];

  const mandar = async (p: string) => {
    const codigo = `P${valor(p, "plani")}B${valor(p, "bloque")}S${valor(p, "semana")}`;
    try {
      setAviso(await enrutarPestana(p, codigo));
      onGuardado();
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg p-3"
         style={{ background: "rgba(255,165,2,0.08)" }} data-no-expand>
      <div className="text-[11px]" style={{ color: theme.text }}>
        Pestañas del plan sin colocar · dime qué semana son
      </div>
      {pendientes.map((p) => (
        <div key={p} className="flex flex-wrap items-end gap-2">
          <span className="w-full text-[11px] sm:w-auto" style={{ color: theme.muted }}>{p}</span>
          {info.campos.map((c) => (
            <div key={c.nombre} className="flex items-center gap-1">
              <span className="text-[11px]" style={{ color: theme.accent }}>{c.etiqueta}</span>
              <Rueda
                campo={c}
                valor={valor(p, c.nombre)}
                sugerencia={(info.sugerencia as Record<string, number>)[c.nombre]}
                onChange={(v) => setTocados((t) => ({
                  ...t, [p]: { ...(t[p] ?? {}), [c.nombre]: Number(v) },
                }))}
              />
            </div>
          ))}
          <button type="button" className="jarvis-chip px-3 py-1 text-[11px]"
                  onClick={() => mandar(p)}>Guardar</button>
        </div>
      ))}
      {aviso && <div className="text-[10px]" style={{ color: theme.muted }}>{aviso}</div>}
    </div>
  );
}

export default function FormulariosPanel({ dias, onExpand }: {
  dias: number; onExpand?: (origin?: DOMRect) => void;
}) {
  const { estado } = usarEstado(dias);
  const sub = estado ? estado.resumen : "";
  return (
    <Panel title="Formularios" subtitle={sub} onExpand={onExpand}>
      <div className="flex flex-col gap-4">
        <Semaforo estado={estado} />
        {estado && (
          <div className="flex flex-col gap-2">
            <Tira estado={estado} />
            <Leyenda />
          </div>
        )}
      </div>
    </Panel>
  );
}

export function FormulariosExpanded({ dias }: { dias: number }) {
  const { estado, recargar } = usarEstado(dias);
  const [esquema, setEsquema] = useState<Esquema | null>(null);
  const [tipo, setTipo] = useState<TipoFormulario>("am");
  const [fecha, setFecha] = useState(hoyISO());

  useEffect(() => { fetchEsquema().then(setEsquema).catch(() => {}); }, []);

  const tipos = useMemo(() => ["am", "pm", "peso"] as TipoFormulario[], []);

  return (
    <div className="mx-auto flex h-[72vh] min-h-0 w-full max-w-3xl flex-col">
      <div className="mb-3 flex shrink-0 flex-col gap-3">
        <Semaforo estado={estado} />
        <PestanasSinEnrutar estado={estado} onGuardado={recargar} />
        {estado && (
          <div className="flex flex-col gap-2">
            <Tira estado={estado} />
            <Leyenda />
          </div>
        )}
      </div>
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2" data-no-expand>
        {tipos.map((t) => (
          <button
            key={t} type="button" onClick={() => setTipo(t)}
            className="jarvis-chip px-3 py-1 text-[11px]"
            style={{
              background: tipo === t ? "rgba(0,212,255,0.18)" : undefined,
              color: tipo === t ? theme.accent : undefined,
            }}
          >
            {esquema?.[t].titulo ?? t.toUpperCase()}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-[11px]" style={{ color: theme.muted }}>
          Día
          <input
            className="jarvis-input" type="date" value={fecha}
            onChange={(e) => setFecha(e.target.value)}
          />
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {esquema
          ? <Editor tipo={tipo} esquema={esquema} fecha={fecha} onGuardado={recargar} />
          : <div className="text-[11px]" style={{ color: theme.muted }}>Cargando formularios…</div>}
      </div>
    </div>
  );
}
