# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductUoM(models.Model):
    _inherit = 'uom.uom'

    l10n_pe_edi_measure_unit_code = fields.Char('Código de unidad de medida comercial', help="Código de unidad que se refiere a un producto con el fin de identificar qué unidad de medid utiliza.")
    code_dam = fields.Char('Código DAM', help='En caso de que el motivo sea Importación o Exportación debe usar las unidades de medida del Catálogo 65 de la SUNAT:  Código de unidades de medida (para uso solo para la GRE en DAM o DS)')
