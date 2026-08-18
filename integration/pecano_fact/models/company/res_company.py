# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api, _
from datetime import timedelta
from odoo.fields import Datetime
import requests

class UnauthenticatedError(Exception):
    def __init__(self, message="Token inválido o expirado"):
        super().__init__(message)

class ResCompany(models.Model):
    _inherit = "res.company"

    sunat_provider = fields.Selection(selection_add=[("pecanofact", "PecanoFact")])  
    pecano_base_url_prod = fields.Char(string="URL base(producción)", tracking=True)
    pecano_key_comercio_prod = fields.Char(string="Key comercio(producción)", tracking=True)
    pecano_base_url_test = fields.Char(string="URL base(pruebas)", tracking=True)
    pecano_key_comercio_test = fields.Char(string="Key comercio(pruebas)", tracking=True)
    pecano_token = fields.Char(string='Token')
    pecano_token_date = fields.Datetime()


    def pecano_generate_token(self):
        self.ensure_one()

        # Parametros obligatorios
        base_url = ""
        ruc_comercio = self.vat
        key_comercio = ""
        if self.electronic_invoicing_type_environment == '1':
            base_url = self.pecano_base_url_prod
            key_comercio = self.pecano_key_comercio_prod
        elif self.electronic_invoicing_type_environment == '0':
            base_url = self.pecano_base_url_test
            key_comercio = self.pecano_key_comercio_test

        if not base_url:
            raise UserError(_(f"La URL base para el proveedor PecanoFact no está configurado en la compañía {self.name}"))
        if not ruc_comercio:
            raise UserError(_(f"El número de RUC de la compañía {self.name} no está configurado."))
        if not key_comercio:
            raise UserError(_(f"El key comercio para el proveedor PecanoFact no está configurado en la compañía {self.name}"))
        
        url = f"{base_url.rstrip('/')}/api/v2/generarToken?ruc={ruc_comercio}"
        headers = {"KEY_COMERCIO": key_comercio}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            body = response.json()
        except Exception as e:
            raise ValidationError(_("Error al conectar con el servicio de PecanoFact: %s") % str(e))

        token = body.get("Token")
        if not token:
            error_code = body.get("CodigoError","")
            error_description = body.get("MensajeError", "No se pudo generar el token PecanoFact")
            raise ValidationError(
                _("Código Error: %s; descripción: %s") % (error_code, error_description)
            )
        self.sudo().write({
            'pecano_token' : token,
            'pecano_token_date': fields.Datetime.now()
        })
        return token
    
    def get_token_pecanofact(self):
        self.ensure_one()

        if self.pecano_token and self.pecano_token_date:
            expiration_time = self.pecano_token_date + timedelta(seconds=3500)

            if Datetime.now() < expiration_time:
                return self.pecano_token

        return self.pecano_generate_token()

    # def set_token_pecanofact(self):
    #     self.pecano_token = self.pecano_generate_token()

class JNQResCurrency(models.Model):
    
    _inherit = 'res.currency'
    
    jnq_code_pecanofact = fields.Char('Código PecanoFact')