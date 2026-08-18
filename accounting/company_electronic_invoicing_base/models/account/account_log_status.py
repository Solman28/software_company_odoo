from odoo import api, models, fields
#from . import oauth
import requests
import json
from odoo.exceptions import UserError, ValidationError
# from odoo.addons.gestionit_pe_fe.models.account.oauth import request_status_ticket,request_status_invoice
import logging
import urllib
import re
from xml.dom.minidom import parse, parseString
_logger = logging.getLogger(__name__)

estado_comprobante_electronico = {
    "0":"0_NO_EXISTE",
    "1":"1_ACEPTADO",
    "2":"2_ANULADO",
    "3":"3_AUTORIZADO",
    "4":"4_NO_AUTORIZADO"
}
estado_contribuyente_ruc = {
    "00":"00_ACTIVO",
    "01":"01_BAJA_PROVISIONAL",
    "02":"02_BAJA_PROV_POR_OFICIO",
    "03":"03_SUSPENSION_TEMPORAL",
    "10":"10_BAJA_DEFINITIVA",
    "11":"11_BAJA_DE_OFICIO",
    "22":"22_INHABILITADO-VENT.UNICA"
}

condicion_domicilio_contribuyente = {
    "00":"00_HABIDO",
    "09":"09_PENDIENTE",
    "11":"11_POR_VERIFICAR",
    "12":"12_NO_HABIDO",
    "20":"20_NO_HALLADO"
}

class AccountLogStatusObservation(models.Model):
    _name = "account.log.status.observation"
    _description = "Observaciones de envíos"

    code = fields.Char("Observación")
    description = fields.Char("Descripción")
    account_log_status_id = fields.Many2one("account.log.status")

