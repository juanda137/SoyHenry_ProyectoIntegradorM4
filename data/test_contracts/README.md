# Contratos de prueba

Son 2 pares de contratos **ficticios**: las empresas, los números de contrato y los montos son inventados. Como los escribimos nosotros, los cambios correctos se conocen de antemano y están en `esperado.json`.

Para regenerarlos, desde la raíz del proyecto:

```bash
python scripts/generar_contratos.py
```

## Par 1: servicios de software (`par_1_original.png`, `par_1_adenda.png`)

Es un escaneo limpio. La adenda **reformula todo el contrato**, así que una cláusula ausente sí está eliminada.

| Tipo | Sección | Cambio esperado |
|---|---|---|
| MODIFICACIÓN | Cláusula 2 | El precio pasa de USD 2.000 a USD 2.400 mensuales |
| MODIFICACIÓN | Cláusula 3 | El plazo de pago pasa de 30 a 45 días calendario |
| ELIMINACIÓN | Cláusula 6 | Se quita la penalidad por demora de USD 50 diarios |
| ADICIÓN | Cláusula 9 | Se agrega el tratamiento de datos personales |

## Par 2: arrendamiento de local (`par_2_original.jpg`, `par_2_adenda.jpg`)

Tiene ruido de escaneo: leve rotación, desenfoque y grano. La adenda **solo enumera las cláusulas que cambian**, así que lo no mencionado sigue vigente.

| Tipo | Sección | Cambio esperado |
|---|---|---|
| MODIFICACIÓN | Cláusula 2 | El canon pasa de USD 1.500 a USD 1.650 mensuales |
| ELIMINACIÓN | Cláusula 6 | Se quita el depósito de garantía de USD 3.000 |
| ADICIÓN | Cláusula 9 | Se agrega un seguro contra incendio por USD 50.000 |

**Trampa intencional:** la Cláusula 7 (y las demás no mencionadas) no aparece en la adenda, pero no está eliminada. Si el sistema la reporta como eliminación, es un error.
