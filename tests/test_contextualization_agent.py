"""Pruebas del Agente 1 con un modelo falso."""
import httpx
import openai
import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage

from src.agents.contextualization_agent import SYSTEM_PROMPT, ContextualizationAgent
from src.errores import ErrorDeEtapa
from tests.ayudantes import llm_falso


def test_devuelve_el_mapa_y_recibe_ambos_textos():
    llm = llm_falso([AIMessage(content="MAPA")])
    assert ContextualizationAgent(llm).analizar("TEXTO_A", "TEXTO_B") == "MAPA"
    enviado = str(llm.mensajes[0])
    assert "TEXTO_A" in enviado and "TEXTO_B" in enviado


def test_llaves_en_el_contrato_no_rompen_el_prompt():
    llm = llm_falso([AIMessage(content="M")])
    assert ContextualizationAgent(llm).analizar("{monto}", "{x}") == "M"


def test_prompt_define_rol_y_prohibe_describir_cambios():
    for frase in ["analista legal senior", "correspondencia", "propósito", "No describas cambios", "datos"]:
        assert frase in SYSTEM_PROMPT


def test_prompt_pide_indicar_el_tipo_de_adenda():
    assert "solo enumera" in SYSTEM_PROMPT


def test_mapa_vacio_es_error():
    with pytest.raises(ErrorDeEtapa):
        ContextualizationAgent(llm_falso([AIMessage(content="   ")])).analizar("a", "b")


def test_truncado_es_error():
    mensaje = AIMessage(content="mapa a medias", response_metadata={"finish_reason": "length"})
    with pytest.raises(ErrorDeEtapa, match="cortado"):
        ContextualizationAgent(llm_falso([mensaje])).analizar("a", "b")


def test_error_de_api_nombra_la_etapa():
    error = openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(ErrorDeEtapa) as info:
        ContextualizationAgent(llm_falso([error])).analizar("a", "b")
    assert info.value.etapa == "contextualization_agent"


def test_pasa_callbacks_a_la_llamada():
    class Registro(BaseCallbackHandler):
        pass

    callback = Registro()
    llm = llm_falso([AIMessage(content="M")])
    ContextualizationAgent(llm).analizar("a", "b", callbacks=[callback])
    assert callback in llm.configs[0]["callbacks"].handlers