class AccountLogStatus(models.Model):
    _name = "account.log.status"
    _order = "create_date desc"
    _description = "Registro de envío de comprobantes"

    name = fields.Char("Nombre")
    is_last_log = fields.Boolean("Activo", default=False)
    #api_user_id = fields.Char("API User id")
    #content_xml = fields.Text("Respuesta de SUNAT base64 ZIP")
    #description = fields.Char("Descripción")
    #response_xml = fields.Text("Respuesta de SUNAT - Formateado")
    request_json = fields.Text("Contenido de Comprobante en JSON")
    signed_xml = fields.Text("Envío de comprobante ZIP en base64")
    response_json = fields.Text("Respuesta del API")
    unsigned_xml = fields.Text("Comprobante sin Firmar")
    xml_name = fields.Char("XML Nombre Archivo")
    xml_base64 = fields.Text("Comprobante XML Base 64")
    signed_xml_data = fields.Text("Comprobante XML Firmado - Formateado")
    signed_xml_with_creds = fields.Text("XML con Credenciales")
    signed_xml_data_without_format = fields.Text("Comprobante XML Firmado")
    cdr_name = fields.Char("CDR Nombre Archivo")
    cdr_base64 = fields.Text("Respuesta de Sunat - CDR Base 64")
    response_content_xml = fields.Text("Respuesta de SUNAT - Formateado")
    response_xml_without_format = fields.Text("Respuesta de Sunat - CDR")
    log_observation_ids= fields.One2many("account.log.status.observation", "account_log_status_id")
    status = fields.Selection(
        string="Estado de envío a SUNAT",
        selection=[
            ('A', 'Aceptado'),
            ('E', 'Enviado a SUNAT'),
            ('N', 'Envio Erróneo'),
            ('O', 'Aceptado con Observación'),
            ('R', 'Rechazado'),
            ('P', 'Pendiente de envió a SUNAT')
        ]
    )
    sunat_observaciones = fields.Text('SUNAT observaciones', help='Cuando hay errores en la SUNAT se describirá el error')
    date_request = fields.Date("Fecha de Envío a SUNAT")  # Fecha en que el comprobante es enviado electrónicamente a SUNAT.
    date_issue = fields.Date("Fecha de Emisión a SUNAT")  # Fecha en que nace el comprobante tributariamente.
    api_request_id = fields.Char("Identificador de Envío")
    digest_value = fields.Char("Digest Value")
    account_move_id = fields.Many2one("account.move", string="Comprobante")
    company_id = fields.Many2one("res.company",string="Compañia",required=True)
    document_type = fields.Selection(
        string="Tipo de comprobante", 
        selection=[
            ("01","Factura"),
            ("03","Boleta"),
            ("07","Nota de crédito"),
            ("08","Nota de débito"),
            ("RC","Resumen de venta"),
            ("RA","Comunicación de Baja")
        ]
    )
    # [ Comunicación de baja ]
    account_voided_id = fields.Many2one("account.comunicacion_baja","Comunicación de baja")
    voided_ticket = fields.Char("Ticket de anulación")
    voided_submission_response_xml = fields.Char("Respuesta de envío de anulación")
    # [ Resumen diario ]
    summary_ticket = fields.Char(string="Ticket de Resumen")
    account_summary_sequence = fields.Integer(string="Resumen - Sec. de envío del día")
    account_summary_id = fields.Many2one("account.summary", string="Resumen Diario")
    summary_submission_response_xml = fields.Char(string="Respuesta de envío de resumen")
    summary_code_response = fields.Char(string="Código de respuesta de resumen")
    summary_description_response = fields.Char(string="Descripción de respuesta de resumen")
    # [ GRE ]
    guia_remision_id = fields.Many2one("guia.remision", string="Guía de Remisión")

    def action_set_last_log_unlink(self):
        self.ensure_one()
        if self.account_move_id:
            self.account_move_id.current_log_status_id = False
            self.is_last_log = False
        elif self.guia_remision_id:
            self.guia_remision_id.current_log_status_id = False
            self.is_last_log = False
        elif self.account_summary_id:
            self.account_summary_id.current_log_status_id = False
            self.is_last_log = False
        elif self.account_voided_id:
            self.account_voided_id.current_log_status_id = False
            self.is_last_log = False

    def action_set_last_log(self):
        self.ensure_one()
        if self.account_move_id:
            self.account_move_id.account_log_status_ids.filtered(lambda log: log != self and log.is_last_log).write({'is_last_log':False})
            self.is_last_log = True
            self.account_move_id.current_log_status_id = self.id
        elif self.guia_remision_id:
            self.guia_remision_id.account_log_status_ids.filtered(lambda log: log != self and log.is_last_log).write({'is_last_log':False})
            self.is_last_log = True
            self.guia_remision_id.current_log_status_id = self.id
        elif self.account_summary_id:
            self.account_summary_id.account_log_status_ids.filtered(lambda log: log != self and log.is_last_log).write({'is_last_log':False})
            self.is_last_log = True
            self.account_summary_id.current_log_status_id = self.id
        elif self.account_voided_id:
            self.account_voided_id.account_log_status_ids.filtered(lambda log: log != self and log.is_last_log).write({'is_last_log':False})
            self.is_last_log = True
            self.account_voided_id.current_log_status_id = self.id
        
    # def action_request_status_ticket_summary(self):
    #     self.ensure_one()
    #     if self.summary_ticket:
    #         company = self.company_id
    #         response = request_status_ticket(company.sunat_provider,company.get_username_sunat(),company.sunat_pass,self.summary_ticket,self.company_id.tipo_envio)
    #         self.write({
    #             "response_xml_without_format":response.get("cdr",False) if response.get("cdr",False) else self.response_xml_without_format,
    #             "summary_description_response":response.get("description",False) if response.get("description",False) else self.summary_description_response,
    #             "summary_code_response":response.get("code",False) if response.get("code",False) else self.summary_description_response,
    #             "status":response.get("status",False) if response.get("status",False) else self.status
    #         })
    #     else:
    #         raise UserError("El campo ticket se encuentra vacío.")
    #     return response

    # def action_request_status_ticket_voided(self):
    #     self.ensure_one()
    #     if self.voided_ticket:
    #         company = self.company_id
    #         response = request_status_ticket(company.sunat_provider,company.get_username_sunat(),company.sunat_pass,self.voided_ticket,self.company_id.tipo_envio)
    #         self.write({
    #             "response_xml_without_format":response.get("cdr",False) if response.get("cdr",False) else self.response_xml_without_format,
    #             # "summary_description_response":response.get("description",False) if response.get("description",False) else self.summary_description_response,
    #             # "summary_code_response":response.get("code",False) if response.get("code",False) else self.summary_description_response,
    #             "status":response.get("status",False) if response.get("status",False) else self.status
    #         })
    #     else:
    #         raise UserError("El campo ticket se encuentra vacío.")
    #     return response

    def action_request_status_invoice(self):
        account_move_id = self.account_move_id
        if account_move_id and account_move_id.state == "posted":
            self._request_api_check_invoice_validity()
            # if account_move_id.invoice_type_code == "01" or account_move_id.journal_id.tipo_comprobante_a_rectificar == "01":
            #     self._request_cdr_invoice()
            # elif account_move_id.invoice_type_code == "03" or account_move_id.journal_id.tipo_comprobante_a_rectificar == "03":
            #     self._request_api_check_invoice_validity()

    # def _request_cdr_invoice(self):
    #     self.ensure_one()
    #     if self.account_move_id:
    #         if self.account_move_id.state == "posted" and \
    #             (self.account_move_id.invoice_type_code == "01" or self.account_move_id.journal_id.tipo_comprobante_a_rectificar == "01"):
    #             company = self.company_id
    #             # _logger.info(company)
    #             result = request_status_invoice(company.get_username_sunat(),company.sunat_pass,company.vat,self.account_move_id.invoice_type_code,self.account_move_id.name)
    #             response_json = json.loads(result.get("response_json","{}"))
    #             if response_json.get("status",False) == "A":
    #                 self.account_move_id.estado_comprobante_electronico = "1_ACEPTADO"

    #             if len(response_json.get("errors",[])) > 0:
    #                 raise UserError("\n".join(["* [{}] {}".format(err.get("code"),err.get("detail")) for err in response_json.get("errors",[])]))
    #             return result

    def _get_token_validez_comprobante(self):
        client_id = self.env["ir.config_parameter"].get_param("sunat.validez.comprobante.client_id")
        client_secret = self.env["ir.config_parameter"].get_param("sunat.validez.comprobante.client_secret")

        if not (client_id and client_secret):
            raise UserError("Las credenciales del api de CONSULTA VALIDEZ DE COMPROBANTE no estan configuradas para este usuario.")
        
        url = "https://api-seguridad.sunat.gob.pe/v1/clientesextranet/{}/oauth2/token/".format(client_id)

        data = {"grant_type":"client_credentials",
                "scope":"https://api.sunat.gob.pe/v1/contribuyente/contribuyentes",
                "client_id":client_id,
                "client_secret":client_secret}
        payload = urllib.parse.urlencode(data)
        headers = {'Content-Type': "application/x-www-form-urlencoded",
                    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'}

        try:
            response = requests.request("POST",url, data=payload, headers=headers)
        except Exception as e:
            raise UserError("Error al consultar el Web Service de SUNAT {}".format(e))
        
        if response.status_code == 200:
            return response.json()
        else:
            return {}

    def _request_api_check_invoice_validity(self):
        token = False
        response = self._get_token_validez_comprobante()
        if "access_token" in response:
            token = response.get("access_token")
        else:
            raise UserError("Las credenciales de consulta validez de comprobantes son incorrectas.")
        
        company = self.account_move_id.company_id
        url = "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes/{}/validarcomprobante".format(company.vat)
        
        if self.account_move_id.journal_id.electronic_invoice and \
            (re.match(r"^F\w{3}-\d{1,8}$", self.account_move_id.name) or re.match(r"^B\w{3}-\d{1,8}$", self.account_move_id.name)) or re.match(r"\d{4}-\d{1,8}$", self.account_move_id.name) and \
            self.account_move_id.invoice_type_code in ["01","03","07","08"]:

            if hasattr(self.account_move_id, 'is_contingencia') and self.account_move_id.is_contingencia:
                comp = self.account_move_id.mapped(lambda r:{
                    "numRuc":company.vat,
                    "codComp":r.journal_id.invoice_type_code_id,
                    "numeroSerie":r.name.split("-")[0],
                    "numero":int(r.name.split("-")[1]),
                    "fechaEmision":r.invoice_date.strftime("%d/%m/%Y")
                })
            else:
                comp = self.account_move_id.mapped(lambda r:{
                    "numRuc":company.vat,
                    "codComp":r.journal_id.invoice_type_code_id,
                    "numeroSerie":r.name.split("-")[0],
                    "numero":int(r.name.split("-")[1]),
                    "fechaEmision":r.invoice_date.strftime("%d/%m/%Y"),
                    "monto": str(round(r.amount_total,2)) 
                })

            headers = {
                'Authorization': "Bearer {}".format(token),
                'Content-Type': "application/json"
                }
            try:
                response = requests.request("POST", url, data=json.dumps(comp[0]), headers=headers)
                res = response.json()
                # _logger.info(res)
                if "data" in res and res.get("success"):
                    data = res["data"]
                    if "estadoCp" in data:
                        self.account_move_id.estado_comprobante_electronico = estado_comprobante_electronico[data["estadoCp"]]
                    if "estadoRuc" in data:
                        self.account_move_id.estado_contribuyente_ruc = estado_contribuyente_ruc[data["estadoRuc"]]
                    if "condDomiRuc" in data:
                        self.account_move_id.condicion_domicilio_contribuyente = condicion_domicilio_contribuyente[data["condDomiRuc"]]
                    
                    self.account_move_id.consulta_validez_observaciones = ";".join(data.get("observaciones",[]))
                else:
                    self.account_move_id.consulta_validez_observaciones = res.get("message","**Error**")
            except Exception as e:
                self.account_move_id.consulta_validez_observaciones = str(e)
        else:
            raise UserError("Asegúrese de que el comprobante esta configurado como un documento electrónico.")
