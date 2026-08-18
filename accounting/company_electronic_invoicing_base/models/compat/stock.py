# -*- coding: utf-8 -*-
# Campos que en la versión original venían de Enterprise "l10n_pe_edi_stock".
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_pe_edi_transport_type = fields.Selection(
        selection=[('01', 'Transporte público'), ('02', 'Transporte privado')],
        string="Modalidad de transporte",
    )


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    need_gre = fields.Boolean(
        string="Requiere Guía de Remisión Electrónica",
        help="Si está activo, se habilita el botón para generar la GRE Remitente desde este tipo de operación."
    )
