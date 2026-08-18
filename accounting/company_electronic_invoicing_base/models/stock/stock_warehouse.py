# -*- coding: utf-8 -*-
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, AccessError
from odoo import fields, models, api, _


class stockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    journal_ids = fields.Many2many('account.journal', string='Series permitidas')