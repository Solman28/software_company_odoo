from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api


class ResPartnerMTC(models.Model):
    _name = 'res.partner.mtc'

    partner_id = fields.Many2one('res.partner', string="Contacto")
    mtc_number = fields.Char(string="Número MTC", required=True)
    modality = fields.Selection([ 
        ('general', 'Mercancías en general'),
        ('hazardous', 'Materiales y Residuos Peligrosos'),
    ], string="Modalidad de Empresa")
    valid_until = fields.Date(string="Vigente Hasta")
    state = fields.Selection([
        ('valid', 'Habilitado'),
        ('expired', 'Vencido'),
    ], string="Estado")

    @api.depends('mtc_number')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.mtc_number