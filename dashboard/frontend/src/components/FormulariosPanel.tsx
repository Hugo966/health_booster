import { useCallback, useEffect, useMemo, useState } from "react";
import Panel from "./Panel";
import { theme } from "../lib/theme";
import {
  fetchEsquema, fetchEstado, fetchValores, guardar, hoyISO,
  type Campo, type EstadoFormularios, type Esquema, type Fuente,
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

function CampoUI({ campo, zonas, valor, onChange }: {
  campo: Campo; zonas: string[]; valor: string | number | undefined; onChange: (v: string) => void;
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
      ) : esEscala ? (
        <Escala campo={campo} valor={valor} onChange={onChange} />
      ) : campo.tipo === "texto" ? (
        <textarea
          className="jarvis-input w-full" rows={2} value={String(valor ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="jarvis-input w-full"
          type={campo.tipo === "hora" ? "text" : "number"}
          inputMode={campo.tipo === "hora" ? "text" : "decimal"}
          placeholder={campo.tipo === "hora" ? "HH:MM" : ""}
          step={campo.tipo === "decimal" ? "0.1" : "1"}
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
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let vivo = true;
    setCargando(true); setError(null); setOk(false);
    // Precargar lo que ya hay es lo que permite CORREGIR y no solo añadir.
    fetchValores(tipo, fecha)
      .then((v) => vivo && setValores(v))
      .catch((e) => vivo && setError(String(e.message ?? e)))
      .finally(() => vivo && setCargando(false));
    return () => { vivo = false; };
  }, [tipo, fecha]);

  const cambiar = (n: string, v: string) => {
    setValores((p) => ({ ...p, [n]: v }));
    setOk(false);
  };

  const enviar = async () => {
    setGuardando(true); setError(null);
    try {
      // Solo lo que tiene valor: un campo vacío significa "no lo toques", no "bórralo".
      const utiles = Object.fromEntries(
        Object.entries(valores).filter(([k, v]) => k !== "fecha" && String(v).trim() !== ""),
      );
      const res = await guardar(tipo, fecha, utiles);
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
                   valor={valores[c.nombre]} onChange={(v) => cambiar(c.nombre, v)} />
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
