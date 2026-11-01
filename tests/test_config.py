"""Pruebas de configuración: anulan load_dotenv para no leer un .env real."""
import pytest

from src import config
from src.config import cargar_configuracion
from src.errores import ErrorDeConfiguracion, ErrorDeEtapa

VARIABLES = ["OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_TIMEOUT", "OPENAI_MAX_ATTEMPTS", "OPENAI_MAX_TOKENS",
             "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: False)
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_falta_clave_openai_pide_copiar_env_example():
    with pytest.raises(ErrorDeConfiguracion, match=r"\.env\.example"):
        cargar_configuracion()


def test_clave_de_ejemplo_cuenta_como_faltante(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "your-key-here")
    with pytest.raises(ErrorDeConfiguracion):
        cargar_configuracion()


def test_valores_por_defecto(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    c = cargar_configuracion()
    assert (c["modelo"], c["timeout_s"], c["max_intentos"], c["max_tokens"]) == ("gpt-4o", 120.0, 3, 4096)


@pytest.mark.parametrize("variable, valor", [("OPENAI_TIMEOUT", "abc"), ("OPENAI_MAX_ATTEMPTS", "0"), ("OPENAI_MAX_TOKENS", "-1")])
def test_numero_invalido_es_error_de_configuracion(monkeypatch, variable, valor):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ErrorDeConfiguracion, match=variable):
        cargar_configuracion()


def test_error_de_etapa_guarda_la_etapa():
    error = ErrorDeEtapa("extraction_agent", "falló")
    assert error.etapa == "extraction_agent" and "extraction_agent" in str(error) and "falló" in str(error)
