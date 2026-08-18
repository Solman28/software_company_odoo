# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    ubigeo = fields.Char(string='Ubigeo', readonly=True)
    is_transport_company = fields.Boolean(string="Es empresa de transporte?", tracking=True)
    is_driver = fields.Boolean(string="Es Conductor", tracking=True)
    is_headquarters = fields.Boolean(string="Es una sede?", tracking=True)
    # [ MTC ]
    mtc_ids = fields.One2many('res.partner.mtc', 'partner_id', string="Registro MTC")
    # [ Retenciones ]
    is_retention_agent = fields.Boolean(string='Agente de retención')
    retention_percentage = fields.Selection([('3','Tasa 3%'),('6','Tasa 6%'),('0','-')], string='Retención(%)', default='0')

    @api.onchange('l10n_pe_district')
    def _onchange_district(self):
        if self.l10n_pe_district:
            self.ubigeo = self.l10n_pe_district.code or ''
        else:
            self.ubigeo = ''
    
    @api.onchange('is_retention_agent')
    def _onchange_retention_agent(self):
        for record in self:
            if not record.is_retention_agent:
                record.retention_percentage = '0'