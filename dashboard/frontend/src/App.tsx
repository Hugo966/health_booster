import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchData, num, type SheetData } from "./lib/api";
import Arranque from "./components/Arranque";
import Readiness, { ReadinessExpanded } from "./components/Readiness";
import HrvTrend, { HrvExpanded } from "./components/HrvTrend";
import SleepPanel, { SleepExpanded } from "./components/SleepPanel";
import LoadPanel, { LoadExpanded, type Sesion } from "./components/LoadPanel";
import StrengthTrend, { StrengthExpanded } from "./components/StrengthTrend";
import WeightTrend, { WeightExpanded } from "./components/WeightTrend";
import CorrelationHeatmap, { CorrelationExpanded } from "./components/CorrelationHeatmap";
import ChatPanel, { ChatExpanded } from "./components/ChatPanel";
import NotasPanel, { NotasExpanded } from "./components/NotasPanel";
import FormulariosPanel, { FormulariosExpanded } from "./components/FormulariosPanel";
import Expanded from "./components/Expanded";
import RangeSelector, { inRange, rangeStart, type Range } from "./components/RangeSelector";
import { useObjetivoPeso } from "./lib/goal";
import { useChat, type Chat } from "./lib/chat";
import { useVoz } from "./lib/voz";
import { reproducir } from "./lib/acciones";
import { anim, theme } from "./lib/theme";

type Widget = "readiness" | "hrv" | "sueno" | "carga" | "fuerza" | "peso" | "correlaciones" | "notas" | "formularios" | "chat";

const TITULOS: Record<Widget, string> = {
  readiness: "Readiness",
  hrv: "HRV",
  sueno: "Sueño",
  carga: "Carga",
  fuerza: "Fuerza",
  peso: "Peso",
  correlaciones: "Correlaciones",
  notas: "Notas",
  formularios: "Formularios",
  chat: "Jarvis",
};

const ES_WIDGET = (s: string): s is Widget => s in TITULOS;

