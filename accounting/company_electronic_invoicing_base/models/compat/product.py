# -*- coding: utf-8 -*-
# "sunat_code" venía originalmente del catálogo de productos de Enterprise
# "l10n_pe_edi". Se define un catálogo propio y liviano (a completar según lo
# que necesite la empresa) para la validación de comprobantes de exportación.
from odoo import fields, models


class SunatProductCode(models.Model):
    _name = "sunat.product.code"
    _description = "Código de producto SUNAT (Catálogo 33 / anexo exportación)"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código debe ser único.'),
    ]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sunat_code = fields.Many2one(
        'sunat.product.code',
        string="Código SUNAT de producto",
        help="Requerido para comprobantes de exportación."
    )
