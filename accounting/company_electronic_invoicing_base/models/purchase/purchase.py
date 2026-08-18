from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
	_inherit = "purchase.order"

    # [ Funciones sobreescritas ]
	def _prepare_invoice(self):
		res = super()._prepare_invoice()
		res['journal_type'] = 'purchase'
		res['invoice_type_code'] = "01"
		return res