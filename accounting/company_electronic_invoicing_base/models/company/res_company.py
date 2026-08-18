# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"

    electronic_invoicing_type_environment = fields.Selection(string="Tipo de envío", selection=[("0", "0 - Pruebas"), ("1", "1 - Producción")], default="0")
    sunat_provider = fields.Selection(string="Proveedor", selection=[("sunat","SUNAT")], default="sunat")
    # [ Consulta validez cpe ]
    sunat_client_id = fields.Char(string="Client ID")
    sunat_client_secret = fields.Char(string="Client Secret")
    validate_cpe_token_url = fields.Char(string="Token URL")
    validate_cpe_url = fields.Char(string="URL de consulta")
    # [ Retenciones ]
    retention_account_id = fields.Many2one('account.account', string='Cuenta de retención', domain=[('deprecated', '=', False)])
    retention_journal_id = fields.Many2one('account.journal', string='Diario')
    # [ Detracciones ]
    default_national_bank_account_id = fields.Many2one(
        "res.partner.bank", string="Cuenta de detracciones del Banco de la Nación", 
    )

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    retention_account_id = fields.Many2one('account.account',string='Cuenta de retención',related="company_id.retention_account_id",readonly=False,domain=[('deprecated', '=', False)])
    retention_journal_id = fields.Many2one('account.journal',string='Diario',related="company_id.retention_journal_id",readonly=False)