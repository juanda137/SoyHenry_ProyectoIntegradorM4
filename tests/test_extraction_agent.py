"""Pruebas del Agente 2 con un modelo falso."""
import json

import httpx
import openai
import pytest

from src.agents.extraction_agent import SYSTEM_PROMPT, ExtractionAgent
from src.errores import ErrorDeEtapa
from src.models import ContractChangeOutput
from tests.ayudantes import LangfuseFalso, chat_openai_simulado, fallo, llm_estructurado_falso, ok

VALIDA = {"sections_changed": ["Cláusula 3"], "topics_touched": ["Pagos"],
          "summary_of_the_change": "MODIFICACIÓN: plazo de 30 a 45 días."}


def test_recibe_mapa_y_textos_y_valida():
    llm = llm_estructurado_falso([ok(VALIDA)])
    salida = ExtractionAgent(llm).extraer("MAPA_X", "ORIG_X", "ADENDA_X")
    assert isinstance(salida, ContractChangeOutput)
    enviado = str(llm.mensajes[0])
    assert all(texto in enviado for texto in ["MAPA_X", "ORIG_X", "ADENDA_X"])
    assert llm.argumentos == {"esquema": ContractChangeOutput, "include_raw": True}


def test_llaves_en_el_contrato_no_rompen_el_prompt():
    assert ExtractionAgent(llm_estructurado_falso([ok(VALIDA)])).extraer("{m}", "{o}", "{a}")


def test_reintenta_enviando_el_error_al_modelo():
    llm = llm_estructurado_falso([fallo("summary_of_the_change vacío"), ok(VALIDA)])
    ExtractionAgent(llm).extraer("M", "O", "A")
    assert "summary_of_the_change vacío" in str(llm.mensajes[1])


def test_parsed_como_dict_invalido_tambien_se_reintenta():
    llm = llm_estructurado_falso([ok({"sections_changed": 1}), ok(VALIDA)])
    assert ExtractionAgent(llm).extraer("M", "O", "A").topics_touched == ["Pagos"]
    assert "topics_touched" in str(llm.mensajes[1])


def test_acepta_parsed_ya_convertido_a_modelo():
    llm = llm_estructurado_falso([ok(ContractChangeOutput.model_validate(VALIDA))])
    assert ExtractionAgent(llm).extraer("M", "O", "A").sections_changed == ["Cláusula 3"]


def test_sin_parsed_ni_error_es_fallo_de_validacion():
    llm = llm_estructurado_falso([ok(None), ok(VALIDA)])
    ExtractionAgent(llm).extraer("M", "O", "A")
    assert len(llm.mensajes) == 2


def test_agotados_tres_intentos_lanza_error_claro():
    llm = llm_estructurado_falso([fallo("x")] * 3)
    with pytest.raises(ErrorDeEtapa, match="3 intentos") as info:
        ExtractionAgent(llm).extraer("M", "O", "A")
    assert len(llm.mensajes) == 3 and info.value.etapa == "extraction_agent"


def test_error_de_api_no_gasta_reintentos_de_validacion():
    error = openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    llm = llm_estructurado_falso([error])
    with pytest.raises(ErrorDeEtapa):
        ExtractionAgent(llm).extraer("M", "O", "A")
    assert len(llm.mensajes) == 1


def test_cada_intento_queda_en_un_span_validation():
    falso = LangfuseFalso()
    llm = llm_estructurado_falso([fallo("x"), ok(VALIDA)])
    ExtractionAgent(llm, cliente_langfuse=falso).extraer("M", "O", "A")
    assert [span.nombre for span in falso.raices] == ["validation", "validation"]
    assert falso.raices[0].campos["level"] == "ERROR"
    assert falso.raices[1].campos["output"]["sections_changed"] == ["Cláusula 3"]


def test_prompt_define_rol_y_reglas():
    for frase in ["auditor", "ADICIÓN:", "ELIMINACIÓN:", "MODIFICACIÓN:", "[ILEGIBLE]", "datos"]:
        assert frase in SYSTEM_PROMPT


def test_prompt_cubre_adenda_parcial():
    assert "no mencionada" in SYSTEM_PROMPT and "no está eliminada" in SYSTEM_PROMPT


def _json(**cambios):
    return json.dumps({**VALIDA, **cambios}, ensure_ascii=False)


@pytest.mark.parametrize("invalida", [_json(summary_of_the_change="   "), "{json roto", _json(extra=1)])
def test_modelo_real_con_salida_invalida_se_reintenta(invalida):
    llm, pedidos = chat_openai_simulado([invalida, _json()])
    assert ExtractionAgent(llm).extraer("M", "O", "A").topics_touched == ["Pagos"]
    assert len(pedidos) == 2
    assert "no pasó la validación" in json.dumps(pedidos[1], ensure_ascii=False)


def test_modelo_real_agota_los_intentos_con_error_de_etapa():
    llm, pedidos = chat_openai_simulado([_json(summary_of_the_change=" ")] * 3)
    with pytest.raises(ErrorDeEtapa, match="3 intentos"):
        ExtractionAgent(llm).extraer("M", "O", "A")
    assert len(pedidos) == 3


def test_modelo_real_registra_el_fallo_en_el_span_validation():
    falso = LangfuseFalso()
    llm, _ = chat_openai_simulado([_json(summary_of_the_change=" "), _json()])
    ExtractionAgent(llm, cliente_langfuse=falso).extraer("M", "O", "A")
    assert falso.raices[0].campos["level"] == "ERROR"
    assert [span.nombre for span in falso.raices] == ["validation", "validation"]
