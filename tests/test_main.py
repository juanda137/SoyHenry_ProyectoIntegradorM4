"""Pruebas del pipeline completo con dobles: no hay llamadas a OpenAI ni a Langfuse."""
import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from PIL import Image

from src import main as modulo_main
from src.errores import ErrorDeConfiguracion
from src.main import configurar_salida_utf8, ejecutar_pipeline, main
from tests.ayudantes import ClienteOpenAIFalso, LangfuseFalso, chat_openai_simulado, respuesta_vision

CONFIG = {"openai_api_key": "sk-prueba", "modelo": "gpt-4o", "timeout_s": 5.0, "max_intentos": 3, "max_tokens": 100,
          "langfuse_public_key": "", "langfuse_secret_key": "", "langfuse_host": ""}
VALIDA = {"sections_changed": ["Cláusula 3"], "topics_touched": ["Pagos"],
          "summary_of_the_change": "MODIFICACIÓN: plazo de 30 a 45 días."}


class LLMDePrueba(RunnableLambda):
    """Sirve a los dos agentes: texto para el primero y JSON estructurado para el segundo."""

    def __init__(self, mapa="MAPA_DEL_AGENTE_1"):
        self.mapa = mapa
        self.mensajes_agente_2 = []
        self.llamadas_agente_1 = 0
        super().__init__(self._responder_agente_1)

    def _responder_agente_1(self, entrada):
        self.llamadas_agente_1 += 1
        return AIMessage(content=self.mapa)

    def with_structured_output(self, esquema, include_raw=False):
        return RunnableLambda(self._responder_agente_2)

    def _responder_agente_2(self, entrada):
        self.mensajes_agente_2.append(entrada)
        return {"raw": AIMessage(content=""), "parsed": VALIDA, "parsing_error": None}


def vision_ok():
    return ClienteOpenAIFalso([respuesta_vision("TEXTO ORIGINAL"), respuesta_vision("TEXTO ADENDA")])


@pytest.fixture
def rutas(tmp_path):
    original, adenda = tmp_path / "original.png", tmp_path / "adenda.png"
    Image.new("RGB", (20, 30), "white").save(original)
    Image.new("RGB", (20, 30), "gray").save(adenda)
    return str(original), str(adenda)


@pytest.fixture
def con_dobles(monkeypatch):
    """Reemplaza lo que main() crearía de verdad. Devuelve el Langfuse falso."""
    falso = LangfuseFalso()
    monkeypatch.setattr(modulo_main, "cargar_configuracion", lambda: CONFIG)
    monkeypatch.setattr(modulo_main, "crear_cliente_langfuse", lambda config: falso)
    monkeypatch.setattr(modulo_main, "crear_callbacks", lambda config, cliente: [])
    monkeypatch.setattr(modulo_main, "crear_llm", lambda config: LLMDePrueba())
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: vision_ok())
    return falso


def test_jerarquia_de_spans_completa(rutas):
    falso = LangfuseFalso()
    ejecutar_pipeline(*rutas, CONFIG, cliente_langfuse=falso, cliente_openai=vision_ok(), llm=LLMDePrueba())
    raiz = falso.raices[0]
    assert raiz.nombre == "contract-analysis"
    assert [hijo.nombre for hijo in raiz.hijos] == [
        "parse_original_contract", "parse_amendment_contract", "contextualization_agent", "extraction_agent"]
    assert raiz.hijos[3].hijos[0].nombre == "validation"
    assert raiz.hijos[0].as_type == "generation"
    assert raiz.hijos[0].campos["usage_details"]["total"] > 0
    assert raiz.hijos[0].campos["model"] == "gpt-4o"
    assert raiz.hijos[0].campos["metadata"]["intentos"] == 1
    assert raiz.hijos[0].campos["output"] == "TEXTO ORIGINAL"
    assert raiz.hijos[2].campos["output"] == "MAPA_DEL_AGENTE_1"
    assert raiz.campos["output"]["sections_changed"] == ["Cláusula 3"]


def test_base64_nunca_llega_a_langfuse(rutas):
    falso = LangfuseFalso()
    ejecutar_pipeline(*rutas, CONFIG, cliente_langfuse=falso, cliente_openai=vision_ok(), llm=LLMDePrueba())
    assert "base64," not in repr(falso.raices)


def test_el_mapa_pasa_del_agente_1_al_agente_2(rutas):
    llm = LLMDePrueba()
    ejecutar_pipeline(*rutas, CONFIG, cliente_openai=vision_ok(), llm=llm)
    enviado = str(llm.mensajes_agente_2[0])
    assert all(texto in enviado for texto in ["MAPA_DEL_AGENTE_1", "TEXTO ORIGINAL", "TEXTO ADENDA"])


def test_fallo_de_etapa_marca_error_y_no_ejecuta_las_siguientes(rutas):
    falso = LangfuseFalso()
    llm = LLMDePrueba()
    vision = ClienteOpenAIFalso([respuesta_vision("")])
    with pytest.raises(Exception):
        ejecutar_pipeline(*rutas, CONFIG, cliente_langfuse=falso, cliente_openai=vision, llm=llm)
    assert llm.llamadas_agente_1 == 0
    assert falso.raices[0].campos["level"] == "ERROR"
    assert falso.raices[0].hijos[0].campos["level"] == "ERROR"


