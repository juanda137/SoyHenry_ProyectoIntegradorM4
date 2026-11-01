"""Errores propios del proyecto.

Separarlos permite a main.py decidir el código de salida:
  * ErrorDeEntrada y ErrorDeConfiguracion -> salida 2 (se arregla sin gastar API).
  * ErrorDeEtapa -> salida 1 (algo falló mientras se procesaba).
"""


class ErrorDeEntrada(Exception):
    """El archivo que pasó el usuario no se puede usar."""


class ErrorDeConfiguracion(Exception):
    """Falta una variable de entorno o tiene un valor inválido."""


class ErrorDeEtapa(Exception):
    """Falló una etapa del pipeline; .etapa dice cuál para que el mensaje sea claro."""

    def __init__(self, etapa, mensaje):
        super().__init__(etapa + ": " + mensaje)
        self.etapa = etapa
