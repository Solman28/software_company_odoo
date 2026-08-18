# ESTADOS DE ENVÍO
# TIPO DE PRECIO DE VENTA UNITARIO

# Codigos de Tipo de Nota de Credito Electronica
tnc = [
    ("01", "Anulación de la operación"),
    ("02", "Anulación por error en el RUC"),
    ("03", "Corrección por error en la descripción"),
    ("04", "Descuento global"),
    ("05", "Descuento por ítem"),
    ("06", "Devolución total"),
    ("07", "Devolución por ítem"),
    ("08", "Bonificación"),
    ("09", "Disminución en el valor"),
    ("10", "Otros Conceptos "),
    ("11", "Ajustes de operaciones de exportación"),
    ("12", "Ajustes afectos al IVAP"),
    ("13", "Ajustes – montos y/o fechas de pago"),
]

tnd = [
    ("01", "Intereses por mora"),
    ("02", "Aumento en el valor"),
    ("03", "Penalidades / otros conceptos"),
    ("11", "Ajustes de operaciones de exportación"),
    ("12", "Ajustes afectos al IVAP"),
]


# TIPO DE DOCUMENTO DE IDENTIDAD
tdi = [
    ("0", "DOC.TRIB.NO.DOM.SIN.RUC"),
    ("1", "DNI"),
    ("4", "Carnet de extranjería"),
    ("6", "RUC"),
    ("7", "Pasaporte"),
    ("A", "Cédula diplomática")]

# CÓDIGO DE DOCUMENTOS RELACIONADOS TRIBUTARIOS - CATÁLOGO 12
tdr = [("01","Factura – emitida para corregir error en el RUC"),
        ("02","Factura – emitida por anticipos"),
        ("03","Boleta de Venta – emitida por anticipos"),
        ("04","Ticket de Salida - ENAPU "),
        ("05","Código SCOP"),
        ("06","Factura electrónica remitente"),
        ("07","Guia de remisión remitente"),
        ("08","Declaración de salida del depósito franco "),
        ("09","Declaración simplificada de importación "),
        ("10","Liquidación de compra - emitida por anticipos"),
        ("99","Otros")]

