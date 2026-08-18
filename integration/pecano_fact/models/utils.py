from odoo.exceptions import UserError,ValidationError
import requests, re
import random
import json
import logging
from odoo import _,fields
_logger = logging.getLogger(__name__)
from xml.dom.minidom import parse, parseString
import base64
from odoo.fields import Datetime, time
from datetime import datetime
from pytz import timezone

PECANO_ISSUING_ENTITY_MAP = {
    '01': 1,  # SUCAMEC
    '02': 2,  # DIGEMID
    '03': 3,  # DIGESA
    '04': 4,  # SENASA
    '05': 5,  # SERFOR
    '06': 6,  # MTC
    '07': 7,  # PRODUCE
    '08': 8,  # MIN. AMBIENTE
    '09': 9,  # SANIPES
    '10': 10, # MML
    '11': 11, # MINSA
    '12': 12, # GOBIERNO REGIONAL
}

PECANO_ESTADOS_CPE = {
    0: 'E', # 0: En proceso E: Enviado a SUNAT
    1: 'A', # 1: Aceptado A: Aceptado
    1: 'O',  # 1: Aceptado O: Aceptado con Observación
    2: 'A', # 2: Anulado A: Aceptado
    3: 'R', # 3: Rechazado R: Rechazado
}

INDICADOR_VEHICULO_CONDUCTORES = 1 # 1 (SI), 0 (NO)

def get_amounts_items(item):
    """
        OBTENER LOS IMPORTES POR LINEA:
            Obtiene los impuestos / descuentos por línea facturable
    """
    amounts = {
        'unit_value': 0,
        'unit_price': 0,
        'discounts': 0,
        'subtotal': 0,
        'igv': 0,
        'icbp': 0,
        'isc': 0,
        'total': 0
    }
    # [ CÁLCULO DE LOS IMPUESTOS TOTALES POR LINEA ]
    sign = item.move_id.direction_sign
    amount_currency = sign * (item.price_unit * (1 - item.discount / 100))
    quantity = item.quantity
    is_free_tax = False
    excluded_igv = False
    compute_all_currency = item.tax_ids.compute_all(
        amount_currency,
        currency=item.move_id.currency_id,
        quantity=quantity,
        product=item.product_id,
        partner=item.move_id.partner_id,
        is_refund=item.is_refund,
        handle_price_include=True,
        include_caba_tags=item.move_id.always_tax_exigible,
    )
    for tax in compute_all_currency.get('taxes',[]):
        inf = item.env['account.tax'].search([('id','=',tax.get('id',0))])
        amount = round(abs(tax.get('amount',0)),2)
        reason = inf.l10n_pe_edi_affectation_reason

        # [ IGV ]
        if inf.l10n_pe_edi_tax_code == '1000':
            amounts.update({
                'type_igv': reason,
                'percentage_igv': inf.amount,
                'igv': amount
            })
        # [ EXP - EXPORTACION ]
        elif inf.l10n_pe_edi_tax_code in ['9995','9996','9997','9998','9999']:
            amounts.update({
                'type_igv': reason,
                'percentage_igv': inf.amount,
            })

        # [ GRATUITO - EXO - INA ]
        if inf.l10n_pe_edi_tax_code in ['9996', '9997', '9998']:
            is_free_tax = True

        # if inf.tax_group_id.name.upper() == "FACTURA GRATUITA":
        #     amounts.update({
        #         'unit_price': amount,
        #         'unit_value': amount,
        #         'subtotal':amount,
        #         'total': amount,
        #     })
    
    # discount_percentage = 0
    compute_all_origin = item.tax_ids.compute_all(
            item.price_unit,
            currency=item.move_id.currency_id,
            quantity=quantity,
            product=item.product_id,
            partner=item.move_id.partner_id,
            is_refund=item.is_refund,
            handle_price_include=True,
            include_caba_tags=item.move_id.always_tax_exigible,
        )
    if not is_free_tax:
        amounts.update({
            'subtotal': round(abs(compute_all_currency.get('total_excluded',0)),2),
            'total': round(abs(compute_all_currency.get('total_included',0)),2),
        })
        unit_value = round(compute_all_origin['total_excluded'],2)
        if item.discount > 0:
            discount_percentage = round(item.discount / 100, 3)
            amounts.update({
                'discount_percentage': discount_percentage,
                'discount_amount': round(unit_value * discount_percentage, 2),
            })
        amounts.update({
            'unit_value': unit_value,
            'unit_price': round(compute_all_origin['total_included'],2) if not excluded_igv else round(compute_all_origin['total_excluded'],2),
        })
        
    return amounts

# [ VALIDAR: INFORMACIÓN SIN RELLENAR ]
# [ INFORMATION: ATRIBUTOS A VALIDAR ]
def replace_false(information):
    if information:
        return information
    else:
        return ""

def replace_false_number(value, number_type=int, default=0):
    """
    Reemplaza valores falsos por un número seguro.
    Convierte cadenas numéricas a int o float según se indique.
    - Si value es None, False o '', devuelve el valor por defecto.
    - Si value es texto numérico ('01', '1.5'), lo convierte al tipo indicado.
    - Si ocurre error de conversión, devuelve el valor por defecto.
    """
    try:
        if value in (False, None, ''):
            return default
        return number_type(value)
    except Exception:
        return default

def sanitize_field(value):
    """
    Sanitiza un campo de texto según las reglas de PecanoFact:
    - Acepta solo caracteres alfanuméricos, espacios y signos comunes.
    - Elimina caracteres no permitidos (<, >, ", ', ;, etc.).
    - Recorta espacios extra.
    """
    if not value:
        return ""

    # Convertir a string por seguridad
    text = str(value).strip()

    # Reemplazar saltos de línea o tabs por un espacio
    text = re.sub(r"[\r\n\t]+", " ", text)

    # Permitir solo caracteres seguros: letras, números, puntos, comas, guiones, slash, paréntesis y espacios
    text = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñüÜ.,\-#/() ]+", "", text)

    # Quitar espacios duplicados
    text = re.sub(r"\s{2,}", " ", text)

    return text
    
# [ OBTENER: CUERPO DEL ENVIO DE GUIA DE REMISIÓN (REMITENTES Y TRANSPORTISTAS) ]
def get_fecha_emision_guide(document):
    fecha_emision = document.fecha_emision if document.fecha_emision else fields.Date.context_today(document)

    now_local = fields.Datetime.context_timestamp(document, fields.Datetime.now())
    dt = datetime.combine(fecha_emision, now_local.time())

    return dt

def get_fecha_inicio_traslado(document, emission_dt):
    fecha_inicio_traslado = document.fecha_inicio_traslado

    if not fecha_inicio_traslado:
        raise UserError("La fecha de traslado es obligatorio.")

    dt = datetime.combine(fecha_inicio_traslado, emission_dt.time())

    return dt

