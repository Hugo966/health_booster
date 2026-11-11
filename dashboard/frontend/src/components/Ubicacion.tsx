// Dónde está quien usa la app. Se pregunta UNA vez, nada más abrirla, y además se puede
// cambiar cuando quiera desde Ajustes: una ubicación que solo se puede poner el primer
// día es una ubicación que no se puede corregir, y la gente se muda.
//
// Va aquí y no en el `.env` porque esto no lo contesta quien instala el proyecto, sino
// quien lo usa. Se guarda en la hoja (pestaña `ajustes`), así que vale igual desde el
// móvil, el portátil y la VM, y sobrevive a los despliegues.
//
// Se admite dirección, ciudad o código postal —cada uno lo tiene en la cabeza de una
// forma— y se guardan DOS: la dirección entera, que sirve para lo que no es el tiempo, y
// una etiqueta corta (ciudad y país) que es la que se enseña, porque el parte de estado
// diría la calle en cada mensaje si fuera la larga.
import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "../lib/api";
import { theme } from "../lib/theme";

export type Lugar = { nombre: string; direccion?: string; lat: number; lon: number } | null;
export type Tiempo = { lugar: string; temp: number; cielo: string } | null;

/** Lee la ubicación guardada y el tiempo de ahí. Lo comparten el aviso y los ajustes. */
export function useUbicacion() {
  const [lugar, setLugar] = useState<Lugar>(null);
  const [tiempo, setTiempo] = useState<Tiempo>(null);
  const [cargado, setCargado] = useState(false);

  const recargar = useCallback(() => {
    fetch(`${API_BASE}/ubicacion`)
      .then((r) => r.json())
      .then((c) => {
        setLugar(c.ubicacion ?? null);
        setTiempo(c.tiempo ?? null);
      })
      .catch(() => {})
      .finally(() => setCargado(true));
  }, []);

  useEffect(() => { recargar(); }, [recargar]);
  return { lugar, tiempo, cargado, aplicar: (c: { ubicacion?: Lugar; tiempo?: Tiempo }) => {
    setLugar(c.ubicacion ?? null);
    setTiempo(c.tiempo ?? null);
  } };
}

/** La casilla y su botón. Es la misma en el aviso del principio y en los ajustes. */
export function CampoUbicacion({ onGuardado, autoFoco }: {
  onGuardado: (c: { ubicacion?: Lugar; tiempo?: Tiempo }) => void;
  autoFoco?: boolean;
}) {
  const [texto, setTexto] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const guardar = async () => {
    setGuardando(true);
    setError("");
    try {
      const r = await fetch(`${API_BASE}/ubicacion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lugar: texto }),
      });
      const c = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(c.detail ?? "no pude guardar ese sitio");
      setTexto("");
      onGuardado(c);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2" data-no-expand>
      <input
        className="jarvis-input w-48"
        placeholder="Madrid · 28001 · Calle…"
        autoFocus={autoFoco}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && texto.trim()) guardar(); }}
      />
      <button
        type="button"
        className="jarvis-chip px-3 py-1 text-[11px]"
        disabled={guardando || !texto.trim()}
        onClick={guardar}
      >
        {guardando ? "Buscando…" : "Guardar"}
      </button>
      {error && (
        <span className="text-[10px]" style={{ color: theme.alert }}>{error}</span>
      )}
    </div>
  );
}

/** El aviso del principio. Desaparece en cuanto hay ubicación; a partir de ahí se cambia
 *  desde Ajustes, que es donde la busca quien ya la puso una vez. */
export default function PedirUbicacion() {
  const { lugar, cargado, aplicar } = useUbicacion();
  if (!cargado || lugar) return null;
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-lg p-3"
      style={{ background: "rgba(0,212,255,0.07)" }}
      data-no-expand
    >
      <span className="text-[11px]" style={{ color: theme.text }}>
        ¿Dónde estás? Dirección, ciudad o código postal — para que Jarvis sepa qué tiempo hace.
      </span>
      <CampoUbicacion onGuardado={aplicar} />
    </div>
  );
}
