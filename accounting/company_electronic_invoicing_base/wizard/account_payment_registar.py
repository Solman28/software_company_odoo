from odoo import fields, models, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    
    @api.onchange('payment_difference_handling')
    def _onchange_payment_difference(self):
        for record in self:
            context = record._context
            if context.get('active_model') == 'account.move.line' and record.payment_difference_handling \
                and record.payment_difference_handling == 'reconcile':
                    move_id = self.env['account.move'].sudo().search([('id','=',context.get('active_id'))])
                    if move_id and  move_id.apply_retention:
                        record.sudo().write({
                            'writeoff_account_id': record.company_id.retention_account_id.id,
                            'writeoff_label': move_id.retention_receipt if move_id.retention_receipt else ''
                        })
                        
    def action_create_payments(self):
        res = super(AccountPaymentRegister,self).action_create_payments()
        context = self._context
        if context.get('active_model') == 'account.move':
            move_id = self.env['account.move.line'].sudo().search([('id','=',context.get('active_id'))])
            if move_id and not move_id.retention_receipt:
                move_id.write({ 
                    'retention_receipt': self.writeoff_label, 
                    'retention_date': self.payment_date
                })
        return res
        