from odoo import api, fields, models

class JNQL10nLatamIdentificationType(models.Model):
    
    _inherit = 'l10n_latam.identification.type'
    
    jnq_code_pecanofact = fields.Char('Código PecanoFact')