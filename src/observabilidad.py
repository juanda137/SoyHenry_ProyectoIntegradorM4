"""Observabilidad con Langfuse: cada etapa del pipeline queda como un span dentro de una traza.

Los spans se abren a mano porque la consigna pide una jerarquía clara. Dentro de un span
activo, lo que registra el CallbackHandler de LangChain queda anidado automáticamente.
Si Langfuse no está disponible, el análisis sigue funcionando, solo que sin trazas.
"""
import sys
from contextlib import contextmanager

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

CLAVES_DE_EJEMPLO = ["pk-lf-xxx", "sk-lf-xxx"]


class SpanNulo:
    """Se usa cuando no hay Langfuse: acepta update() y no hace nada."""

    def update(self, **campos):
        pass


def _avisar(motivo):
    print("[aviso] " + motivo + ": el análisis sigue, pero sin trazas.", file=sys.stderr)


def crear_cliente_langfuse(config):
    """Devuelve el cliente de Langfuse, o None con un aviso si no se puede usar."""
    publica = config["langfuse_public_key"]
    secreta = config["langfuse_secret_key"]
    if not publica or not secreta or publica in CLAVES_DE_EJEMPLO or secreta in CLAVES_DE_EJEMPLO:
        _avisar("Langfuse no está configurado")
        return None
    try:
        cliente = Langfuse(public_key=publica, secret_key=secreta, host=config["langfuse_host"])
        # El SDK envía las trazas en segundo plano y no avisa si fallan.
        # Por eso comprobamos una vez, al inicio, que el host responde y las claves sirven.
        conectado = cliente.auth_check()
    except Exception as error:
        _avisar("Langfuse no responde (" + str(error) + ")")
        return None
    if not conectado:
        _avisar("Langfuse rechazó las claves")
        return None
    return cliente


def crear_callbacks(config, cliente):
    """Callbacks para LangChain: registran cada llamada al modelo con sus tokens."""
    if cliente is None:
        return []
    return [CallbackHandler(public_key=config["langfuse_public_key"])]


@contextmanager
def etapa(cliente, nombre, as_type="span", **campos):
    """Abre un span. Si adentro ocurre un error, lo marca como ERROR y lo deja seguir."""
    if cliente is None:
        yield SpanNulo()
        return
    with cliente.start_as_current_observation(name=nombre, as_type=as_type, **campos) as span:
        try:
            yield span
        except Exception as error:
            span.update(level="ERROR", status_message=str(error))
            raise


def tokens_para_langfuse(tokens):
    """Convierte los tokens al formato usage_details que espera Langfuse."""
    return {"input": tokens["input"], "output": tokens["output"], "total": tokens["total"]}


def url_de_traza(cliente):
    """URL de la traza actual, o None. Un problema aquí nunca debe romper el análisis."""
    if cliente is None:
        return None
    try:
        return cliente.get_trace_url()
    except Exception:
        return None
