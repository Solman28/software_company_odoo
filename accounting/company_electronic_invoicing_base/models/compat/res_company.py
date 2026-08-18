# -*- coding: utf-8 -*-
# Campo que en la versión original venía de Enterprise "l10n_pe_edi".
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_edi_address_type_code = fields.Char(
        string="Código de establecimiento SUNAT",
        size=4,
        help="Código de establecimiento anexo asignado por SUNAT (4 dígitos)."
    )
