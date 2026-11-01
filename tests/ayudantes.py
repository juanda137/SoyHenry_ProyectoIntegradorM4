"""Dobles de prueba: reemplazan a OpenAI y a Langfuse para que nada salga a la red."""
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


class ClienteOpenAIFalso:
    """Imita client.chat.completions.create: cada llamada consume un elemento del guion."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.llamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.llamadas.append(kwargs)
        elemento = self.guion.pop(0)
        if isinstance(elemento, Exception):
            raise elemento
        return elemento


def respuesta_vision(texto, finish_reason="stop", refusal=None):
    """Una respuesta con la misma forma que la del SDK de OpenAI."""
    mensaje = SimpleNamespace(content=texto, refusal=refusal)
    uso = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=mensaje, finish_reason=finish_reason)], usage=uso, model="gpt-4o"
    )


class SpanFalso:
    """Guarda lo que recibiría un span real, para revisar la jerarquía en las pruebas."""

    def __init__(self, nombre, as_type, campos):
        self.nombre = nombre
        self.as_type = as_type
        self.campos = dict(campos)
        self.hijos = []

    def update(self, **campos):
        self.campos.update(campos)

    def __repr__(self):
        return "SpanFalso(" + repr(self.nombre) + ", " + repr(self.campos) + ", " + repr(self.hijos) + ")"


class LangfuseFalso:
    """Imita al cliente de Langfuse: arma el árbol de spans con una pila."""

    def __init__(self):
        self.raices = []
        self.pila = []
        self.flushes = 0

    @contextmanager
    def start_as_current_observation(self, *, name, as_type="span", **campos):
        span = SpanFalso(name, as_type, campos)
        (self.pila[-1].hijos if self.pila else self.raices).append(span)
        self.pila.append(span)
        try:
            yield span
        finally:
            self.pila.pop()

    def flush(self):
        self.flushes += 1

    def get_trace_url(self):
        return "https://langfuse.falso/traza"


def llm_falso(guion):
    """Sustituye al modelo en una cadena de LangChain y guarda lo que recibe."""
    pendientes = list(guion)
    mensajes = []
    configs = []

    def responder(entrada, config):
        mensajes.append(entrada)
        configs.append(config)
        elemento = pendientes.pop(0)
        if isinstance(elemento, Exception):
            raise elemento
        return elemento

    modelo = RunnableLambda(responder)
    modelo.mensajes = mensajes
    modelo.configs = configs
    return modelo


class LLMEstructuradoFalso:
    """Imita a ChatOpenAI.with_structured_output(..., include_raw=True)."""

    def __init__(self, guion):
        self.interno = llm_falso(guion)
        self.mensajes = self.interno.mensajes
        self.configs = self.interno.configs
        self.argumentos = None

    def with_structured_output(self, esquema, include_raw=False):
        self.argumentos = {"esquema": esquema, "include_raw": include_raw}
        return self.interno


def llm_estructurado_falso(guion):
    return LLMEstructuradoFalso(guion)


def ok(datos):
    """Respuesta estructurada correcta."""
    return {"raw": AIMessage(content=""), "parsed": datos, "parsing_error": None}


def fallo(mensaje):
    """Respuesta que no se pudo convertir al esquema."""
    return {"raw": AIMessage(content=""), "parsed": None, "parsing_error": ValueError(mensaje)}


def error_api(clase, status, codigo=None):
    """Crea una excepción real de openai sin hacer ninguna llamada."""
    pedido = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    respuesta = httpx.Response(status, request=pedido)
    return clase("error simulado", response=respuesta, body={"code": codigo})
