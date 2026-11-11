// La app pregunta dónde está quien la usa, UNA vez, la primera que la abre.
//
// Va aquí y no en el `.env` porque esto no lo contesta quien instala el proyecto, sino
// quien lo usa: el nombre de tu ciudad no es configuración de despliegue. Se guarda en
// la hoja (pestaña `ajustes`), así que vale igual desde el móvil, desde el portátil y
// desde la VM, y sobrevive a los despliegues.
//
// Solo sirve para el tiempo, y eso es lo único que se dice: pedir la ubicación sin
// explicar para qué es como se consiguen los "no, gracias". Vale dirección, ciudad o
// código postal —cada uno lo tiene en la cabeza de una forma—, pero lo que se guarda
// es siempre la ciudad y el país: para saber si llueve sobra, y así el portal de nadie
// acaba escrito en la hoja.
import { useEffect, useState } from "react";

import { API_BASE } from "../lib/api";
import { theme } from "../lib/theme";

type Tiempo = { lugar: string; temp: number; cielo: string } | null;

export default function PedirUbicacion() {
  const [haceFalta, setHaceFalta] = useState(false);
  const [lugar, setLugar] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [tiempo, setTiempo] = useState<Tiempo>(null);

  useEffect(() => {
    fetch(`${API_BASE}/ubicacion`)
      .then((r) => r.json())
      .then((c) => {
        setHaceFalta(!c.ubicacion);
        setTiempo(c.tiempo ?? null);
      })
      .catch(() => {});
  }, []);

  if (!haceFalta) return null;

  const guardar = async () => {
    setGuardando(true);
    setError("");
    try {
      const r = await fetch(`${API_BASE}/ubicacion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lugar }),
      });
      const c = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(c.detail ?? "no pude guardar ese sitio");
      setTiempo(c.tiempo ?? null);
      setHaceFalta(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-lg p-3"
      style={{ background: "rgba(0,212,255,0.07)" }}
      data-no-expand
    >
      <span className="text-[11px]" style={{ color: theme.text }}>
        ¿Dónde estás? Dirección, ciudad o código postal — para que Jarvis sepa qué tiempo hace.
      </span>
      <input
        className="jarvis-input w-40"
        placeholder="Madrid · 28001 · Calle…"
        value={lugar}
        onChange={(e) => setLugar(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && lugar.trim()) guardar();
        }}
      />
      <button
        type="button"
        className="jarvis-chip px-3 py-1 text-[11px]"
        disabled={guardando || !lugar.trim()}
        onClick={guardar}
      >
        {guardando ? "Buscando…" : "Guardar"}
      </button>
      {error && (
        <span className="text-[10px]" style={{ color: theme.alert }}>
          {error}
        </span>
      )}
      {tiempo && (
        <span className="text-[10px]" style={{ color: theme.muted }}>
          {tiempo.lugar}: {tiempo.cielo}, {tiempo.temp}°
        </span>
      )}
    </div>
  );
}
