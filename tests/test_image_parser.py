"""Pruebas de la lectura de imágenes con un cliente falso: ninguna llama a OpenAI."""
import httpx
import openai
import pytest
from PIL import Image

from src import image_parser
from src.errores import ErrorDeEntrada, ErrorDeEtapa
from src.image_parser import PROMPT_VISION, codificar_base64, parse_contract_image, validar_imagen
from tests.ayudantes import ClienteOpenAIFalso, error_api, respuesta_vision

CONFIG = {"openai_api_key": "sk-prueba", "modelo": "gpt-4o", "timeout_s": 5.0, "max_intentos": 3, "max_tokens": 100}


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(image_parser, "esperar", lambda segundos: None)


def crear(ruta, formato="PNG"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 30), "white").save(ruta, format=formato)
    return str(ruta)


@pytest.fixture
def imagen(tmp_path):
    return crear(tmp_path / "contrato.png")


def timeout():
    return openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))


def test_valida_y_describe_la_imagen(imagen):
    datos = validar_imagen(imagen)
    assert (datos["formato"], datos["mime"], datos["ancho"], datos["alto"]) == ("PNG", "image/png", 20, 30)
    assert datos["bytes"] > 0 and datos["ruta"] == imagen


def test_detecta_png_con_extension_jpg(tmp_path):
    assert validar_imagen(crear(tmp_path / "engaño.jpg", "PNG"))["mime"] == "image/png"


def test_acepta_jpeg(tmp_path):
    assert validar_imagen(crear(tmp_path / "a.jpeg", "JPEG"))["mime"] == "image/jpeg"


def test_ruta_con_espacios_y_tildes_funciona(tmp_path):
    ruta = crear(tmp_path / "carpeta con ñ" / "adenda número 1.png")
    assert validar_imagen(ruta)["formato"] == "PNG"
    assert codificar_base64(ruta)


def test_archivo_inexistente_nombra_la_ruta(tmp_path):
    with pytest.raises(ErrorDeEntrada, match="no_esta.png"):
        validar_imagen(str(tmp_path / "no_esta.png"))


def test_carpeta_no_es_un_archivo(tmp_path):
    with pytest.raises(ErrorDeEntrada):
        validar_imagen(str(tmp_path))


def test_archivo_vacio(tmp_path):
    ruta = tmp_path / "vacio.png"
    ruta.write_bytes(b"")
    with pytest.raises(ErrorDeEntrada, match="vacío"):
        validar_imagen(str(ruta))


def test_mas_de_20_mb_no_gasta_api(imagen, monkeypatch):
    monkeypatch.setattr(image_parser.os.path, "getsize", lambda ruta: 20 * 1024 * 1024 + 1)
    cliente = ClienteOpenAIFalso([])
    with pytest.raises(ErrorDeEntrada, match="20 MB"):
        parse_contract_image(imagen, CONFIG, cliente=cliente)
    assert cliente.llamadas == []


def test_formato_no_permitido(tmp_path):
    with pytest.raises(ErrorDeEntrada, match="JPEG o PNG"):
        validar_imagen(crear(tmp_path / "a.gif", "GIF"))


def test_texto_con_extension_png(tmp_path):
    ruta = tmp_path / "falso.png"
    ruta.write_text("no soy una imagen", encoding="utf-8")
    with pytest.raises(ErrorDeEntrada):
        validar_imagen(str(ruta))


