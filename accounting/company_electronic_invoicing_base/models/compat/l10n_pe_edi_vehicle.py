# -*- coding: utf-8 -*-
# Modelo propio que reemplaza a "l10n_pe_edi.vehicle" (Odoo Enterprise, módulo
# l10n_pe_edi_stock). Se mantiene el mismo nombre técnico para no tener que
# tocar todas las referencias existentes (guia_remision.py, utils.py de
# PecanoFact, vistas, etc.), pero el modelo es 100% propio y no depende de
# Enterprise.
from odoo import api, fields, models

ISSUING_ENTITY = [
    ('01', 'Entidad 01'),
    ('02', 'Entidad 02'),
    ('03', 'Entidad 03'),
    ('04', 'Entidad 04'),
    ('05', 'Entidad 05'),
    ('06', 'Entidad 06'),
    ('07', 'Entidad 07'),
    ('08', 'Entidad 08'),
    ('09', 'Entidad 09'),
    ('10', 'Entidad 10'),
    ('11', 'Entidad 11'),
    ('12', 'Entidad 12'),
]


class L10nPeEdiVehicle(models.Model):
    _name = "l10n_pe_edi.vehicle"
    _description = "Vehículo (GRE)"

    name = fields.Char(string="Nombre", required=True, default="Vehículo")
    license_plate = fields.Char(string="Placa")
    operator_id = fields.Many2one('res.partner', string="Operador")
    authorization_issuing_entity = fields.Selection(
        selection=ISSUING_ENTITY,
        string="Entidad emisora de autorización especial",
        help="Catálogo N°37 SUNAT: entidad que otorgó la autorización especial del vehículo."
    )
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.depends('license_plate')
    def _compute_display_name(self):
        for vehicle in self:
            vehicle.display_name = vehicle.license_plate or vehicle.name
