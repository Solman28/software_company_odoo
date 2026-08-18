# -*- coding: utf-8 -*-
# Campos que en la versión original venían del módulo Enterprise "l10n_pe_edi".
# Se declaran aquí como campos propios para que "account.tax"/"account.tax.group"
# no necesiten ese módulo. Los valores son los códigos internos SUNAT que ya
# usaba la integración con PecanoFact (Catálogo 07 IGV / tipos de tributo).
from odoo import fields, models

# Catálogo N° 07 SUNAT: Tipo de Afectación del IGV
AFFECTATION_REASON = [
    ('10', 'Gravado - Operación Onerosa'),
    ('11', 'Gravado - Retiro por premio'),
    ('12', 'Gravado - Retiro por donación'),
    ('13', 'Gravado - Retiro'),
    ('14', 'Gravado - Retiro por publicidad'),
    ('15', 'Gravado - Bonificaciones'),
    ('16', 'Gravado - Retiro por entrega a trabajadores'),
    ('17', 'Gravado - IVAP'),
    ('20', 'Exonerado - Operación Onerosa'),
    ('21', 'Exonerado - Transferencia Gratuita'),
    ('30', 'Inafecto - Operación Onerosa'),
    ('31', 'Inafecto - Retiro por Bonificación'),
    ('32', 'Inafecto - Retiro'),
    ('33', 'Inafecto - Retiro por Muestras Médicas'),
    ('34', 'Inafecto - Retiro por Convenio Colectivo'),
    ('35', 'Inafecto - Retiro por premio'),
    ('36', 'Inafecto - Retiro por publicidad'),
    ('40', 'Exportación'),
]


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_pe_edi_tax_code = fields.Char(
        string="Código de tributo SUNAT",
        help="Código interno SUNAT del tributo (p.ej. 1000 = IGV, 9995 = Exportación, "
             "9996 = Gratuito, 9997 = Exonerado, 9998 = Inafecto, 9999 = Otros)."
    )
    l10n_pe_edi_affectation_reason = fields.Selection(
        selection=AFFECTATION_REASON,
        string="Tipo de afectación al IGV",
        help="Catálogo N°07 SUNAT. Para IGV 18% estándar usar '10 - Gravado - Operación Onerosa'.",
    )


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    l10n_pe_edi_code = fields.Char(
        string="Código EDI",
        help="Identificador del grupo de impuesto usado en la facturación electrónica "
             "(IGV, EXO, INA, ISC, ICBPER, FACTURA GRATUITA)."
    )