def test_png_truncado(tmp_path):
    ruta = tmp_path / "cortado.png"
    Image.effect_noise((300, 300), 50).convert("RGB").save(ruta)
    ruta.write_bytes(ruta.read_bytes()[: ruta.stat().st_size // 2])
    with pytest.raises(ErrorDeEntrada):
        validar_imagen(str(ruta))


def test_llamada_usa_gpt4o_base64_y_detalle_alto(imagen):
    cliente = ClienteOpenAIFalso([respuesta_vision("CLÁUSULA 1")])
    resultado = parse_contract_image(imagen, CONFIG, cliente=cliente)
    kw = cliente.llamadas[0]
    assert kw["model"] == "gpt-4o" and kw["temperature"] == 0 and kw["max_tokens"] == 100
    url = kw["messages"][1]["content"][1]["image_url"]
    assert url["detail"] == "high" and url["url"].startswith("data:image/png;base64,")
    assert resultado["texto"] == "CLÁUSULA 1" and resultado["intentos"] == 1
    assert resultado["tokens"] == {"input": 10, "output": 5, "total": 15}
    assert resultado["modelo"] == "gpt-4o" and resultado["imagen"]["formato"] == "PNG"


def test_prompt_exige_fidelidad():
    for frase in ["jerarquía", "[ILEGIBLE]", "SIN_TEXTO_LEGIBLE", "instrucciones"]:
        assert frase in PROMPT_VISION


def test_reintenta_timeout_y_cuenta_intentos(imagen):
    cliente = ClienteOpenAIFalso([timeout(), respuesta_vision("texto")])
    assert parse_contract_image(imagen, CONFIG, cliente=cliente)["intentos"] == 2


def test_agota_reintentos_nombra_la_etapa(imagen):
    cliente = ClienteOpenAIFalso([timeout(), timeout(), timeout()])
    with pytest.raises(ErrorDeEtapa) as info:
        parse_contract_image(imagen, CONFIG, cliente=cliente)
    assert len(cliente.llamadas) == 3 and info.value.etapa == "parse_contract_image"


@pytest.mark.parametrize("clase, status", [(openai.AuthenticationError, 401), (openai.BadRequestError, 400)])
def test_errores_definitivos_no_se_reintentan(imagen, clase, status):
    cliente = ClienteOpenAIFalso([error_api(clase, status)])
    with pytest.raises(ErrorDeEtapa):
        parse_contract_image(imagen, CONFIG, cliente=cliente)
    assert len(cliente.llamadas) == 1


def test_limite_de_uso_si_se_reintenta(imagen):
    cliente = ClienteOpenAIFalso([error_api(openai.RateLimitError, 429, "rate_limit_exceeded"), respuesta_vision("t")])
    assert parse_contract_image(imagen, CONFIG, cliente=cliente)["intentos"] == 2


def test_cuota_agotada_no_reintenta_y_lo_explica(imagen):
    cliente = ClienteOpenAIFalso([error_api(openai.RateLimitError, 429, "insufficient_quota")])
    with pytest.raises(ErrorDeEtapa, match="saldo"):
        parse_contract_image(imagen, CONFIG, cliente=cliente)
    assert len(cliente.llamadas) == 1


@pytest.mark.parametrize("respuesta", [
    respuesta_vision(""),
    respuesta_vision("   "),
    respuesta_vision("parcial", finish_reason="length"),
    respuesta_vision(None, refusal="No puedo"),
    respuesta_vision("SIN_TEXTO_LEGIBLE"),
])
def test_respuestas_inutiles_son_error(imagen, respuesta):
    cliente = ClienteOpenAIFalso([respuesta])
    with pytest.raises(ErrorDeEtapa):
        parse_contract_image(imagen, CONFIG, cliente=cliente)
    assert len(cliente.llamadas) == 1


def test_imagen_descomunal_es_error_de_entrada(imagen, monkeypatch):
    monkeypatch.setattr(image_parser.Image, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ErrorDeEntrada):
        validar_imagen(imagen)


def test_acepta_jpeg_de_celular_con_varias_imagenes(tmp_path):
    ruta = tmp_path / "foto.jpg"
    primera = Image.new("RGB", (20, 30), "white")
    primera.save(ruta, format="MPO", save_all=True, append_images=[Image.new("RGB", (20, 30), "gray")])
    datos = validar_imagen(str(ruta))
    assert (datos["formato"], datos["mime"]) == ("JPEG", "image/jpeg")


def test_prompt_rechaza_lo_que_no_es_un_contrato():
    assert "no es un contrato" in PROMPT_VISION


@pytest.mark.parametrize("texto", [
    "SIN_TEXTO_LEGIBLE.",
    "Respuesta: SIN_TEXTO_LEGIBLE",
    "Lo siento, no puedo ayudar con esa imagen.",
    "I'm sorry, I can't help with that.",
])
def test_negativas_escritas_como_texto_son_error(imagen, texto):
    with pytest.raises(ErrorDeEtapa):
        parse_contract_image(imagen, CONFIG, cliente=ClienteOpenAIFalso([respuesta_vision(texto)]))
