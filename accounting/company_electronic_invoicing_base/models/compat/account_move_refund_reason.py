# -*- coding: utf-8 -*-
# "l10n_pe_edi_refund_reason" venía originalmente del módulo Enterprise
# "l10n_pe_edi" (Catálogo 09 SUNAT: tipo de nota de crédito). Se declara aquí
# como campo propio -con el mismo Catálogo 09- para que account.move y
# account.move.reversal no dependan de Enterprise. Este archivo se importa
# antes que models/account/account_move.py, que le agrega la opción '13'
# vía selection_add.
from ..parameters.catalogs import tnc
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_edi_refund_reason = fields.Selection(selection=tnc, string="Tipo de Nota de Crédito (SUNAT)")


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    l10n_pe_edi_refund_reason = fields.Selection(selection=tnc, string="Tipo de Nota de Crédito (SUNAT)")
