from odoo import api, fields, models

class SunatCatalog54(models.Model):
    
    _inherit = 'sunat.catalog.54'
    
    jnq_code_pecanofact = fields.Char('Código PecanoFact')