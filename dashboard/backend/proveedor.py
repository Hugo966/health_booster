"""Proveedor de modelo — una interfaz, dos implementaciones (Ollama y Anthropic).

Se elige con JARVIS_PROVEEDOR en el .env. La razón de montar esto desde el
principio, aunque hoy solo se use Ollama, es que retrofitear una abstracción de
proveedor cuando ya hay lógica escrita encima es carísimo, y aquí sale casi
gratis: el objetivo es que probar el mismo Jarvis (misma personalidad, misma
memoria) contra los dos sea cambiar una variable de entorno.

El grueso del módulo es NORMALIZAR: las dos APIs difieren sobre todo en cómo
declaran las herramientas y cómo devuelven las llamadas, así que aquí dentro se
traduce a una forma común y fuera nadie se entera de con quién está hablando.

Las herramientas se declaran en formato neutro:
    {"nombre": ..., "descripcion": ..., "params": {json-schema de propiedades},
     "requeridos": [...]}
"""
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# 7B y no 14B: la RTX 3060 del portátil es la variante Laptop, con 6 GB de VRAM.
# El default importa porque los .env ya creados no tienen esta variable.
OLLAMA_MODELO = os.getenv("OLLAMA_MODELO", "qwen2.5:7b")
ANTHROPIC_MODELO = os.getenv("ANTHROPIC_MODELO", "claude-sonnet-5")
TIMEOUT = 120  # un modelo local puede tardar bastante en la primera carga


@dataclass
class Llamada:
    """Una herramienta que el modelo quiere usar."""
    nombre: str
    args: dict
    id: str = ""


@dataclass
class Respuesta:
    """Forma común de respuesta, venga de quien venga."""
    texto: str = ""
    llamadas: list[Llamada] = field(default_factory=list)


def _rescatar_llamadas_texto(texto: str, nombres: list[str]) -> tuple[str, list[Llamada]]:
    """Rescata llamadas que el modelo escribió DENTRO del texto —p.ej.
    `abrir_panel({"panel": "peso"})`— en vez de emitirlas por el canal de
    herramientas.

    Los modelos pequeños (qwen2.5:7b) lo hacen de vez en cuando, y es doblemente
    malo: el usuario ve la llamada cruda (parece roto) y, como el hilo se guarda
    en memoria, ese texto se vuelve un ejemplo que el modelo imita en los turnos
    siguientes. Al sacarlas aquí, la acción se ejecuta de verdad y lo que se
    guarda queda limpio, cortando ese bucle.

    Solo se buscan nombres de herramientas conocidos seguidos de `({...}`, un
    patrón que no aparece en prosa normal, así que no se traga texto legítimo.
    """
    if not texto or not nombres:
        return texto, []
    llamadas: list[Llamada] = []
    patron = re.compile(
        r"\b(" + "|".join(re.escape(n) for n in nombres) + r")\s*\(\s*(\{.*?\})\s*\)",
        re.DOTALL,
    )

    def _sub(m: re.Match) -> str:
        nombre, crudo = m.group(1), m.group(2)
        try:
            args = json.loads(crudo)
        except json.JSONDecodeError:
            try:  # a veces usa comillas simples
                args = json.loads(crudo.replace("'", '"'))
            except json.JSONDecodeError:
                return ""  # ilegible: al menos que no lo vea el usuario
        if isinstance(args, dict):
            llamadas.append(Llamada(nombre=nombre, args=args))
        return ""

    limpio = patron.sub(_sub, texto)
    limpio = re.sub(r"\n{3,}", "\n\n", limpio).strip()
    return limpio, llamadas


class ProveedorOllama:
    """Modelo local. Sin coste y sin que los datos de salud salgan de casa."""

    nombre = "ollama"

    def __init__(self, modelo: str | None = None):
        self.modelo = modelo or OLLAMA_MODELO

    def _herramientas(self, hs):
        return [
            {
                "type": "function",
                "function": {
                    "name": h["nombre"],
                    "description": h["descripcion"],
                    "parameters": {
                        "type": "object",
                        "properties": h.get("params", {}),
                        "required": h.get("requeridos", []),
                    },
                },
            }
            for h in hs
        ]

    def responder(self, sistema: str, mensajes: list[dict], herramientas=None) -> Respuesta:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}] + mensajes,
            "stream": False,
            # Mantener el modelo en la VRAM entre mensajes: si se descarga (idle de
            # 5 min por defecto), el siguiente mensaje paga ~40s de recarga desde
            # disco. Con 6 GB solo cabe este modelo, así que no estorba a nadie.
            "keep_alive": "30m",
            # A ~20 tok/s en este portátil, la latencia la manda la longitud de la
            # respuesta: 40 tokens ≈ 2s, 180 ≈ 9s. El tope evita que un mensaje se
            # dispare; la brevedad habitual la marca el prompt de personalidad.
            "options": {"num_predict": 128},
        }
        if herramientas:
            cuerpo["tools"] = self._herramientas(herramientas)

        r = requests.post(f"{OLLAMA_URL}/api/chat", json=cuerpo, timeout=TIMEOUT)
        r.raise_for_status()
        msg = r.json().get("message", {})

        llamadas = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            args = fn.get("arguments", {})
            # Algunos modelos devuelven los argumentos como string JSON en vez de objeto.
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            llamadas.append(Llamada(nombre=fn.get("name", ""), args=args))

        # Red de seguridad: si el modelo escribió alguna llamada como texto en vez
        # de emitirla por el canal, la rescatamos y la quitamos de lo que se ve.
        texto = msg.get("content", "") or ""
        if herramientas:
            texto, extra = _rescatar_llamadas_texto(texto, [h["nombre"] for h in herramientas])
            llamadas.extend(extra)

        return Respuesta(texto=texto, llamadas=llamadas)


