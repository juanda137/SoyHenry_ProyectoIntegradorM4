"""Pruebas del generador de contratos ficticios y de las imágenes que se entregan."""
import json
from pathlib import Path

from scripts.generar_contratos import generar_todo
from src.image_parser import validar_imagen

CARPETA = Path("data/test_contracts")


def _esperado():
    return json.loads((CARPETA / "esperado.json").read_text(encoding="utf-8"))


def test_genera_cuatro_imagenes_validas(tmp_path):
    rutas = generar_todo(str(tmp_path))
    assert len(rutas) == 4
    assert all(validar_imagen(ruta)["alto"] >= 1600 for ruta in rutas)


def test_generacion_reproducible(tmp_path):
    primera = generar_todo(str(tmp_path / "a"))
    segunda = generar_todo(str(tmp_path / "b"))
    for ruta_a, ruta_b in zip(primera, segunda):
        assert Path(ruta_a).read_bytes() == Path(ruta_b).read_bytes()


def test_cada_par_cubre_los_tres_tipos():
    for par in _esperado().values():
        assert {cambio["tipo"] for cambio in par["cambios"]} == {"ADICIÓN", "ELIMINACIÓN", "MODIFICACIÓN"}
        assert {cambio["seccion"] for cambio in par["cambios"]} == set(par["sections_changed"])


def test_par_2_registra_la_clausula_no_mencionada():
    esperado = _esperado()["par_2"]
    assert esperado["clausula_no_mencionada"] not in esperado["sections_changed"]


def test_las_imagenes_entregadas_existen_y_son_validas():
    nombres = {"par_1_original.png": "PNG", "par_1_adenda.png": "PNG",
               "par_2_original.jpg": "JPEG", "par_2_adenda.jpg": "JPEG"}
    for nombre, formato in nombres.items():
        assert validar_imagen(str(CARPETA / nombre))["formato"] == formato
