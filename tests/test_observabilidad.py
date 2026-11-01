"""Pruebas de los spans con un Langfuse falso: nada sale a la red."""
import pytest

from src import observabilidad
from src.observabilidad import crear_callbacks, crear_cliente_langfuse, etapa, tokens_para_langfuse, url_de_traza
from tests.ayudantes import LangfuseFalso

CONFIG = {"langfuse_public_key": "pk-real", "langfuse_secret_key": "sk-real", "langfuse_host": "https://x"}


def test_sin_claves_devuelve_none_y_avisa(capsys):
    assert crear_cliente_langfuse({**CONFIG, "langfuse_public_key": ""}) is None
    assert "sin trazas" in capsys.readouterr().err


def test_claves_de_ejemplo_devuelven_none():
    assert crear_cliente_langfuse({**CONFIG, "langfuse_public_key": "pk-lf-xxx", "langfuse_secret_key": "sk-lf-xxx"}) is None


def _sdk_que_dice(respuesta):
    class SDK:
        def __init__(self, **kwargs):
            pass

        def auth_check(self):
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta

    return SDK


@pytest.mark.parametrize("respuesta", [False, RuntimeError("sin red")])
def test_auth_check_que_falla_devuelve_none(monkeypatch, capsys, respuesta):
    monkeypatch.setattr(observabilidad, "Langfuse", _sdk_que_dice(respuesta))
    assert crear_cliente_langfuse(CONFIG) is None
    assert "sin trazas" in capsys.readouterr().err


def test_auth_check_correcto_devuelve_cliente(monkeypatch):
    monkeypatch.setattr(observabilidad, "Langfuse", _sdk_que_dice(True))
    assert crear_cliente_langfuse(CONFIG) is not None


def test_sin_cliente_no_hay_callbacks():
    assert crear_callbacks(CONFIG, None) == []


def test_con_cliente_hay_un_callback(monkeypatch):
    monkeypatch.setattr(observabilidad, "CallbackHandler", lambda public_key: "handler:" + public_key)
    assert crear_callbacks(CONFIG, object()) == ["handler:pk-real"]


def test_etapa_sin_cliente_no_falla():
    with etapa(None, "x") as span:
        span.update(output=1)


def test_etapa_sin_cliente_deja_pasar_errores():
    with pytest.raises(ValueError):
        with etapa(None, "x"):
            raise ValueError("boom")


def test_etapa_anida_spans():
    falso = LangfuseFalso()
    with etapa(falso, "padre", input={"a": 1}):
        with etapa(falso, "hijo", as_type="generation"):
            pass
    raiz = falso.raices[0]
    assert raiz.nombre == "padre" and raiz.campos["input"] == {"a": 1}
    assert raiz.hijos[0].nombre == "hijo" and raiz.hijos[0].as_type == "generation"


def test_error_marca_el_span_y_se_relanza():
    falso = LangfuseFalso()
    with pytest.raises(ValueError):
        with etapa(falso, "x"):
            raise ValueError("boom")
    assert falso.raices[0].campos["level"] == "ERROR"
    assert "boom" in falso.raices[0].campos["status_message"]


def test_tokens_para_langfuse():
    assert tokens_para_langfuse({"input": 1, "output": 2, "total": 3}) == {"input": 1, "output": 2, "total": 3}


def test_url_de_traza():
    assert url_de_traza(LangfuseFalso()) == "https://langfuse.falso/traza"
    assert url_de_traza(None) is None


def test_url_de_traza_no_lanza_si_el_sdk_falla():
    class Roto:
        def get_trace_url(self):
            raise RuntimeError("sin red")

    assert url_de_traza(Roto()) is None