# TIPO DE COMPROBANTE
tdc = [
    ("00", "Otros"),
    ("01", "Factura"),
    ("02","Recibo por Honorarios"),
    ("03", "Boleta de Venta"),
    # ("04","Liquidación de compra"),
    ("05","Boleto de compañía de aviación comercial por el servicio de transporte aéreo de pasajeros"),
    ("06","Carta de porte aéreo por el servicio de transporte de carga aérea"),
    ("07", "Nota de crédito"),
    ("08", "Nota de débito"),
    ("09", "Guía de remisión - Remitente"),
    ("10","Recibo por Arrendamiento"),
    # ("11","Póliza emitida por las Bolsas de Valores, Bolsas de Productos o Agentes de Intermediación por operaciones realizadas en las Bolsas de Valores o Productos o fuera de las mismas, autorizadas por CONASEV"),
    # ("12","Ticket o cinta emitido por máquina registradora"),
    # ("13","Documento emitido por bancos, instituciones financieras, crediticias y de seguros que se encuentren bajo el control de la Superintendencia de Banca y Seguros"),
    ("14","Recibo por servicios públicos de suministro de energía eléctrica, agua, teléfono, telex y telegráficos y otros servicios complementarios que se incluyan en el recibo de servicio público"),
    ("15","Boleto emitido por las empresas de transporte público urbano de pasajeros"),
    ("16","Boleto de viaje emitido por las empresas de transporte público interprovincial de pasajeros dentro del país"),
    # ("17","Documento emitido por la Iglesia Católica por el arrendamiento de bienes inmuebles"),
    ("18","Documento emitido por las Administradoras Privadas de Fondo de Pensiones que se encuentran bajo la supervisión de la Superintendencia de Administradoras Privadas de Fondos de Pensiones"),
    # ("19","Boleto o entrada por atracciones y espectáculos públicos"),
    ("20","Comprobante de Retención"),
    # ("21","Conocimiento de embarque por el servicio de transporte de carga marítima"),
    # ("22","Comprobante por Operaciones No Habituales"),
    # ("23","Pólizas de Adjudicación emitidas con ocasión del remate o adjudicación de bienes por venta forzada, por los martilleros o las entidades que rematen o subasten bienes por cuenta de terceros"),
    # ("24","Certificado de pago de regalías emitidas por PERUPETRO S.A"),
    # ("25","Documento de Atribución (Ley del Impuesto General a las Ventas e Impuesto Selectivo al Consumo, Art. 19º, último párrafo, R.S. N° 022-98-SUNAT)."),
    # ("26","Recibo por el Pago de la Tarifa por Uso de Agua Superficial con fines agrarios y por el pago de la Cuota para la ejecución de una determinada obra o actividad acordada por la Asamblea General de la Comisión de Regantes o Resolución expedida por el Jefe de la Unidad de Aguas y de Riego (Decreto Supremo N° 003-90-AG, Arts. 28 y 48)"),
    # ("27","Seguro Complementario de Trabajo de Riesgo"),
    # ("28","Tarifa Unificada de Uso de Aeropuerto"),
    # ("29","Documentos emitidos por la COFOPRI en calidad de oferta de venta de terrenos, los correspondientes a las subastas públicas y a la retribución de los servicios que presta"),
    ("30","Documentos emitidos por las empresas que desempeñan el rol adquirente en los sistemas de pago mediante tarjetas de crédito y débito"),
    ("31","Guía de Remisión - Transportista"),
    # ("32","Documentos emitidos por las empresas recaudadoras de la denominada Garantía de Red Principal a la que hace referencia el numeral 7.6 del artículo 7° de la Ley N° 27133 – Ley de Promoción del Desarrollo de la Industria del Gas Natural "),
    # ("34","Documento del Operador"),
    # ("35","Documento del Partícipe"),
    ("36","Recibo de Distribución de Gas Natural"),
    # ("37","Documentos que emitan los concesionarios del servicio de revisiones técnicas vehiculares, por la prestación de dicho servicio "),
    # ("40","Constancia de Depósito - IVAP (Ley 28211)"),
    ("40", "Comprobante de Percepción "),
    ("41", "Comprobante de Percepción – Venta interna ( físico - formato impreso)"),
    ("50","Declaración Única de Aduanas - Importación definitiva"),
    # ("52","Despacho Simplificado - Importación Simplificada"),
    # ("53","Declaración de Mensajería o Courier"),
    # ("54","Liquidación de Cobranza"),
    # ("87","Nota de Crédito Especial"),
    # ("88","Nota de Débito Especial"),
    ("91","Comprobante de No Domiciliado"),
    # ("96","Exceso de crédito fiscal por retiro de bienes"),
    ("97","Nota de Crédito - No Domiciliado"),
    ("98","Nota de Débito - No Domiciliado"),
    # ("99","Otros -  Consolidado de Boletas de Venta")
    ("100", "Notas de Venta"),
]

# ESTADO DE COMPROBANTE ELECTRÓNICO
ece = [
    ("0", "0_NO_EXISTE"),
    ("1", "1_ACEPTADO"),
    ("2", "2_ANULADO"),
    ("3", "3_AUTORIZADO"),
    ("4", "4_NO_AUTORIZADO")]

# ESTADO DE COMPROBANTE: EMISIÓN
estado_emision = [
    ("A", "Aceptado"),
    ("E", "Enviado a SUNAT"),
    ("N", "Envio Erróneo"),
    ("O", "Aceptado con Observación"),
    ("R", "Rechazado"),
    ("P", "Pendiente de envió a SUNAT")]

# ESTADO CONTRIBUYENTE: RUC
ecruc = [
    ("00", "00_ACTIVO"),
    ("01", "01_BAJA_PROVISIONAL"),
    ("02", "02_BAJA_PROV_POR_OFICIO"),
    ("03", "03_SUSPENSION_TEMPORAL"),
    ("10", "10_BAJA_DEFINITIVA"),
    ("11", "11_BAJA_DE_OFICIO"),
    ("22", "22_INHABILITADO-VENT.UNICA")]

# CONDICION DOMICILIO CONTRIBUYENTE
cdc = [
    ("00", "00_HABIDO"),
    ("09", "09_PENDIENTE"),
    ("11", "11_POR_VERIFICAR"),
    ("12", "12_NO_HABIDO"),
    ("20", "20_NO_HALLADO")]

