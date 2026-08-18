from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    detraction_id = fields.Many2one('sunat.catalog.54', string="Código de detracción", help="Selecciona el concepto de detracción al que pertenece el producto/servicio.")
    detraction_percentage = fields.Float(related="detraction_id.rate", string="Tasa(%) de detracción")