// El widget ampliado vive en el hash: /#fuerza se puede compartir y sobrevive a un
// recargado. Atrás del navegador cierra la vista, como espera cualquiera.
function useWidgetEnHash(): [Widget | null, (w: Widget | null) => void] {
  const leer = () => {
    const h = location.hash.slice(1);
    return ES_WIDGET(h) ? h : null;
  };
  // Al ARRANCAR, el chat es la excepción: recargar con #chat te plantaba el orbe a
  // pantalla completa antes de ver el dashboard, y Hugo quiere entrar por el dashboard.
  // Los demás paneles sí se restauran (el deep-link sigue sirviendo para compartirlos).
  const [w, setW] = useState<Widget | null>(() => {
    const inicial = leer();
    if (inicial === "chat") {
      history.replaceState(null, "", location.pathname + location.search);
      return null;
    }
    return inicial;
  });
  useEffect(() => {
    const onHash = () => setW(leer());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const set = (next: Widget | null) => {
    if (next) location.hash = next;
    else if (location.hash) history.pushState(null, "", location.pathname + location.search);
    setW(next);
  };
  return [w, set];
}

export default function App() {
  const [data, setData] = useState<SheetData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<Range>(90);
  const [abierto, setAbierto] = useWidgetEnHash();
  // Rectángulo del panel pinchado, para que el overlay crezca desde ahí.
  const [origen, setOrigen] = useState<DOMRect | null>(null);
  // El rango global manda también en Formularios. "TODO" (0) se topa en 90:
  // una tira de 400 columnas no se lee, y los huecos viejos ya no se arreglan.
  const diasRango = range === 0 ? 90 : range;
  const abrir = (w: Widget) => (o?: DOMRect) => { setOrigen(o ?? null); setAbierto(w); };
  const [objetivo, setObjetivo] = useObjetivoPeso();
  // El hilo del chat vive aquí para que el compacto y el ampliado lo compartan.
  // Chat y voz se necesitan mutuamente (la voz manda comandos al chat; el chat le
  // pasa la respuesta para leerla), así que el chat se referencia por ref para
  // romper el círculo: la voz llama a chatRef, el chat llama a voz.decir.
  const chatRef = useRef<Chat | null>(null);
  const voz = useVoz({ onComando: (texto) => chatRef.current?.enviar(texto) });
  const chat = useChat(
    // Acciones de UI: v1 solo navegación de paneles (abrir/cerrar), vía el hash.
    (acciones) => reproducir(acciones, { abrir: (p) => setAbierto(p as Widget), cerrar: () => setAbierto(null) }),
    // Abre el turno de voz: el chat le empuja cada frase en cuanto está escrita, así
    // Jarvis empieza a hablar sin esperar a terminar la respuesta entera.
    () => voz.hablar(),
  );
  chatRef.current = chat;
  // Secuencia de arranque: tapa la pantalla mientras cargan los datos y se
  // aparta al terminar. Con "reducir movimiento" ni se monta.
  //
  // Son dos estados y no uno porque se solapan: el panel se monta cuando los
  // engranajes EMPIEZAN a separarse, y el overlay no se desmonta hasta que
  // termina de desvanecerse encima.
  const [arrancando, setArrancando] = useState(anim.on);
  const [revelado, setRevelado] = useState(!anim.on);
  const revelar = useCallback(() => setRevelado(true), []);
  const finArranque = useCallback(() => setArrancando(false), []);

  useEffect(() => {
    fetchData().then(setData).catch((e) => setError(String(e)));
  }, []);

  const start = useMemo(() => rangeStart(range), [range]);

  // El rango recorta todas las series por fecha. Readiness es la excepción: el hero
  // siempre muestra el último valor disponible, mires el rango que mires.
  const dd = useMemo(
    () => (data?.derived_diario ?? []).filter((r) => inRange(String(r.fecha), start)),
    [data, start],
  );

  const readinessTodo = useMemo(
    () =>
      (data?.derived_diario ?? [])
        .map((r) => ({ fecha: String(r.fecha), v: num(r.readiness) }))
        .filter((x): x is { fecha: string; v: number } => x.v !== null),
    [data],
  );
  const hoy = readinessTodo[readinessTodo.length - 1] ?? null;
  // Media de los 7 días PREVIOS, sin incluir el de hoy: si no, el propio valor
  // amortigua su delta contra sí mismo.
  const previos = readinessTodo.slice(-8, -1);
  const base7 = previos.length ? previos.reduce((s, x) => s + x.v, 0) / previos.length : null;

  const readinessRango = useMemo(
    () => readinessTodo.filter((r) => inRange(r.fecha, start)),
    [readinessTodo, start],
  );

  const hrvRows = useMemo(
    () => dd.map((r) => ({
      fecha: String(r.fecha), hrv: num(r.hrv_rmssd), fc: num(r.fc_reposo),
    })),
    [dd],
  );

  const sleepRows = useMemo(
    () =>
      dd.map((r) => ({
        fecha: String(r.fecha),
        horas: num(r.sueno_horas),
        cama: num(r.tiempo_en_cama_h),
        calidad: num(r.sueno_calidad),
        score: num(r.sueno_score),
        eficiencia: num(r.eficiencia_sueno),
      })),
    [dd],
  );

  // El RPE de sesión (form PM) y el sRPE ya calculado viven en derived_diario; se unen a
  // las sesiones por fecha. El sRPE NO se recalcula aquí: la fórmula está en
  // status_pipeline.py y este panel solo la consume, para que la pantalla y Jarvis
  // —que lee la misma columna de la hoja— no puedan dar números distintos.
  const porFecha = useMemo(() => {
    const rpe = new Map<string, number>();
    const srpe = new Map<string, number>();
    for (const r of data?.derived_diario ?? []) {
      const f = String(r.fecha);
      const v = num(r.rpd_sesion);
      if (v !== null) rpe.set(f, v);
      const s = num(r.sRPE_series);
      if (s !== null) srpe.set(f, s);
    }
    return { rpe, srpe };
  }, [data]);

  // Las bandas de carga se calculan sobre TODO el histórico; el rango solo recorta
  // lo que se dibuja. Si no, "alto para Hugo" cambiaría al cambiar de 90D a 30D.
  const sesionesTodas: Sesion[] = useMemo(
    () =>
      (data?.entreno_sesion ?? [])
        .map((s) => ({
          fecha: String(s.fecha),
          nSeries: num(s.n_series_total),
          nFallos: num(s.n_fallos_total) ?? 0,
          rpeSesion: porFecha.rpe.get(String(s.fecha)) ?? null,
          srpeSeries: porFecha.srpe.get(String(s.fecha)) ?? null,
          volumen: num(s.volumen_total) ?? 0,
          volBasicos: num(s.vol_basicos),
          volAccesorios: num(s.vol_accesorios),
        }))
        .filter((s) => s.volumen > 0)
        .sort((a, b) => a.fecha.localeCompare(b.fecha)),
    [data, porFecha],
  );
  const sesionesRango = useMemo(
    () => sesionesTodas.filter((s) => inRange(s.fecha, start)),
    [sesionesTodas, start],
  );

  // Igual que en carga: el histórico completo fija la paleta de colores por
  // ejercicio, para que una variante no cambie de color al mover el rango.
  const setsTodos = useMemo(() => data?.entreno_sets ?? [], [data]);
  const setsRango = useMemo(
    () => setsTodos.filter((s) => inRange(String(s.fecha ?? ""), start)),
    [setsTodos, start],
  );

  // TODO el historial de pesadas (para el ritmo histórico y las estimaciones), y el
  // subconjunto del rango (lo que dibuja el gráfico). Igual criterio que las bandas.
  const weightAll = useMemo(
    () =>
      (data?.peso ?? [])
        .map((r) => ({ fecha: String(r.fecha), peso: num(r.peso_kg) }))
        .filter((x): x is { fecha: string; peso: number } => x.peso !== null)
        .sort((a, b) => a.fecha.localeCompare(b.fecha)),
    [data],
  );
  const weightRows = useMemo(
    () => weightAll.filter((x) => inRange(x.fecha, start)),
    [weightAll, start],
  );

  const cerrar = () => setAbierto(null);

  return (
    <div className="min-h-screen w-full p-6 md:p-8" style={{ background: theme.bg, color: theme.text }}>
      <header className="mx-auto mb-8 max-w-6xl">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1
            className="font-display text-2xl tracking-[0.5em]"
            style={{ color: theme.accent, textShadow: "0 0 18px rgba(0,212,255,0.5)" }}
          >
            JARVIS
          </h1>
          <span className="font-display text-[10px] uppercase tracking-[0.35em]" style={{ color: theme.muted }}>
            Panel de bienestar
          </span>
          <div className="ml-auto">
            <RangeSelector value={range} onChange={setRange} />
          </div>
        </div>
        <div
          className="mt-3 h-px w-full"
          style={{ background: "linear-gradient(90deg, rgba(0,212,255,0.5), rgba(0,212,255,0.05) 60%, transparent)" }}
        />
      </header>

      {revelado && error && <div style={{ color: theme.alert }}>Error: {error}</div>}
      {revelado && !data && !error && <div style={{ color: theme.muted }}>Cargando datos…</div>}

      {revelado && data && (
        <div className="jarvis-rise mx-auto flex max-w-6xl flex-col gap-6">
          <div className="flex justify-center">
            <Readiness
              value={hoy?.v ?? null}
              base7={base7}
              fecha={hoy?.fecha ?? null}
              onExpand={abrir("readiness")}
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <HrvTrend rows={hrvRows} onExpand={abrir("hrv")} />
            <SleepPanel rows={sleepRows} onExpand={abrir("sueno")} />
            <LoadPanel todas={sesionesTodas} rango={sesionesRango} onExpand={abrir("carga")} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <StrengthTrend todos={setsTodos} rango={setsRango} onExpand={abrir("fuerza")} />
            <WeightTrend
              rows={weightRows}
              todo={weightAll}
              objetivo={objetivo}
              onChangeObjetivo={setObjetivo}
              onExpand={abrir("peso")}
            />
            <CorrelationHeatmap rows={dd} onExpand={abrir("correlaciones")} />
          </div>

          {/* Notas: texto libre de los formularios, a lo ancho (puede ser largo). */}
          <NotasPanel rows={data.derived_diario} onExpand={abrir("notas")} />


          {/* El chat de Jarvis, a lo ancho: es la pieza central de la Fase 2, no
              una columna más. Compacto aquí; conversación entera al ampliar. */}
          <ChatPanel chat={chat} voz={voz} onExpand={abrir("chat")} />

          {/* Formularios: el semáforo de lo que falta por rellenar. Se pide aparte al
              backend (lee las pestañas origen), no sale de `data`: derived_diario no
              tiene fila para los días vacíos, que son justo los que hay que detectar. */}
          <FormulariosPanel dias={diasRango} onExpand={abrir("formularios")} />
        </div>
      )}

      {arrancando && (
        <Arranque
          cargado={data !== null || error !== null}
          onRevelar={revelar}
          onFin={finArranque}
        />
      )}

      {revelado && data && abierto && (
        <Expanded
          title={TITULOS[abierto]}
          onClose={cerrar}
          origin={origen}
          // Formularios no dibuja una serie temporal: se rellena un día concreto, y ese
          // se elige con su propio selector de fecha. El rango global aquí solo confunde.
          actions={abierto === "formularios"
            ? undefined
            : <RangeSelector value={range} onChange={setRange} />}
          sinCaja={abierto === "chat"}
        >
          {abierto === "readiness" && <ReadinessExpanded series={readinessRango} />}
          {abierto === "hrv" && <HrvExpanded rows={hrvRows} />}
          {abierto === "sueno" && <SleepExpanded rows={sleepRows} />}
          {abierto === "carga" && <LoadExpanded todas={sesionesTodas} rango={sesionesRango} sets={setsRango} />}
          {abierto === "fuerza" && <StrengthExpanded todos={setsTodos} rango={setsRango} />}
          {abierto === "peso" && (
            <WeightExpanded rows={weightRows} todo={weightAll} objetivo={objetivo} onChangeObjetivo={setObjetivo} />
          )}
          {abierto === "correlaciones" && <CorrelationExpanded rows={dd} />}
          {abierto === "notas" && <NotasExpanded rows={data.derived_diario} />}
          {abierto === "formularios" && <FormulariosExpanded dias={diasRango} />}
          {abierto === "chat" && <ChatExpanded chat={chat} voz={voz} />}
        </Expanded>
      )}
    </div>
  );
}
