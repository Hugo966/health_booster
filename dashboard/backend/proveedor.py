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
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODELO = os.getenv("OLLAMA_MODELO", "qwen2.5:14b")
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

        return Respuesta(texto=msg.get("content", "") or "", llamadas=llamadas)


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


def obtener(nombre: str | None = None):
    """Devuelve el proveedor configurado. `nombre` fuerza uno concreto (para comparar)."""
    elegido = (nombre or os.getenv("JARVIS_PROVEEDOR", "ollama")).lower()
    if elegido == "anthropic":
        return ProveedorAnthropic()
    if elegido == "ollama":
        return ProveedorOllama()
    raise ValueError(f"JARVIS_PROVEEDOR desconocido: {elegido!r} (usa 'ollama' o 'anthropic')")