class ProveedorAnthropic:
    """API de Anthropic. Mejor tono y mejor uso de herramientas, a cambio de
    coste por mensaje y de que la conversación salga de la máquina."""

    nombre = "anthropic"

    def __init__(self, modelo: str | None = None):
        # Import perezoso: el SDK solo hace falta si se usa este proveedor, así
        # que no tenerlo instalado no debe romper a quien tire de Ollama.
        import anthropic

        self.cliente = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.modelo = modelo or ANTHROPIC_MODELO

    def _herramientas(self, hs):
        return [
            {
                "name": h["nombre"],
                "description": h["descripcion"],
                "input_schema": {
                    "type": "object",
                    "properties": h.get("params", {}),
                    "required": h.get("requeridos", []),
                },
            }
            for h in hs
        ]

    def responder(self, sistema: str, mensajes: list[dict], herramientas=None) -> Respuesta:
        kwargs = {
            "model": self.modelo,
            "max_tokens": 1024,
            # El bloque de sistema (personaje + memoria + briefing) es largo y
            # apenas cambia entre mensajes: cachearlo abarata bastante la charla.
            "system": [
                {
                    "type": "text",
                    "text": sistema,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": mensajes,
        }
        if herramientas:
            kwargs["tools"] = self._herramientas(herramientas)

        msg = self.cliente.messages.create(**kwargs)

        texto, llamadas = "", []
        for bloque in msg.content:
            if bloque.type == "text":
                texto += bloque.text
            elif bloque.type == "tool_use":
                llamadas.append(Llamada(nombre=bloque.name, args=bloque.input, id=bloque.id))

        return Respuesta(texto=texto, llamadas=llamadas)


class ProveedorFalso:
    """Modelo de mentira, para desarrollar sin Ollama ni API.

    Existe porque el circuito completo (herramientas, acciones de UI, memoria,
    panel de React) se puede verificar sin que haya un modelo detrás, y hacerlo
    así evita depurar a la vez la fontanería y el comportamiento del modelo.

    Dos modos:
      - con `guion`: devuelve esas respuestas en orden. Determinista, para tests.
      - sin `guion`: heurística tonta por palabras clave, suficiente para ver el
        circuito moverse a mano.
    """

    nombre = "falso"

    def __init__(self, guion: list[Respuesta] | None = None):
        self.guion = list(guion or [])
        self.recibidos = []  # lo que se le pidió, para poder comprobarlo en tests

    def responder(self, sistema: str, mensajes: list[dict], herramientas=None) -> Respuesta:
        self.recibidos.append({"sistema": sistema, "mensajes": list(mensajes)})
        if self.guion:
            return self.guion.pop(0)

        ultimo = next(
            (m["content"] for m in reversed(mensajes) if m.get("role") == "user"), ""
        ).lower()

        # Si acaba de llegar un resultado de herramienta, toca comentar, no pedir más.
        if ultimo.startswith("[resultado de"):
            return Respuesta(texto="Ya lo tengo delante. Pinta bien.")

        for panel, palabras in [
            ("sueno", ("sueño", "sueno", "dormi", "dormí")),
            ("carga", ("carga", "volumen", "srpe")),
            ("fuerza", ("fuerza", "banca", "sentadilla", "muerto")),
            ("peso", ("peso", "kilos", "báscula", "bascula")),
            ("hrv", ("hrv", "variabilidad")),
        ]:
            if any(p in ultimo for p in palabras):
                return Respuesta(
                    texto=f"Venga, te abro {panel}.",
                    llamadas=[Llamada(nombre="abrir_panel", args={"panel": panel})],
                )

        if "leyendo" in ultimo or "libro" in ultimo:
            return Respuesta(
                texto="Anotado, luego te pregunto qué tal va.",
                llamadas=[Llamada(nombre="recordar",
                                  args={"tema": "lectura", "texto": ultimo[:120]})],
            )

        return Respuesta(texto="Aquí sigo. Cuéntame.")


def precalentar():
    """Carga el modelo local en la VRAM al arrancar, en segundo plano, para que el
    PRIMER mensaje no espere a la carga desde disco (~8s). Con keep_alive luego se
    queda residente. Si Ollama no está levantado, falla en silencio: ya lo dirá el
    primer mensaje con un error claro."""
    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODELO, "prompt": "", "keep_alive": "30m"},
            timeout=TIMEOUT,
        )
    except Exception:
        pass


def obtener(nombre: str | None = None):
    """Devuelve el proveedor configurado. `nombre` fuerza uno concreto (para comparar)."""
    elegido = (nombre or os.getenv("JARVIS_PROVEEDOR", "ollama")).lower()
    if elegido == "anthropic":
        return ProveedorAnthropic()
    if elegido == "ollama":
        return ProveedorOllama()
    if elegido == "falso":
        return ProveedorFalso()
    raise ValueError(
        f"JARVIS_PROVEEDOR desconocido: {elegido!r} (usa 'ollama', 'anthropic' o 'falso')"
    )
