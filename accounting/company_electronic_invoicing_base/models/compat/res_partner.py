# -*- coding: utf-8 -*-
# Campos que en la versión original venían de Enterprise "l10n_pe_edi_stock"
# (datos de conductor / transportista para la Guía de Remisión Electrónica).
from odoo import fields, models
from .l10n_pe_edi_vehicle import ISSUING_ENTITY


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_edi_authorization_issuing_entity = fields.Selection(
        selection=ISSUING_ENTITY,
        string="Entidad emisora de autorización especial",
        help="Catálogo N°37 SUNAT: entidad que otorgó la autorización especial de la empresa de transporte."
    )
    l10n_pe_edi_operator_license = fields.Char(
        string="Licencia de conducir",
        help="Número de licencia de conducir del operador/conductor."
    )
