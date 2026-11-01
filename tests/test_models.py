"""Pruebas del contrato de salida: no llaman a ninguna API."""
import pytest
from pydantic import ValidationError

from src.models import ContractChangeOutput, describir_error_validacion

VALIDA = {
    "sections_changed": ["Cláusula 3"],
    "topics_touched": ["Pagos"],
    "summary_of_the_change": "MODIFICACIÓN: el plazo pasa de 30 a 45 días.",
}


def test_acepta_salida_valida_y_limpia_listas():
    salida = ContractChangeOutput.model_validate({**VALIDA, "sections_changed": [" Cláusula 3 ", "Cláusula 3", "  "]})
    assert salida.sections_changed == ["Cláusula 3"]


def test_rechaza_campo_extra():
    with pytest.raises(ValidationError):
        ContractChangeOutput.model_validate({**VALIDA, "extra": 1})


@pytest.mark.parametrize("resumen", ["", "   "])
def test_rechaza_resumen_vacio(resumen):
    with pytest.raises(ValidationError):
        ContractChangeOutput.model_validate({**VALIDA, "summary_of_the_change": resumen})


def test_acepta_listas_vacias_si_no_hay_cambios():
    salida = ContractChangeOutput.model_validate({**VALIDA, "sections_changed": [], "topics_touched": []})
    assert salida.sections_changed == []


def test_todos_los_campos_tienen_descripcion():
    assert all(campo.description for campo in ContractChangeOutput.model_fields.values())


def test_tiene_exactamente_los_tres_campos_de_la_consigna():
    assert set(ContractChangeOutput.model_fields) == {"sections_changed", "topics_touched", "summary_of_the_change"}


def test_describir_error_nombra_el_campo():
    with pytest.raises(ValidationError) as info:
        ContractChangeOutput.model_validate({"sections_changed": []})
    assert "topics_touched" in describir_error_validacion(info.value)