def get_general_information_guide(guide, emision_dt, body):
    numero_documento = guide.name
    note = replace_false(guide.note or "").strip()

    # Valores ONU y Clase
    onu = guide.onu_gre.name if guide.onu_gre else ""
    clase = guide.clase or ""
    precintos = guide.precintos or ""
    planta = guide.warehouse_id.name if guide.warehouse_id else ""

    extras = []
    if onu:
        extras.append(f"ONU: {onu}")
    if clase:
        extras.append(f"CLASE: {clase}")
    if precintos:
        extras.append(f"PRECINTOS: {precintos}")
    if planta:
        extras.append(f"PLANTA: {planta}")

    extra_text = " - ".join(extras) if extras else ""

    # Concatenación final
    observacion = note
    if extra_text:
        if observacion:
            observacion = f"{extra_text} | {observacion}"
        else:
            observacion = extra_text

    observacion = observacion.replace("\n", " ").replace("\r", " ").strip()
    observacion = observacion[:250]

    body.update({
        'NumeroDocumento': numero_documento,
        'FechaEmision': emision_dt.strftime('%Y-%m-%dT%H:%M:%S') if emision_dt else "",
        'Correo': guide.company_id.email,
        'Observacion': observacion
    })
    _logger.info("[GRE %s] get_general_information_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body
    
def get_sender_guide(guide, body):
    if guide.gre_type == 'transportista':
        if guide.related_document_code == '09':
            remitente = guide.guia_remitente_id.company_id
    else:
        remitente = guide.company_id
    body.update({
        'Remitente':{
            'Ruc': replace_false(remitente.vat),
            'RazonSocial': replace_false(remitente.name),
            'DomFiscalUbigeo': replace_false(guide.company_partner_id.ubigeo),
            'DomFiscalDireccion': replace_false(remitente.street)
        }
    })
    return body

def get_addressee_guide(guide, body):
    addressee = guide.destinatario_partner_id
    body.update({
        'Destinatario': {
            'TipoDocumentoIdentidad': replace_false_number(addressee.l10n_latam_identification_type_id.jnq_code_pecanofact, int),
            'ValorDocumentoIdentidad': replace_false(guide.destinatario_numero_documento_identidad),
            'RazonSocial': replace_false(addressee.name)
        }
    })
    _logger.info("[GRE %s] get_addressee_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_company_public_transport_guide(guide, body):
    carrier = guide.transporte_partner_id
    body.update({
        'Transportista': {
            'TipoDocumentoIdentidad': replace_false_number(carrier.l10n_latam_identification_type_id.jnq_code_pecanofact, int),
            #'ValorDocumentoIdentidad': replace_false(carrier.vat),
            'ValorDocumentoIdentidad': '20506120315',
            'RazonSocial': replace_false(carrier.name)
        },
        'NumeroRegistroMtc': replace_false(guide.transporte_partner_mtc_id.mtc_number),
        'NumeroAutorizacionEspecialTransportista': replace_false(guide.autorization_number_transporte_partner_id.mtc_number),
        'EntidadEmisoraAutorizacionTransportista': PECANO_ISSUING_ENTITY_MAP.get(carrier.l10n_pe_edi_authorization_issuing_entity, 0)
    })
    _logger.info("[GRE %s] get_company_public_transport_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_driver_vehicle_guide(guide, body):
    array_vehicles = []
    index = 1
    if guide.transport_type == '01':
        # Vehículo principal
        if guide.vehiculo_publico_id:
            data = {
                "IdItem": index,
                "NumeroPlaca": replace_false(guide.vehiculo_publico_id.license_plate),
                "NumeroCivTucChv": replace_false(guide.tuce_chv_vehiculo_publico),
                "NumeroAutorizacionEspecial": replace_false(guide.vehiculo_publico_mtc_id.mtc_number),
                "EntidadEmisoraAutorizacion": PECANO_ISSUING_ENTITY_MAP.get(guide.vehiculo_publico_id.authorization_issuing_entity, 0)
            }
            array_vehicles.append(data)
            index += 1

        # Vehículo secundario
        if guide.vehiculo_publico_secundario_id:
            data = {
                "IdItem": index,
                "NumeroPlaca": replace_false(guide.vehiculo_publico_secundario_id.license_plate),
                "NumeroCivTucChv": replace_false(guide.tuce_chv_vehiculo_publico_secundario),
                "NumeroAutorizacionEspecial": replace_false(guide.vehiculo_publico_secundario_mtc_id.mtc_number),
                "EntidadEmisoraAutorizacion": PECANO_ISSUING_ENTITY_MAP.get(guide.vehiculo_publico_secundario_id.authorization_issuing_entity, 0)
            }
            array_vehicles.append(data)
    elif guide.transport_type == '02':
        # Vehículo principal
        if guide.vehiculo_privado_id:
            data = {
                "IdItem": index,
                "NumeroPlaca": replace_false(guide.vehiculo_privado_id.license_plate),
                #"NumeroCivTucChv": replace_false(guide.tuce_chv_vehiculo_privado),
                "NumeroAutorizacionEspecial": replace_false(guide.vehiculo_privado_mtc_id.mtc_number),
                "EntidadEmisoraAutorizacion": PECANO_ISSUING_ENTITY_MAP.get(guide.vehiculo_privado_id.authorization_issuing_entity, 0)
            }
            array_vehicles.append(data)
            index += 1

        # Vehículo secundario
        if guide.vehiculo_privado_secundario_id:
            data = {
                "IdItem": index,
                "NumeroPlaca": replace_false(guide.vehiculo_privado_secundario_id.license_plate),
                #"NumeroCivTucChv": replace_false(guide.tuce_chv_vehiculo_privado_secundario),
                "NumeroAutorizacionEspecial": replace_false(guide.vehiculo_privado_secundario_mtc_id.mtc_number),
                "EntidadEmisoraAutorizacion": PECANO_ISSUING_ENTITY_MAP.get(guide.vehiculo_privado_secundario_id.authorization_issuing_entity, 0)
            }
            array_vehicles.append(data)
    
    # Conductores
    array_drivers = []
    if guide.transport_type == '01':
        drivers = guide.conductor_publico_id | guide.conductor_publico_secundario_id
    elif guide.transport_type == '02':
        drivers = guide.conductor_privado_id | guide.conductor_privado_secundario_id

    for index, item in enumerate(drivers, start=1):
        data = {
            "IdItem": index,
            "TipoDocumentoIdentidad": replace_false_number(item.l10n_latam_identification_type_id.jnq_code_pecanofact, int),
            "ValorDocumentoIdentidad": replace_false(item.vat),
            "NombresConductor": replace_false(item.names),
            "ApellidosConductor": replace_false(item.fathers_last_name)+' '+replace_false(item.mothers_last_name),
            "NumeroLicenciaConducir": replace_false(item.l10n_pe_edi_operator_license)
        }
        array_drivers.append(data)

    body.update({
        "Vehiculos": array_vehicles,
        "Conductores": array_drivers
    })
    _logger.info("[GRE %s] get_driver_vehicle_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_transfer_guide(guide, emision_dt, body):
    fecha_inicio_traslado = get_fecha_inicio_traslado(guide, emision_dt)
    body.update({
        'FechaInicioTraslado': fecha_inicio_traslado.strftime("%Y-%m-%dT%H:%M:%S") if fecha_inicio_traslado else "",
        'PesoBrutoTotalCarga': round(guide.peso_bruto_total or 0.0, 3),
        'UnidadMedidaPesoBruto': replace_false(guide.peso_bruto_uom),
    })
    _logger.info("[GRE %s] get_transfer_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_route_guide(guide, body):
    body.update({
        'UbigeoPartida': replace_false(guide.lugar_partida_ubigeo),
        'DireccionPartida': replace_false(guide.lugar_partida_direccion),
        'CodLocalSunatPuntoPartida': replace_false(guide.codigo_sunat_partida),
        'UbigeoLlegada': replace_false(guide.lugar_llegada_ubigeo),
        'DireccionLlegada': replace_false(guide.lugar_llegada_direccion),
        'CodLocalSunatPuntoLlegada': replace_false(guide.codigo_sunat_llegada)
    })
    _logger.info("[GRE %s] get_route_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_items_guide(guide, body):
    items = []
    motivo_traslado = guide.env['transfer.reason'].search([('code', '=', guide.motivo_traslado)])
    for index, item in enumerate(guide.guia_remision_line_ids, start=1):
        if item.product_id.type in ['product','consu']:
            # [ IMPORTACIÓN | EXPORTACIÓN ]
            unidad_medida = replace_false(item.uom_id.l10n_pe_edi_measure_unit_code.code)
            if motivo_traslado.jnq_code_pecanofact in ('8', '9'):
                unidad_medida = replace_false(item.uom_id.code_dam)
            line = {
                'IdItem': index,
                'Cantidad': round(item.qty, 10),
                'UnidadMedida': unidad_medida,
                'Descripcion': replace_false(item.description),
                'CodigoProducto': replace_false(item.product_id.default_code if item.product_id.default_code else item.product_id.product_tmpl_id.default_code) if item.product_id else random.randint(0, 9999),
                "CodigoProductoSunat": replace_false(item.product_id.unspsc_code_id.code)
            }
            items.append(line)
    body.update({
        'DetalleGuia': items,
    })
    _logger.info("[GRE %s] get_items_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_company_transport_guide(guide, body):
    carrier = guide.transporte_partner_id
    body.update({
        'Transportista': {
            'Ruc': replace_false(carrier.vat),
            'RazonSocial': replace_false(carrier.name),
            "DomFiscalUbigeo": replace_false(carrier.ubigeo),
            "DomFiscalDireccion": replace_false(carrier.street)
        },
        'NumeroRegistroMtc': replace_false(guide.transporte_partner_mtc_id.mtc_number),
        "NumeroAutorizacionEspecial": replace_false(guide.transporte_partner_mtc_id.mtc_number),
        "EntidadEmisoraAutorizacion": PECANO_ISSUING_ENTITY_MAP.get(carrier.l10n_pe_edi_authorization_issuing_entity, 0)
    })
    _logger.info("[GRE %s] get_company_transport_guide:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

def get_related_document(guide, body):
    if guide.journal_id.invoice_type_code == '09' or guide.gre_type == 'remitente':
        documents = []
        if guide.documento_asociado == 'comprobante_pago':
            for index, move in enumerate(guide.comprobante_pago_ids, start=1):
                documents.append({
                    'IdItem': index,
                    #'TipoComprobanteVenta': move.invoice_type_code,
                    'TipoComprobanteVenta': replace_false(move.l10n_latam_document_type_id.code),
                    'NumeroComprobanteVenta': replace_false(move.name),
                    'FechaEmisionVenta': move.invoice_date.strftime("%Y-%m-%d") if move.invoice_date else "",
                })
            body.update({ 
                'VentaGuia': documents
            })
    if guide.journal_id.invoice_type_code == '31' or guide.gre_type == 'transportista':
        if guide.related_document.jnq_code_pecanofact == '9':
            body.update({
                "TipoComprobanteRelacionado": 9,
                "NumeroComprobanteRelacionado": replace_false(guide.guia_remitente_id.name),
                #"RucEmisorComprobanteRelacionado": replace_false(guide.guia_remitente_id.company_id.vat),
                "RucEmisorComprobanteRelacionado":'20514133931'
            })
    _logger.info("[GRE %s] get_related_document:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body
    
# [ GUIDE: GUIA DE REMISIÓN REMITENTE O TRANSPORTISTA ]
def get_request_guide_body(guide):
    # [ VALIDACIONES: GUIA REMISIÓN TRANSPORTISTA / GUÍA DE REMISIÓN REMITENTE ]
    numero_documento = guide.name
    if not numero_documento:
        if guide.estado_gre_sunat in ["A", "O"]: # A: Aceptado O: Aceptado con Observación
            raise UserError("La guía de remisión ya ha sido emitida y tiene estado de ACEPTADA.")
        if guide.estado_gre_sunat in ["R"]:
            raise UserError("La guía de remisión ya ha sido emitida y tiene estado de RECHAZADA.")
    else:
        tipo_doc = guide.journal_id.invoice_type_code
        if tipo_doc == '09' and not re.match(r'^T[A-Z0-9]{3}-\d{1,8}$', numero_documento):
            raise UserError("El número de la guía de remisión remitente no tiene el formato correcto: " + str(numero_documento))
        elif tipo_doc == '31' and not re.match(r'^V[A-Z0-9]{3}-\d{1,8}$', numero_documento):
            raise UserError("El número de la guía de remisión transportista no tiene el formato correcto: " + str(numero_documento))
    
    motivo_traslado = guide.env['transfer.reason'].search([('code', '=', guide.motivo_traslado)])
    modalidad_transporte = guide.env["transport.type"].search([('code', '=', guide.transport_type)])
    # [ OBTENER: BODY ]
    # [ Información general ]
    body = {}
    emision_dt = get_fecha_emision_guide(guide)
    body = get_general_information_guide(guide, emision_dt, body)
    # [ Destinatario ]
    body = get_addressee_guide(guide, body)
    # [ Traslado ]
    body = get_transfer_guide(guide, emision_dt, body)
    # [ Ruta ]
    body = get_route_guide(guide, body)

    # [ GRE: REMITENTE ]
    if guide.journal_id.invoice_type_code == '09' or guide.gre_type == 'remitente':
        remitente = guide.company_id
        body.update({
            'Remitente':{
                'Ruc': replace_false(remitente.vat),
                'RazonSocial': replace_false(remitente.name),
                'DomFiscalUbigeo': replace_false(guide.company_partner_id.ubigeo),
                'DomFiscalDireccion': replace_false(remitente.street)
            },
        })
        # [ Compra | Recojo de bienes transformados ]
        if motivo_traslado.jnq_code_pecanofact in ('2', '7'):
            proveedor = guide.proveedor_partner_id
            body.update({
                'Proveedor':{
                    'TipoDocumentoIdentidad': replace_false_number(proveedor.l10n_latam_identification_type_id.jnq_code_pecanofact, int),
                    'ValorDocumentoIdentidad': replace_false(guide.proveedor_numero_documento_identidad),
                    'RazonSocial': replace_false(proveedor.name)
                },
            })

        body.update({
            'MotivoTraslado': replace_false_number(motivo_traslado.jnq_code_pecanofact, int),
            'ModalidadTransporte': replace_false_number(modalidad_transporte.jnq_code_pecanofact, int),
        })

        # [ Exportación ]
        if motivo_traslado.jnq_code_pecanofact == '9':
            body.update({
                'NumeroBultos': guide.numero_bultos,
            })
        
        #[ Transporte Público(1) / Privado(2) ]
        if modalidad_transporte.jnq_code_pecanofact == '1':
            body = get_company_public_transport_guide(guide, body)
            # [ INDICADOR VEHICULO CONDUCTORES ]
            body.update({'IndicadorVehiculoConductoresTransp': INDICADOR_VEHICULO_CONDUCTORES}) #1 (SI), 0 (NO)
            if INDICADOR_VEHICULO_CONDUCTORES == 1:
                body = get_driver_vehicle_guide(guide, body)
        elif modalidad_transporte.jnq_code_pecanofact == '2':
            body.update({'IndicadorVehiculoConductoresTransp': 0}) #1 (SI), 0 (NO)
            body = get_driver_vehicle_guide(guide, body)
    
    # [ GRE: TRANSPORTISTA ]
    if guide.journal_id.invoice_type_code == '31' or guide.gre_type == 'transportista':
        remitente = guide.guia_remitente_id.company_id
        body.update({
            'Remitente':{
                "TipoDocumentoIdentidad": replace_false_number(remitente.partner_id.l10n_latam_identification_type_id.jnq_code_pecanofact, int),
                "ValorDocumentoIdentidad": replace_false(remitente.vat),
                #"ValorDocumentoIdentidad": "20514133931",
                "RazonSocial": replace_false(remitente.name)
            }
        })
        body = get_company_transport_guide(guide, body)
        body = get_driver_vehicle_guide(guide, body)
    
    # [ Documento relacionado ]
    body = get_related_document(guide, body)
    # [ Detalle ]
    body = get_items_guide(guide, body)

    _logger.info("JSON construido para GRE %s:\n%s", guide.name, json.dumps(body, indent=4, ensure_ascii=False))
    return body

# [ ACTUALIZAR: INFORMACIÓN DEL LOG ACTUAL DE LA GUIA DE REMISIÓN ]
# [ DOCUMENT: GUIA DE REMISIÓN REMITENTE O TRANSPORTISTA ]
# [ BODY: JSON CREADO en get_request_guide_body() ]
def get_log_status_guide(document,body):
    data = {
        "guia_remision_id": document.id, # Guía de Remisión
        "request_json": json.dumps(body, indent=4), # Contenido de Comprobante en JSON
        "name": document.name, # Nombre
        "date_request": fields.Datetime.today(), # Fecha de Envío a SUNAT
        "date_issue": document.fecha_emision, # Fecha de Emisión a SUNAT
        "status": "P", # Estado Pendiente de envió a SUNAT
        "company_id": document.company_id.id, # Compañía
        "submitted_pecanofact": True if document.company_id.sunat_provider == 'pecanofact' else False       
    }
    return data

# [ OBTENER: CUERPO DE LA CONSULTA DE GUIAS DE REMISIÓN (REMITENTE Y TRANSPORTISTA) ]
def get_request_check_guide_body(log_guide):
    """
        VALIDAR GRE REMITENTE Y GRE TRANSPORTISTA:
            Procesar y crear todos los valores necesarios para el objeto json
    """
    type_guide = {
        '09': 70, # [ GRE REMITENTE ]
        '31': 80  # [ GRE TRANSPORTISTA ]
    }
    guide = log_guide.guia_remision_id
    body = {
	    'TipoDocumento': type_guide.get(guide.journal_id.invoice_type_code,0),
        'FechaEmision': guide.fecha_emision.strftime("%Y-%m-%d") if guide.fecha_emision else "",
	    'NumeroDocumento': guide.name or ""
    }
    return body

# [ OBTENER ENLACE PDF GUIA DE REMISIÓN ]
def get_pdf_link_guide(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test

        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/enlace/pdf"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }

        body = get_request_check_guide_body(document.current_log_status_id)

        response = requests.post(url, json=body, headers=headers, timeout=20)
   
        response_data = response.json()

        if response.status_code == 200:
            enlace_pdf = response_data.get("EnlacePDF", "")
            return enlace_pdf
                
        elif response.status_code in (400,404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaEnlacePDF): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(e)

# [ CONSULTAR ESTADO : GUIA DE REMISIÓN ]
def get_guide_status(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/estado/documento"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }
        body = get_request_check_guide_body(document.current_log_status_id)
        response = requests.post(url, json=body, headers=headers, timeout=20)
        # SI TOKEN EXPIRÓ
        if response.status_code == 401:
            token = company_id.pecano_generate_token()
            headers["TOKEN-PSE-PECANOFACT"] = token
            response = requests.post(url, json=body, headers=headers, timeout=20)
        try:
            response_data = response.json()
        except Exception:
            raise UserError("Respuesta inválida de PecanoFact")
        if response.status_code == 200:
            estado_documento = response_data.get("EstadoDocumento")
            cdr_description = response_data.get("DescripcionCdrDeclaracion") or ""
            aceptado_con_observacion = response_data.get("AceptadoConObservacion")
            if estado_documento == 0: # En proceso
                status = 'E'
            elif estado_documento in [1, 2]: # Aceptado, Anulado
                status = 'A'
            elif estado_documento == 3: # Rechazado
                status = 'R'
            else:
                status = document.estado_gre_sunat
            if aceptado_con_observacion is True:
                status = 'O' # Aceptado con observacion
            data = {
                "status": status,
                "status_pecanofact": str(estado_documento),
                "sunat_observaciones": cdr_description
            }
            return data
        elif response.status_code in (400,404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaCPE x NumeroDocumento): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")

# [ CONSULTAR PDF, XML, CDR : GUIA DE REMISIÓN ]
def get_guide_files(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/archivo/documento"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }

        body = get_request_check_guide_body(document.current_log_status_id)
        response = requests.post(url, json=body, headers=headers, timeout=20)
        response_data = response.json()

        if response.status_code == 200:
            archivo_declaracion = response_data.get("ArchivoCpeDeclaracion", {}) or {}
            #identificador_anulacion = replace_false(response_data.get("IdentificadorAnulacion", ""))
            #archivo_anulacion = response_data.get("ArchivoCpeAnulacion", {})
            cdr_base64 = xml_base64 = pdf_base64 = ""
            if archivo_declaracion:
                for name in ['Cdr', 'Xml', 'Pdf']:
                    value = archivo_declaracion.get(name)
                    if not isinstance(value, dict):
                        value = {}
                    archivo_declaracion[name] = value
                cdr_base64 = replace_false(archivo_declaracion['Cdr'].get("ContenidoArchivo", ""))
                cdr_nombre = replace_false(archivo_declaracion['Cdr'].get("NombreArchivo", ""))
                xml_nombre = replace_false(archivo_declaracion['Xml'].get("NombreArchivo", ""))
                xml_base64 = replace_false(archivo_declaracion['Xml'].get("ContenidoArchivo", ""))
                pdf_base64 = replace_false(archivo_declaracion['Pdf'].get("ContenidoArchivo", ""))

            data = {
                "response_json": json.dumps(response_data, indent=4),
                "xml_name": xml_nombre,
                "xml_base64": xml_base64,
                "signed_xml_data_without_format": (
                    base64.b64decode(xml_base64).decode("utf-8") if xml_base64 != "" else ""
                ),
                "signed_xml_data": (
                    parseString(base64.b64decode(xml_base64).decode("utf-8")).toprettyxml() if xml_base64 != "" else ""
                ),
                "signed_xml": pdf_base64,
                "cdr_name": cdr_nombre,
                "cdr_base64": cdr_base64,
                "response_content_xml": (
                    parseString(base64.b64decode(cdr_base64).decode("utf-8")).toprettyxml() if cdr_base64 != "" else ""
                ),
                "response_xml_without_format": (
                    base64.b64decode(cdr_base64).decode("utf-8") if cdr_base64 != "" else ""
                ),
                "date_request": fields.Datetime.now(),
                "log_observation_ids": [],
            }
            return data
                
        elif response.status_code in (400,404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaArchivoCpe): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")

# [ ACTUALIZAR: INFORMACIÓN DEL LOG ACTUAL DEL DOCUMENTO ELECTÓNICO (FACTURAS, BOLETAS Y NOTAS) ]
# [ DOCUMENT: DOCUMENTO ELECTRÓNICO (FACTURAS, BOLETAS Y NOTAS) ]
# [ BODY: JSON CREADO EN get_request_invoice_body() ]
def vals_log_cpe(document,body):
    data = {
        "account_move_id": document.id, # Comprobante
        "request_json": json.dumps(body, indent=4), # Contenido de Comprobante en JSON
        "name": document.name, # Nombre
        "date_request": fields.Date.today(), # Fecha de Envío a SUNAT
        "date_issue": document.invoice_date, # Fecha de Emisión a SUNAT
        "status": "P", # Estado Pendiente de envió a SUNAT
        "company_id": document.company_id.id, # Compañía
        "submitted_pecanofact": True if document.company_id.sunat_provider == 'pecanofact' else False       
    }
    return data

# [ CONSULTAR ESTADO : COMPROBANTE ELECTRÓNICO ]
def get_invoice_status(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/estado/documento"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }
        body = get_request_check_invoice(document.current_log_status_id)
        response = requests.post(url, json=body, headers=headers, timeout=20)
        # SI TOKEN EXPIRÓ
        if response.status_code == 401:
            token = company_id.pecano_generate_token()
            headers["TOKEN-PSE-PECANOFACT"] = token
            response = requests.post(url, json=body, headers=headers, timeout=20)
        try:
            response_data = response.json()
        except Exception:
            raise UserError("Respuesta inválida de PecanoFact")
        if response.status_code == 200:
            estado_documento = response_data.get("EstadoDocumento")
            cdr_description = response_data.get("DescripcionCdrDeclaracion") or ""
            aceptado_con_observacion = response_data.get("AceptadoConObservacion")
            if estado_documento == 0: # En proceso
                status = 'E'
            elif estado_documento in [1, 2]: # Aceptado, Anulado
                status = 'A'
            elif estado_documento == 3: # Rechazado
                status = 'R'
            else:
                status = document.estado_emision
            if aceptado_con_observacion is True:
                status = 'O' # Aceptado con observacion
            data = {
                "status": status,
                "status_pecanofact": str(estado_documento),
                "sunat_observaciones": cdr_description
            }
            return data
        elif response.status_code in (400, 404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaCPE x NumeroDocumento): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")

# [ OBTENER: CUERPO DE LA CONSULTA DE DOCUMENTO ELECTRÓNICO (FACTURAS, BOLETAS Y NOTAS) ]
def get_request_check_invoice(log):
    """
        VALIDAR FACTURAS, BOLETAS Y NOTAS:
            Procesar y crear todos los valores necesarios para el objeto json
    """
    document = log.account_move_id
    if document.journal_id.electronic_invoice and (re.match(r"^F\w{3}-\d{1,8}$", document.name) or re.match(r"^B\w{3}-\d{1,8}$", document.name)) or re.match(r"\d{4}-\d{1,8}$", document.name) and document.invoice_type_code in ["01","03","07","08"]:
        vouchers = {
            '01': 10, # [ FACTURA ]
            '03': 20, # [ BOLETA ]
            '07': 30, # [ NOTA DE CRÉDITO ]
            '08': 40, # [ NOTA DE DÉBITO ]
        }
        body = {
            'TipoDocumento':vouchers.get(document.invoice_type_code,0),
            'FechaEmision': document.invoice_date.strftime("%Y-%m-%d") if document.invoice_date else "",
            'NumeroDocumento': document.name or "",     
        }
        return body
    else:
        raise UserError("El comprobante está configurado como un documento electrónico.")

# [ CONSULTAR / ACTUALIZAR : DOCUMENTO ELECTÓNICO (FACTURAS, BOLETAS Y NOTAS) ]
def get_invoice_files(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/archivo/documento"
        
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }

        body = get_request_check_invoice(document.current_log_status_id)

        response = requests.post(url, json=body, headers=headers, timeout=20)
        response_data = response.json()

        if response.status_code == 200:
            archivo_declaracion = response_data.get("ArchivoCpeDeclaracion", {}) or {}
            #identificador_anulacion = replace_false(response_data.get("IdentificadorAnulacion", ""))
            #archivo_anulacion = response_data.get("ArchivoCpeAnulacion", {})
            cdr_base64 = xml_base64 = pdf_base64 = ""
            if archivo_declaracion:
                for name in ['Cdr', 'Xml', 'Pdf']:
                    value = archivo_declaracion.get(name)
                    if not isinstance(value, dict):
                        value = {}
                    archivo_declaracion[name] = value
                cdr_base64 = replace_false(archivo_declaracion['Cdr'].get("ContenidoArchivo", ""))
                cdr_nombre = replace_false(archivo_declaracion['Cdr'].get("NombreArchivo", ""))
                xml_nombre = replace_false(archivo_declaracion['Xml'].get("NombreArchivo", ""))
                xml_base64 = replace_false(archivo_declaracion['Xml'].get("ContenidoArchivo", ""))
                pdf_base64 = replace_false(archivo_declaracion['Pdf'].get("ContenidoArchivo", ""))
            data = {
                "response_json": json.dumps(response_data, indent=4),
                "xml_name": xml_nombre,
                "xml_base64": xml_base64,
                # "digest_value": replace_false(response_data.get("digest_value","")),
                "signed_xml_data_without_format": (
                    base64.b64decode(xml_base64).decode("utf-8") if xml_base64 != "" else ""
                ),
                "signed_xml_data": (
                    parseString(base64.b64decode(xml_base64).decode("utf-8")).toprettyxml() if xml_base64 != "" else ""
                ),
                "signed_xml": pdf_base64,
                "cdr_name": cdr_nombre,
                "cdr_base64": cdr_base64,
                "response_content_xml": (
                    parseString(base64.b64decode(cdr_base64).decode("utf-8")).toprettyxml() if cdr_base64 != "" else ""
                ),
                "response_xml_without_format": (
                    base64.b64decode(cdr_base64).decode("utf-8") if cdr_base64 != "" else ""
                ),
                "date_request": fields.Datetime.now(),
                "log_observation_ids": [],
            }
            return data
                
        elif response.status_code in (400, 404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaArchivoCpe): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")

# [ OBTENER ENLACE PDF COMPROBANTES ]
def get_pdf_link_invoice(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test

        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/enlace/pdf"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }

        body = get_request_check_invoice(document.current_log_status_id)

        response = requests.post(url, json=body, headers=headers, timeout=20)
   
        response_data = response.json()

        if response.status_code == 200:
            enlace_pdf = response_data.get("EnlacePDF", "")
            return enlace_pdf
                
        elif response.status_code in (400,404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaEnlacePDF): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(e)
  
# [ CUERPO DEL ENVIO DE DOCUMENTO ELECTRÓNICO (FACTURAS, BOLETAS Y NOTAS) ]
# [ DOCUMENT : FACTURAS, BOLETAS Y NOTAS ]
def get_fecha_emision(document):
    invoice_date = document.invoice_date if document.invoice_date else fields.Date.context_today(document)

    now_local = fields.Datetime.context_timestamp(document, fields.Datetime.now())
    dt = datetime.combine(invoice_date, now_local.time())

    return dt

def get_fecha_vencimiento(document, emission_dt):
    invoice_date_due = document.invoice_date_due

    if not invoice_date_due:
        raise UserError("La fecha de vencimiento es obligatorio.")

    dt = datetime.combine(invoice_date_due, emission_dt.time())

    return dt

def get_fecha_pago_cuota(date_value):
    if not date_value:
        raise UserError("La fecha de vencimiento es obligatorio para cada cuota.")

    dt = datetime.combine(date_value, time(0, 0, 0))
    return dt.strftime('%Y-%m-%dT%H:%M:%S')

def get_request_invoice_body(document):
    customer = document.partner_id
    company = document.company_id
    vouchers = {
        '01': 10, # [ FACTURA ]
        '03': 20, # [ BOLETA ]
        '07': 30, # [ NOTA DE CRÉDITO ]
        '08': 40, # [ NOTA DE DÉBITO ]
    }
    affections = { 
        '10': 1, # [ GRAVADO - OPERACIÓN ONEROSA ]
        '11': 2, # [ GRAVADO - RETIRO POR PREMIO ]
        '12': 3, # [ GRAVADO - RETIRO POR DONACIÓN ]
        '13': 4, # [ GRAVADO - RETIRO ]
        '14': 5, # [ GRAVADO - RETIRO POR PUBLICIDAD ]
        '15': 6, # [ GRAVADO - BONIFICACIONES ]
        '16': 7, # [ GRAVADO - RETIRO POR ENTREGA A TRABAJADORES ]
        '17': 8, # [ GRAVADO - IVAP ] / [ 101 = IVAP Gratuito NO EXISTE EN ODOO ]
        '20': 9, # [ EXONERADO - OPERACIÓN ONEROSA ]
        '21': 10, # [ EXONERADO - TRANSFERENCIA GRATUITA ]
        '30': 11, # [ INAFECTO - OPERACIÓN ONEROSA ]
        '31': 12, # [ INAFECTO - RETIRO POR BONIFICACIÓN ]
        '32': 13, # [ INAFECTO - RETIRO ]
        '33': 14, # [ INAFECTO - RETIRO POR MUESTRAS MÉDICAS ]
        '34': 15, # [ INAFECTO - RETIRO POR CONVENIO COLECTIVO ]
        '35': 16, # [ INAFECTO - RETIRO POR PREMIO ]
        '36': 17, # [ INAFECTO - RETIRO POR PUBLICIDAD ]
        '37': 18, # [ INAFECTO - TRANSFERENCIA GRATUITA ]
        '40': 19, # [ EXPORTACIÓN ]
    }
    if document.invoice_type_code == '01':
        if not re.match(r"^F\w{3}-\d{1,8}$", document.name):
            raise UserError("El formato de la factura es incorrecto. Empieza con F para FACTURAS y NOTAS ASOCIADAS.")
    elif document.invoice_type_code == '03':
        if not re.match(r"^B\w{3}-\d{1,8}$", document.name):
            raise UserError("El formato de la boleta es incorrecto. Empieza con B para BOLETAS DE VENTA y NOTAS ASOCIADAS.")
    elif document.invoice_type_code == '07':
        if document.reversed_entry_id.invoice_type_code == '01':
            if not re.match(r"^F\w{3}-\d{1,8}$", document.name):
                raise UserError("El formato de la nota de crédito para la factura es incorrecto. Empieza con F para FACTURAS y NOTAS ASOCIADAS.")
        if document.reversed_entry_id.invoice_type_code == '03':
            if not re.match(r"^B\w{3}-\d{1,8}$", document.name):
                raise UserError("El formato de la nota de crédito para la boleta es incorrecto. Empieza con B para BOLETAS DE VENTA y NOTAS ASOCIADAS.")
    elif document.invoice_type_code == '08':
        if document.reversed_entry_id.invoice_type_code == '01':
            if not re.match(r"^F\w{3}-\d{1,8}$", document.name):
                raise UserError("El formato de la nota de débito para la factura es incorrecto. Empieza con F para FACTURAS y NOTAS ASOCIADAS.")
        if document.reversed_entry_id.invoice_type_code == '03':
            if not re.match(r"^B\w{3}-\d{1,8}$", document.name):
                raise UserError("El formato de la nota de débito para la boleta es incorrecto. Empieza con B para BOLETAS DE VENTA y NOTAS ASOCIADAS.")
    else:
        raise UserError("El tipo de documento del comprobante es obligatorio.")
    body = { }
    # [ DOCUMENTO: INFORMACIÓN GENERAL ]
    emision_dt = get_fecha_emision(document)
    vencimiento_dt = get_fecha_vencimiento(document, emision_dt)
    body.update({
        'NumeroDocumento': document.name,
        'FechaEmision': emision_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'Correo': replace_false(company.email),
        'TipoMoneda': int(document.currency_id.jnq_code_pecanofact),
        'TipoCambio': document.exchange_rate_sunat,
        'FechaVencimiento': vencimiento_dt.strftime('%Y-%m-%dT%H:%M:%S'),
    })
    # [ DOCUMENTO: EMISOR ]
    body.update({
        'Emisor':{
            'Ruc': replace_false(company.vat),
            'NombreComercial': replace_false(company.name),
            'RazonSocial': replace_false(company.name),
            'DomFiscalUbigeo': replace_false(company.partner_id.ubigeo),
            'DomFiscalDireccion': replace_false(company.street),
            'DomFiscalCodPais04': company.country_id.code or "PE",
            'CodLocalSunat': replace_false(company.l10n_pe_edi_address_type_code),
        }
    })
    # [ DOCUMENTO: CLIENTE ]
    body.update({
        'Cliente':{
            'TipoDocumentoIdentidad': int(customer.l10n_latam_identification_type_id.jnq_code_pecanofact),
            'ValorDocumentoIdentidad': replace_false(customer.vat),
            'RazonSocial': replace_false(customer.name),
            'Direccion': replace_false(customer.street),
        }
    })
    # [ DOCUMENTO: TOTALES ]
    amount_totals = document.get_amount_totals()
    total_global_discount = round(amount_totals.get('total_descuento_global',0.0), 2)
    body.update({
        'TotalValorVentaOpeGravada': document.currency_id.round(document.amount_untaxed) + total_global_discount,
        'Igv': document.currency_id.round(document.amount_tax),
        'ImporteTotal': document.currency_id.round(document.amount_total),
    })
    # [ DOCUMENTO: RETENCIONES ]
    if document.apply_retention:
        body.update({
            'PorcentajeRetencion': round(document.retention_rate/100, 2),
            'ImporteRetencion': round(document.amount_retention, 2),
        })
    # [ DOCUMENTO: DETRACCIONES ]
    if document.is_detraction:
        if document.round_amount_detraction:
            detraccion_soles = document.amount_detraction_signed_rounded
        else:
            detraccion_soles = document.amount_detraction_signed
        body.update({
            'BienServicioDetraccion': replace_false_number(document.detraction_id.jnq_code_pecanofact, int),
            'NumeroCuentaBNDetraccion': replace_false(document.register_detraction_id.national_bank_account_id.acc_number),
            'ImporteDetraccion':  detraccion_soles if int(document.currency_id.jnq_code_pecanofact) == 1 else document.amount_detraction,
            'ImporteDetraccionEnMN': detraccion_soles,
            'PorcentajeDetraccion': document.detraction_rate/100
        })
    # [ DOCUMENTO: DESCUENTO GLOBAL ]
    if document.invoice_type_code not in ["07","08"]:
        global_discount_percentage = round(amount_totals.get('porcentaje_descuento_global',0.0), 2)
        total_global_discount_igv = round(amount_totals.get('total_descuento_global_con_igv',0.0), 2)
        body.update({
            'PorcentajeDescuentoGlobal': global_discount_percentage,
            'ImporteDescuentoGlobal': total_global_discount,
            'ImporteDescuentoGlobalConIgv': total_global_discount_igv,
        })
    # [ DOCUMENTO: NOTA DE CRÉDITO / NOTA DE DÉBITO ]
    if document.invoice_type_code in ["07","08"]:
        reversed_entry = document.reversed_entry_id if document.invoice_type_code == '07' else document.debit_origin_id
        reversed_entry_date = reversed_entry.invoice_date
        reversed_entry_date_due = reversed_entry.invoice_date_due
        reversed_entry_date_dt = datetime.combine(reversed_entry_date, time(0, 0, 0))
        reversed_entry_date_due_dt = datetime.combine(reversed_entry_date_due, time(0, 0, 0))

        body.update({
            'FechaEmisionDocReferencia': reversed_entry_date_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'FechaVencimientoDocReferencia': reversed_entry_date_due_dt.strftime('%Y-%m-%dT%H:%M:%S'),
            'TipoComprobanteReferencia': vouchers.get(reversed_entry.invoice_type_code, 0),
            'NumeroDocumentoReferencia': replace_false(reversed_entry.name) 
        })
        if document.invoice_type_code == '07':
            credit_type = {
                '01': 1, # [ ANULACIÓN DE LA OPERACIÓN ]
                '02': 2, # [ ANULACIÓN POR ERROR EN EL RUC ]
                '03': 3, # [ CORRECCIÓN POR ERROR EN LA DESCRIPCIÓN ]
                '04': 4, # [ DESCUENTO GLOBAL ]
                '05': 5, # [ DESCUENTO POR ÍTEM ]
                '06': 6, # [ DEVOLUCIÓN TOTAL ]
                '07': 7, # [ DEVOLUCIÓN POR ÍTEM ]
                '08': 8, # [ BONIFICACIÓN ]
                '09': 9, # [ DISMINUCIÓN EN EL VALOR ]
                '10': 10, # [ OTROS CONCEPTOS ]
                '11': 12, # [ AJUSTES DE OPERACIONES DE EXPORTACIÓN ]
                '12': 11, # [ AJUSTES AFECTOS AL IVAP ]
                '13': 13  # [ AJUSTES - MONTOS Y/O FECHAS DE PAGO ]
            }
            body.update({
                'TipoNotaCredito': credit_type.get(document.tipo_nota_credito, 0),
                'MotivoNotaCredito': replace_false(document.sustento_nota)
            })
        # else:
        #     debit_type = {
        #         '01': 1, # [ INTERESES POR MORA ]
        #         '02': 2, # [ AUMENTO DE VALOR ]
        #         '03': 3, # [ PENALIDADES / OTROS CONCEPTOS ]
        #         '11': 5, # [ AJUSTES DE OPERACIONES DE EXPORTACIÓN ]
        #         '12': 4  # [ AJUSTES AFECTOS AL IVAP ]
        #     }
        #     body.update({'tipo_de_nota_de_debito': debit_type.get(document.tipo_nota_debito,0)})
    # [ DOCUMENTO: ADICIONALES ]
    # [ Observacion de venta ]
    #accounts_text = "Scotia: 000-4231023  CCI: 00917000000423102325 | BCP: 193-2451201-0-05 CCI:00219300245120100519 | BN Detracción: 00-058-244341"
    base_text = replace_false(document.sunat_observacion_venta) or ""
    #full_text = f"{base_text}\n{accounts_text}" if base_text else accounts_text
    #observacion_final = full_text[:100]
    body.update({
        'TipoOperacion': document.invoice_type_code_catalog_51.code, #campo nativo l10n_pe_edi_operation_type
        'ObservacionVenta': base_text
    })
    sale_order_reference = replace_false(document.sale_order_reference)
    if sale_order_reference:
        body.update({
            'NumeroOrdenCompra': sale_order_reference, 
        })
    # [ DOCUMENTO: PAGOS ]
    payment_term = document.invoice_payment_term_type
    body.update({
        'TipoCondicionVenta': 2 if payment_term == 'Credito' else 1, # 1 (contado), 2 (credito)        
    })
    # [ DOCUMENTO: VENTA AL CRÉDITO ]
    if payment_term == 'Credito':
        credits,i = [],1
        total_cuotas = 0
        for paymentterm in document.paymentterm_line:
            credits.append({
                'NumeroCuota': i,
                'FechaPagoCuota': get_fecha_pago_cuota(paymentterm.date_due),
                'ImporteCuota': paymentterm.amount
            })
            i = i + 1
            total_cuotas += paymentterm.amount
        body.update({
            'FormaPago': document.invoice_payment_term_id.name if document.invoice_payment_term_id else "",
            'DetalleCredito': credits,
            'MontoNetoPendientePago': round(total_cuotas, 2)
        })
    # [ DOCUMENTO: DOCUMENTOS RELACIONADOS ]
    # [ GUIAS DE REMISION ]
    guides = []
    for i, item in enumerate(document.guia_remision_ids, start=1):
        # 70 : Remitente
        # 80: Transportista
        guides.append({
            'IdItem': i,
            'TipoGuiaRemisionRelacionada': 70 if item.gre_type == 'remitente' else 80,
            'NumeroGuiaRemisionRelacionada': item.name
        })
    if guides:
        body.update({'GuiaRelacionadaFactura': guides})
    # [ DOCUMENTO: CUENTAS DE ABONO ]
    bank_accounts = []
    for bank_account in document.partner_bank_ids:
        bank_accounts.append({
            'Banco': replace_false(bank_account.bank_id.name),
            'Moneda': replace_false(bank_account.currency_id.name),
            'NumeroCuentaCorriente': bank_account.acc_number,
            'CodigoCuentaInterbancaria': bank_account.interbank_acc_number
        })
    body.update({'CuentasCorrientes': bank_accounts})
    # [ DOCUMENTO: ITEMS ]
    items = []
    # [ LINEAS FACTURABLES ]
    # (1) LINEAS DE PRODUCTOS Y SERVICIOS QUE PUEDEN SER VENDIDOS (SI)
    # (2) LINEAS DE IMPUESTO POR CONSUMO DE BOLSAS DE PLÁSTICO (NO)
    # (3) LINEAS POR CUPONES Y PROMOCIONES (NO)
    # [ ¿PRODUCTOS QUE SON CUPONES O PROMOCIONES? ]
    #coupons_promotions = document.env['loyalty.program'].sudo().search([]).reward_ids.discount_line_product_id    
    lines = document.invoice_line_ids.filtered(lambda r: r.display_type == 'product' and r.product_id != r.company_id.sale_discount_product_id)
    #coupon_promotion_items = lines.filtered(lambda r: r.product_id.id in coupons_promotions.ids)
    #billable_items = lines.filtered(lambda r: r.id not in coupon_promotion_items.ids)
    for i, item in enumerate(lines, start=1):
        amounts_item = get_amounts_items(item)
        move = item.move_id
        invoice_type_code = move.invoice_type_code
        # [ ITEMS: INFORMACIÓN DEL PRODUCTO ]
        line = {
            'IdItem': i,
            'CodigoProducto': replace_false(item.product_id.default_code),
            'UnidadMedida': replace_false(item.product_uom_id.l10n_pe_edi_measure_unit_code.code) if item.product_id.type != 'service' else 'ZZ',
        }
        product_description = replace_false(item.product_id.name)[0:500].strip().replace("\n", " ")
        if invoice_type_code in ['01', '03']:
            line.update({'Descripcion': product_description})
        else:
            line.update({'DescripcionProducto': product_description})
        # [ ITEMS: LOTES ]
        #DetalleLoteProducto
        # [ ITEMS: MONTOS BASE ]
        price_unit = item.currency_id.round(amounts_item.get('unit_price',0))/ round(item.quantity, 10)
        discount_percentage = amounts_item.get('discount_percentage',0)
        line.update({
            'Cantidad': abs(round(item.quantity, 10)),
            #'ValorUnitario': round(abs(amounts_item.get('unit_value', 0) / (item.quantity or 1)), 10),
            'ValorUnitario': round(abs(item.price_unit), 10),
            'PrecioUnitario': round(abs(price_unit)*(1-discount_percentage), 10),
            #'PorcentajeDescuento': discount_percentage,
            #'ImporteDescuento': item.currency_id.round(amounts_item.get('discount_amount',0)),
            'PorcentajeIgv': amounts_item.get('percentage_igv',0),
        })
        if invoice_type_code in ['01', '03']:
            line.update({
                'PorcentajeDescuento': discount_percentage,
                'ImporteDescuento': item.currency_id.round(amounts_item.get('discount_amount',0)),
            })
        # [ ITEMS: IMPUESTOS ]
        line.update({ 
            'TipoAfectacionIgv': affections.get(amounts_item.get('type_igv',0),''),
            'Igv': item.currency_id.round(amounts_item.get('igv',0)),
        })
        # [ ITEMS: TOTALES]
        line.update({
            'ValorVenta': abs(item.currency_id.round(amounts_item.get('subtotal',0))),
            'Total': abs(item.currency_id.round(amounts_item.get('total',0))),
        })
        items.append(line)
    if document.invoice_type_code == "01":
        body.update({'DetalleFactura': items })
    elif document.invoice_type_code == "03":
        body.update({'DetalleBoleta': items })
    elif document.invoice_type_code == "07":
        body.update({'DetalleNotaCredito': items })
    return body

# [ CONSULTAR ESTADO : BAJA ]
def get_low_status(document):
    try:
        token = document.get_token_pecanofact()
        company_id = document.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/estado/documento"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }
        body = get_request_check_invoice(document.current_log_status_id)
        response = requests.post(url, json=body, headers=headers, timeout=20)
        # SI TOKEN EXPIRÓ
        if response.status_code == 401:
            token = company_id.pecano_generate_token()
            headers["TOKEN-PSE-PECANOFACT"] = token
            response = requests.post(url, json=body, headers=headers, timeout=20)
        try:
            response_data = response.json()
        except Exception:
            raise UserError("Respuesta inválida de PecanoFact")
        if response.status_code == 200:
            estado_documento = response_data.get("EstadoDocumento")
            cdr_description = response_data.get("DescripcionCdrDeclaracion") or ""
            aceptado_con_observacion = response_data.get("AceptadoConObservacion")
            if estado_documento == 0: # En proceso
                status = 'E'
            elif estado_documento in [1, 2]: # Aceptado, Anulado
                status = 'A'
            elif estado_documento == 3: # Rechazado
                status = 'R'
            else:
                status = document.estado_emision
            if aceptado_con_observacion is True:
                status = 'O' # Aceptado con observacion
            data = {
                "status": status,
                "status_pecanofact": str(estado_documento),
                "sunat_observaciones": cdr_description
            }
            return data
        elif response.status_code in (400, 404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaCPE x NumeroDocumento): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")
    
# [ ENVIAR / CONSULTAR / ACTUALIZAR : DOCUMENTOS DE BAJA (OPCIONAL) ]
# [ LOG: LOG ACTUAL DE LA LISTA DE LOG DEL DOCUMENTO DE BAJA ]
def get_log_status_anulacion(log):
    try:
        token = log.get_token_pecanofact()
        company_id = log.company_id
        pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
        url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/archivo/documento"
        headers = {
            "Content-Type": "application/json",
            "TOKEN-PSE-PECANOFACT": token,
        }

        body = get_request_check_invoice(log)

        response = requests.post(url, json=body, headers=headers, timeout=20)
   
        response_data = response.json()

        if response.status_code == 200:
            estado_documento = response_data.get("EstadoDocumento", "")
            archivo_declaracion = response_data.get("ArchivoCpeDeclaracion", {}) or {}
            #identificador_anulacion = replace_false(response_data.get("IdentificadorAnulacion", ""))
            #archivo_anulacion = response_data.get("ArchivoCpeAnulacion", {})
            cdr_base64 = xml_base64 = pdf_base64 = ""
            if archivo_declaracion:
                for name in ['Cdr', 'Xml', 'Pdf']:
                    value = archivo_declaracion.get(name)
                    if not isinstance(value, dict):
                        value = {}
                    archivo_declaracion[name] = value
                cdr_base64 = replace_false(archivo_declaracion['Cdr'].get("ContenidoArchivo", ""))
                xml_base64 = replace_false(archivo_declaracion['Xml'].get("ContenidoArchivo", ""))
                pdf_base64 = replace_false(archivo_declaracion['Pdf'].get("ContenidoArchivo", ""))
            status = 'E'
            if estado_documento == 0: #En proceso
                status = 'E'
            elif estado_documento == 1: #Aceptado
                status = 'A'
            elif estado_documento == 3: #Rechazado
                status = 'R'

            data = {
                "response_json": json.dumps(response_data, indent=4),
                "digest_value": replace_false(response_data.get("digest_value","")),
                "signed_xml_data_without_format": (
                    base64.b64decode(xml_base64).decode("utf-8") if xml_base64 != "" else ""
                ),
                "signed_xml_data": (
                    parseString(base64.b64decode(xml_base64).decode("utf-8")).toprettyxml() if xml_base64 != "" else ""
                ),
                "signed_xml": pdf_base64,
                "response_content_xml": (
                    parseString(base64.b64decode(cdr_base64).decode("utf-8")).toprettyxml() if cdr_base64 != "" else ""
                ),
                "response_xml_without_format": (
                    base64.b64decode(cdr_base64).decode("utf-8") if cdr_base64 != "" else ""
                ),
                "status": status,
                "status_pecanofact": str(estado_documento),
                "date_request": fields.Datetime.now(),
                "log_observation_ids": [],
            }
            return data
                
        elif response.status_code in (400,404):
            error = response_data.get("MensajeError", "Error desconocido")
            raise UserError(f"Error de validación o estructura: {error}")
        elif response.status_code == 500:
            code_error = response_data.get("CodigoError", "Error desconocido")
            raise UserError(f"Error interno del servidor PSE PecanoFact (ConsultaArchivoCpe): {code_error}")
        else:
            raise UserError(f"Respuesta HTTP inesperada ({response.status_code})")
        
    except requests.exceptions.Timeout:
        raise UserError("Tiempo de espera agotado al consultar PecanoFact.")
    except requests.exceptions.ConnectionError:
        raise UserError("No se pudo conectar con el servidor de PecanoFact.")
    except Exception as e:
        raise UserError(f"Error inesperado al consultar PecanoFact: {e}")
    
def update_low(response,low,body):
    data = {
        "request_json":json.dumps(body,indent=4), # Contenido de Comprobante en JSON
        "name": "{} {}".format('COMUNICACIÓN DE BAJA - ',str(low.id)), # Nombre
        "date_request": fields.Date.today(),
        "date_issue": low.date_invoice, # Fecha de Emisión a SUNAT
        "account_voided_id":low.id, # Comunicación de baja
        "status":"P", # Estado ( P = PENDIENTE DE ENVÍO A LA SUNAT ),
        "company_id":low.company_id.id, # Compañía
        "submitted_pecanofact": True if low.company_id.sunat_provider == 'pecanofact' else False,
        #"voided_ticket": replace_false(response.get('sunat_ticket_numero','')), # Ticket de anulación
    }
    return data

# [ OBTENER: CUERPO DE LA CONSULTA DEL ENVIO DE COMUNICACIÓN DE BAJA DE DOCUMENTO ELECTRÓNICO (FATURAS, BOLETAS Y NOTAS) ]
# [ LOW: DOCUMENTO DE BAJA ]
def get_request_baja_document_body(low):
    """
        GENERAR COMUNICACIÓN DE BAJA PARA FACTURAS, BOLETAS Y NOTAS:
            Procesar y crear todos los valores necesarios para el objeto json
    """
    vouchers = {
        '01': 10, # [ FACTURA ]
        '03': 20, # [ BOLETA ]
        '07': 30, # [ NOTA DE CRÉDITO ]
        '08': 40, # [ NOTA DE DÉBITO ]
        '09': 70, # [ GRE REMITENTE ]
        '31': 80  # [ GRE TRANSPORTISTA ]
    }
    invoices = low.invoice_ids
    body = []
    for document in invoices:
        body.append({
            'RucEmisor': replace_false(document.company_id.vat),
            'NumeroDocumento': replace_false(document.name),
            'TipoDocumento': vouchers.get(document.invoice_type_code,0),
            'MotivoBaja': low.motivo,
        })        
    return body