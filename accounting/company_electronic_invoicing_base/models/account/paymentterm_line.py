from odoo import models,fields,api
from odoo.exceptions import UserError
from pytz import timezone
from datetime import datetime, timedelta


class PaymentTermLine(models.Model):

    _name = "paymentterm.line"
    _order = "date_due ASC"
    _description = "Lineas de término de pago de facturas"
    
    currency_id = fields.Many2one("res.currency", related="move_id.currency_id", store=True)
    move_id = fields.Many2one("account.move", string="Comprobante")
    date_due = fields.Date(string="Fecha de vencimiento")
    amount = fields.Float(string="Monto")

    @api.constrains("move_id")
    def check_move_id(self):
        for record in self:
            move = record.move_id
            if move:
                if move.invoice_payment_term_id:
                    if move.invoice_payment_term_id.type != "Credito":
                        raise UserError("Si la factura tiene líneas de plazos de pago, entonces su término de pago debe ser uno de tipo Crédito.")
                else:
                    if not ((move.invoice_date != False and move.invoice_date_due > move.invoice_date) or \
                        (move.invoice_date == False and move.invoice_date_due > datetime.now(tz=timezone("America/Lima")).date())):
                        raise UserError("Si la factura tiene líneas de plazos de pago, entonces su término de pago debe ser uno de tipo Crédito.")

    


