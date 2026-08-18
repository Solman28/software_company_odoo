from odoo import fields, models

class ResPartnerBank(models.Model):
	_inherit = 'res.partner.bank'

	is_bank_detraction_account = fields.Boolean(string="Cuenta de detracción", help="Activar si la cuenta es usada para el régimen de detracciones", default=False)
	interbank_acc_number = fields.Char('Número de cuenta interbancaria', required=True, tracking=True)
	currency_id = fields.Many2one(required=True)
	show_in_invoice = fields.Boolean(string="Mostrar en comprobante de venta", help="Si esta activo la cuenta bancaria se establece como cuenta bancaria de pago en el comprobante.")