"""Genera 2 pares de contratos ficticios como imágenes, con sus cambios esperados.

Como escribimos los contratos nosotros, sabemos de antemano qué cambió. Eso permite medir
si el sistema detecta los cambios correctos.

Uso: python scripts/generar_contratos.py
"""
import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ANCHO, ALTO = 1700, 2200
MARGEN = 130
SEMILLA = 2026
CARPETA_POR_DEFECTO = os.path.join("data", "test_contracts")

PARTES_1 = ("NubeAndina Software S.A.S. (Proveedor, empresa ficticia) y Panadería La Espiga Imaginaria Ltda. "
            "(Cliente, empresa ficticia)")
OBJETO_1 = "El Proveedor presta al Cliente el servicio mensual de facturación en línea y soporte técnico."
LEY_1 = "Este contrato se rige por las leyes de la República de Colombia."

PAR_1_ORIGINAL = [
    ("CONTRATO DE PRESTACIÓN DE SERVICIOS N.º LM-2026-014", ""),
    ("PARTES", PARTES_1),
    ("Cláusula 1. Objeto", OBJETO_1),
    ("Cláusula 2. Precio", "El Cliente pagará USD 2.000 mensuales, más impuestos."),
    ("Cláusula 3. Plazo de pago", "Cada factura se paga dentro de los 30 días calendario siguientes a su emisión."),
    ("Cláusula 4. Vigencia", "El contrato dura 12 meses a partir del 1 de febrero de 2026."),
    ("Cláusula 5. Confidencialidad", "Las partes guardarán reserva de la información recibida durante 3 años."),
    ("Cláusula 6. Penalidad por demora", "Cada día de atraso en el soporte genera una penalidad de USD 50 a cargo del Proveedor."),
    ("Cláusula 7. Terminación", "Cualquiera de las partes puede terminar el contrato con un aviso escrito de 60 días."),
    ("Cláusula 8. Ley aplicable", LEY_1),
]

# Esta adenda reformula el contrato completo: una cláusula ausente sí está eliminada.
PAR_1_ADENDA = [
    ("ADENDA N.º 1: TEXTO COMPLETO DEL CONTRATO N.º LM-2026-014", ""),
    ("PARTES", PARTES_1),
    ("Cláusula 1. Objeto", OBJETO_1),
    ("Cláusula 2. Precio", "El Cliente pagará USD 2.400 mensuales, más impuestos."),
    ("Cláusula 3. Plazo de pago", "Cada factura se paga dentro de los 45 días calendario siguientes a su emisión."),
    ("Cláusula 4. Vigencia", "El contrato dura 12 meses a partir del 1 de febrero de 2026."),
    ("Cláusula 5. Confidencialidad", "Las partes guardarán reserva de la información recibida durante 3 años."),
    ("Cláusula 7. Terminación", "Cualquiera de las partes puede terminar el contrato con un aviso escrito de 60 días."),
    ("Cláusula 8. Ley aplicable", LEY_1),
    ("Cláusula 9. Datos personales", "El Proveedor tratará los datos personales solo para prestar el servicio y los borrará al terminar el contrato."),
]

PAR_2_ORIGINAL = [
    ("CONTRATO DE ARRENDAMIENTO DE LOCAL COMERCIAL N.º LM-2026-077", ""),
    ("PARTES", "Inmobiliaria Horizonte Inventado S.A. (Arrendador, empresa ficticia) y Librería El Quijote de Papel "
               "S.A.S. (Arrendatario, empresa ficticia)"),
    ("Cláusula 1. Objeto", "El Arrendador entrega en arriendo el local 12 del Centro Comercial Ficticio de Bogotá."),
    ("Cláusula 2. Canon", "El Arrendatario pagará un canon de USD 1.500 mensuales."),
    ("Cláusula 3. Duración", "El arriendo dura 24 meses a partir del 1 de marzo de 2026."),
    ("Cláusula 4. Uso del local", "El local se destinará únicamente a la venta de libros y papelería."),
    ("Cláusula 5. Servicios públicos", "El Arrendatario paga los servicios de agua, energía e internet."),
    ("Cláusula 6. Depósito de garantía", "El Arrendatario entrega un depósito de USD 3.000, reembolsable al terminar el arriendo."),
    ("Cláusula 7. Mantenimiento", "El Arrendador responde por las reparaciones estructurales del local."),
    ("Cláusula 8. Ley aplicable", "Este contrato se rige por las leyes de la República de Colombia."),
]

# Esta adenda solo enumera lo que cambia: lo no mencionado sigue vigente.
PAR_2_ADENDA = [
    ("ADENDA N.º 1 AL CONTRATO N.º LM-2026-077", ""),
    ("PARTES", "Inmobiliaria Horizonte Inventado S.A. y Librería El Quijote de Papel S.A.S. acuerdan únicamente las "
               "siguientes modificaciones. Todo lo demás sigue vigente."),
    ("Primero", "La Cláusula 2 queda así: El Arrendatario pagará un canon de USD 1.650 mensuales."),
    ("Segundo", "Se elimina la Cláusula 6 (Depósito de garantía)."),
    ("Tercero", "Se agrega la Cláusula 9. Seguro: El Arrendatario mantendrá un seguro contra incendio por USD 50.000."),
]

