from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError

class AccountParameters(models.Model):
    
    _name = "account.parameters"
    _description = "Parámetros de facturación"
    
    name = fields.Char('Nombre')
    code = fields.Char('Código')
    duration = fields.Integer('Duración')
    measure_time = fields.Selection([('day','Día'),('currency','Soles')], string='Medida', default='day')
    company_id = fields.Many2one('res.company', 'Compañía', required=True, default=lambda self: self.env.company.id)
    
    _sql_constraints = [
        ('unique_code_company_id', 'unique (code,company_id)', '¡El código del parámetro debe ser único por compañía!')
    ] 
    
    @api.model
    def get_value_parameters(self,information=False):
        if information:
            company = information.get('company',False)
            code = information.get('code','')
            value_maximum = self.env['account.parameters'].search([('company_id','=',company),('code','=',code)])
            if not value_maximum.id:
                raise ValidationError("No existe un parámetro configurado para esta validación. Por favor, revise su configuración.")
            return value_maximum.duration
                    
    