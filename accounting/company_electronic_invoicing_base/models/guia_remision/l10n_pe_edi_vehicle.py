# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api


class L10nPeEdiVehicle(models.Model):
    _inherit = "l10n_pe_edi.vehicle"

    is_public_vehicle = fields.Boolean(string="Es vehículo público")
    transporte_partner_id = fields.Many2one('res.partner', string="Empresa")
    mtc_ids = fields.Many2many(
        'res.partner.mtc',
        domain="[('partner_id', '=', transporte_partner_id)]",
        string="Número de Autorización Especial (Documento que autoriza la ruta)",
        help="El número de autorización especial del vehículo"
    )
    tuce_chv = fields.Char(string="TUCE o CHV", help="Número de TUCE o Certificado de Habiltación Vehicular")