ESPERADO = {
    "par_1": {
        "tipo_de_adenda": "reformula todo el contrato",
        "sections_changed": ["Cláusula 2", "Cláusula 3", "Cláusula 6", "Cláusula 9"],
        "topics_touched": ["Precio", "Pagos", "Penalidades", "Protección de datos"],
        "cambios": [
            {"tipo": "MODIFICACIÓN", "seccion": "Cláusula 2", "detalle": "El precio pasa de USD 2.000 a USD 2.400 mensuales."},
            {"tipo": "MODIFICACIÓN", "seccion": "Cláusula 3", "detalle": "El plazo de pago pasa de 30 a 45 días calendario."},
            {"tipo": "ELIMINACIÓN", "seccion": "Cláusula 6", "detalle": "Se quita la penalidad por demora de USD 50 diarios."},
            {"tipo": "ADICIÓN", "seccion": "Cláusula 9", "detalle": "Se agrega el tratamiento de datos personales."},
        ],
    },
    "par_2": {
        "tipo_de_adenda": "solo enumera las cláusulas que modifica",
        "sections_changed": ["Cláusula 2", "Cláusula 6", "Cláusula 9"],
        "topics_touched": ["Canon", "Garantías", "Seguros"],
        "clausula_no_mencionada": "Cláusula 7",
        "cambios": [
            {"tipo": "MODIFICACIÓN", "seccion": "Cláusula 2", "detalle": "El canon pasa de USD 1.500 a USD 1.650 mensuales."},
            {"tipo": "ELIMINACIÓN", "seccion": "Cláusula 6", "detalle": "Se quita el depósito de garantía de USD 3.000."},
            {"tipo": "ADICIÓN", "seccion": "Cláusula 9", "detalle": "Se agrega un seguro contra incendio por USD 50.000."},
        ],
    },
}


def _fuente(tamano, negrita=False):
    """Arial tiene tildes y ñ. Si no está instalada, se usa la fuente incluida en Pillow."""
    try:
        return ImageFont.truetype("arialbd.ttf" if negrita else "arial.ttf", tamano)
    except OSError:
        return ImageFont.load_default(size=tamano)


def _partir_en_lineas(texto, fuente, ancho_maximo):
    """Reparte las palabras en líneas que quepan en el ancho de la página."""
    lineas = []
    actual = ""
    for palabra in texto.split():
        candidata = (actual + " " + palabra).strip()
        if fuente.getlength(candidata) <= ancho_maximo:
            actual = candidata
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _dibujar_documento(bloques):
    """Dibuja el título y las secciones en una página blanca."""
    pagina = Image.new("RGB", (ANCHO, ALTO), "white")
    dibujo = ImageDraw.Draw(pagina)
    titulo, cuerpo = _fuente(38, negrita=True), _fuente(34)
    subtitulo = _fuente(34, negrita=True)
    ancho_util = ANCHO - 2 * MARGEN
    y = MARGEN
    for indice, (encabezado, texto) in enumerate(bloques):
        fuente_encabezado = titulo if indice == 0 else subtitulo
        for linea in _partir_en_lineas(encabezado, fuente_encabezado, ancho_util):
            dibujo.text((MARGEN, y), linea, font=fuente_encabezado, fill="black")
            y += 50
        for linea in _partir_en_lineas(texto, cuerpo, ancho_util):
            dibujo.text((MARGEN, y), linea, font=cuerpo, fill="black")
            y += 46
        y += 28
    if y > ALTO - MARGEN // 2:
        raise ValueError("El contrato no cabe en una sola imagen: " + bloques[0][0])
    return pagina


def _ensuciar(pagina, generador):
    """Imita un escaneo: leve rotación, desenfoque y grano, pero legible para una persona."""
    angulo = generador.uniform(0.5, 0.9) * generador.choice([-1, 1])
    girada = pagina.rotate(angulo, resample=Image.BICUBIC, fillcolor="white")
    borrosa = girada.filter(ImageFilter.GaussianBlur(0.7))
    grano = Image.frombytes("L", pagina.size, generador.randbytes(ANCHO * ALTO)).convert("RGB")
    return Image.blend(borrosa, grano, 0.06)


def generar_todo(carpeta=CARPETA_POR_DEFECTO):
    """Crea las 4 imágenes y esperado.json. Devuelve las rutas de las imágenes."""
    os.makedirs(carpeta, exist_ok=True)
    generador = random.Random(SEMILLA)  # semilla fija: siempre salen los mismos archivos
    rutas = []
    for nombre, bloques in [("par_1_original.png", PAR_1_ORIGINAL), ("par_1_adenda.png", PAR_1_ADENDA)]:
        ruta = os.path.join(carpeta, nombre)
        _dibujar_documento(bloques).save(ruta, format="PNG")
        rutas.append(ruta)
    for nombre, bloques in [("par_2_original.jpg", PAR_2_ORIGINAL), ("par_2_adenda.jpg", PAR_2_ADENDA)]:
        ruta = os.path.join(carpeta, nombre)
        _ensuciar(_dibujar_documento(bloques), generador).save(ruta, format="JPEG", quality=75)
        rutas.append(ruta)
    with open(os.path.join(carpeta, "esperado.json"), "w", encoding="utf-8") as archivo:
        json.dump(ESPERADO, archivo, ensure_ascii=False, indent=2)
    return rutas


if __name__ == "__main__":
    for ruta_creada in generar_todo():
        print("Creado: " + ruta_creada)
