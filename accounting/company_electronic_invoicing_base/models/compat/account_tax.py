# -*- coding: utf-8 -*-
# Campos que en la versión original venían del módulo Enterprise "l10n_pe_edi".
# Se declaran aquí como campos propios para que "account.tax"/"account.tax.group"
# no necesiten ese módulo. Los valores son los códigos internos SUNAT que ya
# usaba la integración con PecanoFact (Catálogo 07 IGV / tipos de tributo).
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_pe_edi_tax_code = fields.Char(
        string="Código de tributo SUNAT",
        help="Código interno SUNAT del tributo (p.ej. 1000 = IGV, 9995 = Exportación, "
             "9996 = Gratuito, 9997 = Exonerado, 9998 = Inafecto, 9999 = Otros)."
    )
    l10n_pe_edi_affectation_reason = fields.Char(
        string="Tipo de afectación al IGV",
        help="Código SUNAT del tipo de afectación del IGV (Catálogo 07)."
    )


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    l10n_pe_edi_code = fields.Char(
        string="Código EDI",
        help="Identificador del grupo de impuesto usado en la facturación electrónica "
             "(IGV, EXO, INA, ISC, ICBPER, FACTURA GRATUITA)."
    )
