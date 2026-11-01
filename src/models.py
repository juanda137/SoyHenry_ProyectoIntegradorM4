"""El contrato de salida del sistema: lo que reciben los demás sistemas de la empresa.

El modelo garantiza la forma del JSON; Pydantic comprueba además que tenga sentido
(sin campos inventados y sin un resumen vacío).
"""
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractChangeOutput(BaseModel):
    """Cambios que introduce una adenda respecto del contrato original."""

    # extra="forbid": un campo que no está en la consigna es un error, no se ignora.
    model_config = ConfigDict(extra="forbid")

    sections_changed: List[str] = Field(
        description="Identificadores de las secciones modificadas, tal como aparecen en el documento."
    )
    topics_touched: List[str] = Field(
        description="Categorías legales o comerciales afectadas, por ejemplo Pagos o Vigencia."
    )
    summary_of_the_change: str = Field(
        description="Descripción detallada de los cambios, con las etiquetas ADICIÓN:, ELIMINACIÓN: y MODIFICACIÓN:."
    )

    @field_validator("sections_changed", "topics_touched")
    @classmethod
    def limpiar_lista(cls, valores):
        """Quita espacios, cadenas vacías y duplicados, conservando el orden."""
        limpios = []
        for valor in valores:
            texto = valor.strip()
            if texto != "" and texto not in limpios:
                limpios.append(texto)
        return limpios

    @field_validator("summary_of_the_change")
    @classmethod
    def resumen_con_contenido(cls, valor):
        """Un resumen vacío no informa nada, ni siquiera que no hubo cambios."""
        texto = valor.strip()
        if texto == "":
            raise ValueError("el resumen no puede estar vacío")
        return texto


def describir_error_validacion(error):
    """Convierte un ValidationError en una frase por campo, fácil de leer."""
    partes = []
    for detalle in error.errors():
        campo = ".".join(str(parte) for parte in detalle["loc"]) or "(salida completa)"
        partes.append(campo + ": " + detalle["msg"])
    return "; ".join(partes)
