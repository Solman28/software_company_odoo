# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import fields, models, api, _


class StockPicking(models.Model):
	_inherit = 'stock.picking'

	guia_remision_ids = fields.Many2many('guia.remision', string='Guia de remision', copy=False)
	guia_remision_remitente_count = fields.Integer(string="Cantidad total de GRR", compute="_compute_guia_remision_remitente_count")
	guia_remision_transportista_count = fields.Integer(string="Cantidad total de GRT", compute="_compute_guia_remision_transportista_count")
	hide_grr_button = fields.Boolean(compute="_compute_hide_grr_button")
	hide_grt_button = fields.Boolean(compute="_compute_hide_grt_button")

	# [ Guia de remision ]
	# [ Guia de remision remitente ]
	@api.depends("guia_remision_ids")
	def _compute_guia_remision_remitente_count(self):
		for record in self:
			record.guia_remision_remitente_count = len(record.guia_remision_ids.filtered(lambda g:g.gre_type == 'remitente'))
	
	@api.depends('guia_remision_ids', 'guia_remision_ids.gre_type')
	def _compute_hide_grr_button(self):
		for record in self:
			record.hide_grr_button = any(
				g.state == 'validated' and g.gre_type == 'remitente'
				for g in record.guia_remision_ids
			) or not self.picking_type_id.need_gre
	
	def action_generate_gre_remitente(self):
		self.ensure_one()
		if not self.l10n_pe_edi_transport_type:
			raise ValidationError("Es obligatorio que seleccione el tipo de transporte.")
		warehouse = self.picking_type_id.warehouse_id if self.picking_type_id else False
		destinatario = self.partner_id
		action = {
			'type': 'ir.actions.act_window',
			'name': 'Guia de Remision Remitente',
			'view_mode': 'form',
			'res_model': 'guia.remision',
			'context': {
				"default_gre_type": "remitente",
				"default_fecha_inicio_traslado": fields.Datetime.now(),
				"default_documento_asociado": "movimiento_stock",
				"default_destinatario_partner_id": destinatario.id if destinatario else False,
				"default_partner_direccion_partida_id": self.company_id.id if self.company_id else False,
				"default_partner_direccion_llegada_id": destinatario.id if destinatario else False,
				"default_transport_type": self.l10n_pe_edi_transport_type,
				"default_picking_ids": [(6, 0, [self.id])],
			},
		}
		if warehouse:
			action["context"].update({
				"default_warehouse_id": warehouse.id,
				"block_warehouse": True
			})
		return action
	
	def action_view_guia_remision_remitente(self):
		self.ensure_one()
		guia_remision_ids = self.guia_remision_ids.filtered(lambda g: g.gre_type == 'remitente')

		if len(guia_remision_ids) == 1:
			action = {
				"type": "ir.actions.act_window",
				"res_model": "guia.remision",
				"target": "self",
				"view_mode": "form",
				"res_id": guia_remision_ids.id,
				"context": {
					'block_warehouse': True,
					'create': False,
					'delete': False
				}
			}
		elif len(guia_remision_ids) > 1:
			action = {
				"type": "ir.actions.act_window",
				"res_model": "guia.remision",
				"target": "self",
				"view_mode": "list,form",
				"domain": [("id", "in", guia_remision_ids.mapped("id"))],
				"context": {
					'block_warehouse': True,
					'create': False,
					'delete': False
				}
			}
		return action
	
	# [ Guia de remision transportista ]
	@api.depends("guia_remision_ids")
	def _compute_guia_remision_transportista_count(self):
		for record in self:
			record.guia_remision_transportista_count = len(record.guia_remision_ids.filtered(lambda g:g.gre_type == 'transportista'))
	
	@api.depends('guia_remision_ids', 'guia_remision_ids.state', 'l10n_pe_edi_transport_type')
	def _compute_hide_grt_button(self):
		for record in self:
			exist = any(
				g.state == 'validated' and g.gre_type == 'transportista'
				for g in record.guia_remision_ids
			)
			record.hide_grt_button = not self.env.company.partner_id.is_transport_company or exist or record.l10n_pe_edi_transport_type != '01'
	
	def action_generate_gre_transportista(self):
		self.ensure_one()
		# Validar que la compañia sea una empresa de transporte
		if not self.env.company.partner_id.is_transport_company:
			raise ValidationError("La compañía no esta configurada como empresa de transporte.")
		if self.l10n_pe_edi_transport_type != '01':
			raise ValidationError("La emisión de Guia de Remision Transportista solo esta permitido para el tipo de transporte Público.")
		guia_remitente_ids = self.guia_remision_ids.filtered(lambda g:g.state == 'validated' and g.gre_type == 'remitente')
		warehouse = self.picking_type_id.warehouse_id if self.picking_type_id else False
		action = {
			'type': 'ir.actions.act_window',
			'name': 'Guia de Remision Transportista',
			'view_mode': 'form',
			'res_model': 'guia.remision',
			'context': {
				"default_gre_type": "transportista",
				"default_related_document": self.env['related.document'].search([('code', '=', '09')]).id,
				"default_guia_remitente_id": guia_remitente_ids[0].id if guia_remitente_ids else False,
				"default_transport_type": '01',
				"default_picking_ids": [(6, 0, [self.id])],
			}
		}
		if warehouse:
			action["context"].update({
				"default_warehouse_id": warehouse.id,
				"block_warehouse": True
			})
		return action

	def action_view_guia_remision_transportista(self):
		self.ensure_one()
		guia_remision_ids = self.guia_remision_ids.filtered(lambda g: g.gre_type == 'transportista')
		
		if len(guia_remision_ids) == 1:
			action = {
				"type": "ir.actions.act_window",
				"res_model": "guia.remision",
				"target": "self",
				"view_mode": "form",
				"res_id": guia_remision_ids.id,
				"context": {
					'block_warehouse': True,
					'create': False,
					'delete': False
				}
			}
		elif len(guia_remision_ids) > 1:
			action = {
				"type": "ir.actions.act_window",
				"res_model": "guia.remision",
				"target": "self",
				"view_mode": "list,form",
				"domain": [("id", "in", guia_remision_ids.mapped("id"))],
				"context": {
					'block_warehouse': True,
					'create': False,
					'delete': False
				}
			}
		return action