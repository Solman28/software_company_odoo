from odoo import models,api,fields
from odoo.exceptions import UserError, ValidationError

class SunatCatalog59(models.Model):
    _name = "sunat.catalog.59"
    _description = "Medios de Pago"

    active = fields.Boolean("Activo",default=True)
    name = fields.Char("Descripción")
    code = fields.Char("Código")

class SunatCatalog54(models.Model):
    _name = "sunat.catalog.54"
    _description = "Códigos de bienes y servicios sujetos a detracciones"

    active = fields.Boolean("Activo", default=True)
    name = fields.Char("Descripción")
    #anexo = fields.Char("Anexo", required=True)
    code = fields.Char("Código", required=True)
    rate = fields.Float("Tasa %")
    # product_ids = fields.Many2many(
    #     'product.product',
    #     'sunat_catalog_54_product_rel',
    #     'catalog_id',
    #     'product_id',
    #     string="Productos y/o Servicios"
    # )
    product_ids = fields.One2many('product.product', 'detraction_id', string="Productos y/o Servicios")
    description = fields.Text("Comentario")

    _sql_constraints = [
		('code_uniq', 'unique(code)', 'El codigo tiene que ser Unico!'),
	]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}"
    
    # @api.constrains('product_ids')
    # def _check_unique_detraccion(self):
    #     for record in self:
    #         for product in record.product_ids:
    #             exist = self.search([
    #                 ('id', '!=', record.id),
    #                 ('product_ids', 'in', product.id)
    #             ], limit=1)
    #             if exist:
    #                 raise ValidationError(
    #                     f"El producto {product.display_name} "
    #                     f"ya pertenece a la categoría {exist.name}"
    #                 )

class SunatCatalog53(models.Model):
    _name = "sunat.catalog.53"
    _description = "Códigos de cargos, descuentos y otras deducciones"

    active = fields.Boolean("Activo",default=True)
    name = fields.Char("Descripción")
    code = fields.Char("Código")

class SunatCatalog51(models.Model):
    _name = "sunat.catalog.51"
    _description = " Código de tipo de operación"

    active = fields.Boolean("Activo",default=True)
    name = fields.Char("Descripción")
    code = fields.Char("Código")
    available_factura = fields.Boolean("Factura")
    available_boleta = fields.Boolean("Boleta")

class SunatCatalog03(models.Model):
    _name = "sunat.catalog.03"
    _description = "Unidades de medida comerciales (SUNAT)"
    _order = "code"

    active = fields.Boolean("Activo", default=True)
    name = fields.Char("Descripción", required=True)
    code = fields.Char("Código", required=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'El código tiene que ser único!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.code}] {record.name}"
    
        