def test_valida_las_dos_imagenes_antes_de_gastar_api(rutas, tmp_path, capsys, con_dobles, monkeypatch):
    vision = vision_ok()
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: vision)
    assert main([rutas[0], str(tmp_path / "no_esta.png")]) == 2
    assert vision.llamadas == []


def test_exito_stdout_es_solo_json(rutas, capsys, con_dobles):
    assert main(list(rutas)) == 0
    assert set(json.loads(capsys.readouterr().out)) == {"sections_changed", "topics_touched", "summary_of_the_change"}


def test_archivo_faltante_sale_2_sin_json(capsys):
    assert main(["no_esta_a.png", "no_esta_b.png"]) == 2
    salida = capsys.readouterr()
    assert salida.out == "" and "no_esta_a.png" in salida.err


def test_falta_clave_sale_2_sin_json(rutas, capsys, monkeypatch):
    def sin_clave():
        raise ErrorDeConfiguracion("Falta OPENAI_API_KEY")

    monkeypatch.setattr(modulo_main, "cargar_configuracion", sin_clave)
    assert main(list(rutas)) == 2
    salida = capsys.readouterr()
    assert salida.out == "" and "OPENAI_API_KEY" in salida.err


def test_fallo_de_proceso_sale_1_sin_json(rutas, capsys, con_dobles, monkeypatch):
    monkeypatch.setattr(modulo_main, "crear_cliente_openai",
                        lambda config: ClienteOpenAIFalso([respuesta_vision("SIN_TEXTO_LEGIBLE")]))
    assert main(list(rutas)) == 1
    salida = capsys.readouterr()
    assert salida.out == "" and "parse_contract_image" in salida.err


def test_flush_ocurre_tambien_si_falla(rutas, con_dobles, monkeypatch):
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: ClienteOpenAIFalso([respuesta_vision("")]))
    main(list(rutas))
    assert con_dobles.flushes == 1


def test_url_de_traza_va_a_stderr(rutas, capsys, con_dobles):
    main(list(rutas))
    salida = capsys.readouterr()
    assert "https://langfuse.falso/traza" in salida.err and "https://" not in salida.out


def test_url_de_traza_tambien_sale_si_falla(rutas, capsys, con_dobles, monkeypatch):
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: ClienteOpenAIFalso([respuesta_vision("")]))
    assert main(list(rutas)) == 1
    assert "https://langfuse.falso/traza" in capsys.readouterr().err


def test_ilegible_genera_aviso(rutas, capsys, con_dobles, monkeypatch):
    vision = ClienteOpenAIFalso([respuesta_vision("a [ILEGIBLE] b [ILEGIBLE]"), respuesta_vision("c")])
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: vision)
    assert main(list(rutas)) == 0
    assert "2 partes ilegibles" in capsys.readouterr().err


def test_mismo_archivo_dos_veces_avisa_y_sigue(rutas, capsys, con_dobles):
    assert main([rutas[0], rutas[0]]) == 0
    assert "mismo archivo" in capsys.readouterr().err


def test_mismo_contenido_con_otro_nombre_tambien_avisa(rutas, tmp_path, capsys, con_dobles):
    copia = tmp_path / "copia.png"
    copia.write_bytes(open(rutas[0], "rb").read())
    assert main([rutas[0], str(copia)]) == 0
    assert "mismo archivo" in capsys.readouterr().err


def test_acentos_no_rompen_con_salida_cp1252(monkeypatch):
    buffer = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buffer, encoding="cp1252"))
    configurar_salida_utf8()
    print("Cláusula ñ →")
    sys.stdout.flush()
    assert "Cláusula ñ →".encode("utf-8") in buffer.getvalue()


@pytest.mark.parametrize("comando", [["src/main.py"], ["-m", "src.main"]])
def test_ambas_formas_de_ejecutar(comando):
    resultado = subprocess.run([sys.executable, *comando, "no_existe_a.png", "no_existe_b.png"],
                               capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 2 and "no_existe_a.png" in resultado.stderr and resultado.stdout == ""


def test_validacion_agotada_con_modelo_real_sale_1_sin_json(rutas, capsys, con_dobles, monkeypatch):
    invalida = json.dumps({**VALIDA, "summary_of_the_change": "  "})
    llm, pedidos = chat_openai_simulado(["MAPA", invalida, invalida, invalida])
    monkeypatch.setattr(modulo_main, "crear_llm", lambda config: llm)
    assert main(list(rutas)) == 1
    salida = capsys.readouterr()
    assert salida.out == "" and "3 intentos" in salida.err and len(pedidos) == 4


def test_excepcion_inesperada_sale_1_sin_traceback(rutas, capsys, con_dobles, monkeypatch):
    rota = SimpleNamespace(choices=None, usage=None, model="gpt-4o")
    monkeypatch.setattr(modulo_main, "crear_cliente_openai", lambda config: ClienteOpenAIFalso([rota]))
    assert main(list(rutas)) == 1
    salida = capsys.readouterr()
    assert salida.out == "" and "Error" in salida.err


def test_fallo_de_flush_no_pierde_el_json(rutas, capsys, con_dobles, monkeypatch):
    def falla():
        raise RuntimeError("sin red")

    monkeypatch.setattr(con_dobles, "flush", falla)
    assert main(list(rutas)) == 0
    salida = capsys.readouterr()
    assert json.loads(salida.out)["topics_touched"] == ["Pagos"] and "sin red" in salida.err
