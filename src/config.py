"""Lee la configuración desde variables de entorno (.env) y la valida una sola vez."""
import os

from dotenv import load_dotenv

from src.errores import ErrorDeConfiguracion

CLAVE_DE_EJEMPLO = "your-key-here"


def _leer_numero(variable, por_defecto, convertir):
    """Convierte una variable a número positivo; si no se puede, explica cuál está mal."""
    texto = os.getenv(variable, "").strip()
    if texto == "":
        return por_defecto
    try:
        valor = convertir(texto)
    except ValueError:
        raise ErrorDeConfiguracion(variable + " debe ser un número; llegó: " + texto) from None
    if valor <= 0:
        raise ErrorDeConfiguracion(variable + " debe ser mayor que 0; llegó: " + texto)
    return valor


def cargar_configuracion():
    """Devuelve un dict con la configuración. Lanza ErrorDeConfiguracion si algo falta."""
    load_dotenv()
    clave = os.getenv("OPENAI_API_KEY", "").strip()
    if clave == "" or clave == CLAVE_DE_EJEMPLO:
        raise ErrorDeConfiguracion("Falta OPENAI_API_KEY: copia .env.example como .env y agrega tu clave.")
    return {
        "openai_api_key": clave,
        "modelo": os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o",
        "timeout_s": _leer_numero("OPENAI_TIMEOUT", 120.0, float),
        "max_intentos": _leer_numero("OPENAI_MAX_ATTEMPTS", 3, int),
        "max_tokens": _leer_numero("OPENAI_MAX_TOKENS", 4096, int),
        "langfuse_public_key": os.getenv("LANGFUSE_PUBLIC_KEY", "").strip(),
        "langfuse_secret_key": os.getenv("LANGFUSE_SECRET_KEY", "").strip(),
        "langfuse_host": os.getenv("LANGFUSE_HOST", "").strip() or "https://cloud.langfuse.com",
    }
