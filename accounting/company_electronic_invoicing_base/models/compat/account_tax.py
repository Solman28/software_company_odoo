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


# Identificador interno usado por el módulo (get_amount_totals) para clasificar
# los grupos de impuesto en el resumen del comprobante electrónico.
EDI_TAX_GROUP_CODE = [
    ('IGV', 'IGV - Impuesto General a las Ventas (operación gravada)'),
    ('EXO', 'EXO - Operación Exonerada del IGV'),
    ('INA', 'INA - Operación Inafecta al IGV'),
    ('ISC', 'ISC - Impuesto Selectivo al Consumo'),
    ('ICBPER', 'ICBPER - Impuesto a las Bolsas Plásticas'),
    ('FACTURA GRATUITA', 'FACTURA GRATUITA - Operación Gratuita (sin cobro)'),
]


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    l10n_pe_edi_code = fields.Selection(
        selection=EDI_TAX_GROUP_CODE,
        string="Código EDI",
        help="Clasificación del grupo de impuesto para el resumen del comprobante electrónico. "
             "Usar IGV para el grupo del IGV 18%, EXO/INA para exoneradas/inafectas, ISC para "
             "el impuesto selectivo, ICBPER para bolsas plásticas y FACTURA GRATUITA para "
             "operaciones sin cobro (bonificaciones, muestras, etc.).",
    )
