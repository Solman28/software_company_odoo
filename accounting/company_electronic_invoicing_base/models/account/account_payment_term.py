from odoo import fields,api,models
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    type = fields.Selection(selection=[("Credito","Crédito"),("Contado","Contado")], default="Contado")

    @api.constrains
    def check_type_paymentterm(self):
        for record in self:
            if record.type == "Contado":
                if len(record.line_ids) != 1:
                    raise UserError("El tipo de pago al contado debe tener sólo una línea en los términos de pago. Los valores que debe tomar son (Tipo='Balance',Número de días=0,Días del mes=0)")
                else:
                    line = record.line_ids
                    if line.value != 'balance' or line.days != 0 or line.day_of_the_month != 0:
                        raise UserError("El tipo de pago al contado debe tener sólo una línea en los términos de pago. Los valores que debe tomar son (Tipo='Balance',Número de días=0,Días del mes=0)")
