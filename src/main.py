"""Entrada del programa: compara un contrato con su adenda y devuelve un JSON validado.

Uso:
    python src/main.py data/test_contracts/par_1_original.png data/test_contracts/par_1_adenda.png

Stdout lleva solo el JSON, para poder redirigirlo. Los avisos y errores van por stderr.
Códigos de salida: 0 éxito, 2 entrada o configuración inválida, 1 fallo durante el proceso.
"""
import argparse
import os
import sys

# "python src/main.py" no incluye la raíz del proyecto en la ruta de imports.
# Este ajuste permite que los imports "src.x" funcionen también con esa forma.
if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openai  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from src.agents.contextualization_agent import ContextualizationAgent  # noqa: E402
from src.agents.extraction_agent import ExtractionAgent  # noqa: E402
from src.config import cargar_configuracion  # noqa: E402
from src.errores import ErrorDeConfiguracion, ErrorDeEntrada, ErrorDeEtapa  # noqa: E402
from src.image_parser import parse_contract_image, validar_imagen  # noqa: E402
from src.observabilidad import (crear_callbacks, crear_cliente_langfuse, etapa,  # noqa: E402
                                tokens_para_langfuse, url_de_traza)

MARCA_ILEGIBLE = "[ILEGIBLE]"


def configurar_salida_utf8():
    """En Windows la consola o una redirección pueden usar cp1252, que no admite todos los caracteres."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def crear_cliente_openai(config):
    # max_retries=0: image_parser cuenta sus propios reintentos.
    return openai.OpenAI(api_key=config["openai_api_key"], timeout=config["timeout_s"], max_retries=0)


def crear_llm(config):
    """El modelo que usan los dos agentes; temperatura 0 para que el análisis sea estable."""
    return ChatOpenAI(model=config["modelo"], api_key=config["openai_api_key"], temperature=0,
                      timeout=config["timeout_s"], max_retries=config["max_intentos"] - 1,
                      max_tokens=config["max_tokens"])


def _leer_documento(cliente_langfuse, nombre_span, ruta, config, cliente_openai):
    """Lee una imagen dentro de su span y devuelve el texto. Avisa si quedaron partes ilegibles."""
    with etapa(cliente_langfuse, nombre_span, as_type="generation", input={"ruta": ruta}) as span:
        leido = parse_contract_image(ruta, config, cliente=cliente_openai)
        # La imagen en base64 no se envía a Langfuse: pesa mucho y es contenido legal.
        span.update(output=leido["texto"], model=leido["modelo"],
                    usage_details=tokens_para_langfuse(leido["tokens"]),
                    metadata={"intentos": leido["intentos"], "imagen": leido["imagen"]})
    cantidad = leido["texto"].count(MARCA_ILEGIBLE)
    if cantidad > 0:
        print("[aviso] " + ruta + " tiene " + str(cantidad) + " partes ilegibles: revisa el resultado.",
              file=sys.stderr)
    return leido["texto"]


def ejecutar_pipeline(ruta_original, ruta_adenda, config, cliente_langfuse=None, callbacks=None,
                      cliente_openai=None, llm=None):
    """Ejecuta las 4 etapas en orden, dentro de una sola traza, y devuelve el ContractChangeOutput."""
    cliente_openai = cliente_openai or crear_cliente_openai(config)
    llm = llm or crear_llm(config)
    entrada = {"contrato_original": ruta_original, "adenda": ruta_adenda}
    with etapa(cliente_langfuse, "contract-analysis", input=entrada) as raiz:
        texto_original = _leer_documento(cliente_langfuse, "parse_original_contract", ruta_original,
                                         config, cliente_openai)
        texto_adenda = _leer_documento(cliente_langfuse, "parse_amendment_contract", ruta_adenda,
                                       config, cliente_openai)
        textos = {"texto_original": texto_original, "texto_adenda": texto_adenda}
        with etapa(cliente_langfuse, "contextualization_agent", input=textos) as span:
            mapa = ContextualizationAgent(llm).analizar(texto_original, texto_adenda, callbacks=callbacks)
            span.update(output=mapa)
        with etapa(cliente_langfuse, "extraction_agent", input={"mapa": mapa, **textos}) as span:
            agente = ExtractionAgent(llm, cliente_langfuse=cliente_langfuse)
            salida = agente.extraer(mapa, texto_original, texto_adenda, callbacks=callbacks)
            span.update(output=salida.model_dump())
        raiz.update(output=salida.model_dump())
    return salida


def _son_el_mismo_contenido(ruta_a, ruta_b):
    with open(ruta_a, "rb") as archivo_a, open(ruta_b, "rb") as archivo_b:
        return archivo_a.read() == archivo_b.read()


def _crear_parser():
    parser = argparse.ArgumentParser(description="Compara un contrato con su adenda a partir de imágenes.")
    parser.add_argument("original", help="imagen JPEG o PNG del contrato original")
    parser.add_argument("adenda", help="imagen JPEG o PNG de la adenda")
    return parser


def main(argv=None):
    configurar_salida_utf8()
    args = _crear_parser().parse_args(argv)
    cliente_langfuse = None
    try:
        # Primero lo que se puede comprobar gratis: así un error no gasta API.
        validar_imagen(args.original)
        validar_imagen(args.adenda)
        if _son_el_mismo_contenido(args.original, args.adenda):
            print("[aviso] Ambas rutas tienen el mismo archivo: no se esperan cambios.", file=sys.stderr)
        config = cargar_configuracion()
        cliente_langfuse = crear_cliente_langfuse(config)
        salida = ejecutar_pipeline(
            args.original, args.adenda, config, cliente_langfuse=cliente_langfuse,
            callbacks=crear_callbacks(config, cliente_langfuse),
            cliente_openai=crear_cliente_openai(config), llm=crear_llm(config),
        )
    except (ErrorDeEntrada, ErrorDeConfiguracion) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2
    except ErrorDeEtapa as error:
        # Sin JSON: una salida vacía se confundiría con "no hubo cambios".
        print("Error en " + str(error), file=sys.stderr)
        return 1
    finally:
        # Envía la traza aunque algo haya fallado.
        if cliente_langfuse is not None:
            cliente_langfuse.flush()
    print(salida.model_dump_json(indent=2))
    url = url_de_traza(cliente_langfuse)
    if url:
        print("Traza en Langfuse: " + url, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
