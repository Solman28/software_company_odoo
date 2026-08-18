# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from ..parameters.catalogs import tnc, tnd, tdc
import re
import logging
from datetime import datetime
from pytz import timezone
from odoo.tools import float_round, float_compare
import urllib
import requests
import logging
_logger = logging.getLogger(__name__)

patron_dni = re.compile(r"^\d{8}$")
patron_ruc = re.compile(r"^[12]\d{10}$")

estado_comprobante_electronico_list = [
	("0_NO_EXISTE", "NO EXISTE"),
	("1_ACEPTADO", "ACEPTADO"),
	("2_ANULADO", "ANULADO"),
	("3_AUTORIZADO", "AUTORIZADO"),
	("4_NO_AUTORIZADO", "NO AUTORIZADO"),
	("-", "-")
]

estado_contribuyente_ruc_list = [
	("00_ACTIVO", "ACTIVO"),
	("01_BAJA_PROVISIONAL", "BAJA PROVISIONAL"),
	("02_BAJA_PROV_POR_OFICIO", "BAJA PROV. POR OFICIO"),
	("03_SUSPENSION_TEMPORAL", "SUSPENSION TEMPORAL"),
	("10_BAJA_DEFINITIVA", "BAJA DEFINITIVA"),
	("11_BAJA_DE_OFICIO", "BAJA DE OFICIO"),
	("22_INHABILITADO-VENT.UNICA", "INHABILITADO-VENT.UNICA"),
	("-", "-")
]

condicion_domicilio_contribuyente_list = [
	("00_HABIDO", "HABIDO"),
	("09_PENDIENTE", "PENDIENTE"),
	("11_POR_VERIFICAR", "POR VERIFICAR"),
	("12_NO_HABIDO", "NO HABIDO"),
	("20_NO_HALLADO", "NO HALLADO"),
	("-", "-")
]

estado_comprobante_electronico_sunat = {
	"0":"0_NO_EXISTE",
	"1":"1_ACEPTADO",
	"2":"2_ANULADO",
	"3":"3_AUTORIZADO",
	"4":"4_NO_AUTORIZADO"
}

estado_contribuyente_ruc = {
	"00": "00_ACTIVO",
	"01": "01_BAJA_PROVISIONAL",
	"02": "02_BAJA_PROV_POR_OFICIO",
	"03": "03_SUSPENSION_TEMPORAL",
	"10": "10_BAJA_DEFINITIVA",
	"11": "11_BAJA_DE_OFICIO",
	"22": "22_INHABILITADO",
	"-": "-"
}

condicion_domicilio_ruc = {
	"00": "00_HABIDO",
	"09": "09_PENDIENTE",
	"11": "11_POR_VERIFICAR",
	"12": "12_NO_HABIDO",
	"20": "20_NO_HALLADO",
	"-": "-"
}

MAX_AMOUNT = 700

class AccountMove(models.Model):
	_inherit = "account.move"

	warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", domain="[('id', 'in', suitable_warehouse_ids)]")
	suitable_warehouse_ids = fields.Many2many("stock.warehouse", string="Almacenes Permitidos", compute="_compute_suitable_warehouse_ids")
	invoice_type_code = fields.Selection(selection=[('00', 'Otros'), ('01', 'Factura'), ('03', 'Boleta'), ('07', 'Nota de crédito'), ('08', 'Nota de débito')], string="Tipo de Comprobante", readonly=True)
	jnq_invoice_type_code = fields.Char(string="Tipo de Documento", compute="_compute_invoice_type_for_journal")
	journal_type = fields.Selection(selection=[("sale", "Venta"), ("purchase", "compra")])
	inv_supplier_ref = fields.Char(string="Número de comprobante", default="-")
	# [ Compras ]
	prefix_code=fields.Char(string="Serie del Comprobante")
	invoice_number=fields.Char(string="Correlativo del Comprobante")
	# [ Pagos ]
	invoice_payment_term_type = fields.Char(string="Condición de pago", compute="_compute_invoice_payment_term_type", store=True)
	paymentterm_line = fields.One2many("paymentterm.line", "move_id")
	residual_credit_paymentterm = fields.Monetary(string="Saldo restante de plazos de pago a crédito", compute="_compute_residual_credit_paymentterm")
	partner_bank_ids = fields.Many2many(
		'res.partner.bank',
		string='Cuentas bancarias para pago',
		compute='_compute_partner_bank_ids',
        store=True,
		readonly=False
	)
	# [ Tipo de cambio ]
	exchange_rate_sunat = fields.Float(
		string="T/C",
		compute="_compute_exchange_rate_sunat",
		store=True,
		readonly=True,
		digits=(5, 3),
		help="Tipo de cambio SUNAT (Moneda del comprobante → Moneda de la compañía). "
	)
	exchange_rate_warning = fields.Boolean(
		string="Advertencia TC",
		compute="_compute_exchange_rate_sunat",
		store=True,
	)
	# [ Configuración ]
	# inv_supplier_ref_validation = fields.Boolean(string='Requiere validación',compute='_compute_inv_supplier_ref_validation', store=True)
	# [ Facturacion Electrónica ]
	invoice_type_code_catalog_51 = fields.Many2one("sunat.catalog.51", string="Tipo de Operación catg51", default=lambda self: self.env.ref("company_electronic_invoicing_base.catalog_51_0101", raise_if_not_found=False), required=True)
	sustento_nota = fields.Text(string="Sustento de nota", readonly=True, copy=False)
	tipo_nota_credito = fields.Selection(string='Tipo de Nota de Crédito', readonly=True, selection="_selection_tipo_nota_credito")
	tipo_nota_debito = fields.Selection(string='Tipo de Nota de Débito', readonly=True, selection="_selection_tipo_nota_debito")
	sale_order_reference = fields.Char("Número de la orden de compra")
	# [ Validez del comprobante ]
	estado_comprobante_electronico = fields.Selection(selection=estado_comprobante_electronico_list, default="-", copy=False, tracking=True)
	estado_contribuyente_ruc = fields.Selection(selection=estado_contribuyente_ruc_list, default="-", copy=False)
	condicion_domicilio_contribuyente = fields.Selection(selection=condicion_domicilio_contribuyente_list, default="-", copy=False)
	consulta_validez_observaciones = fields.Text("Consulta Validez - Observaciones", copy=False)
	show_validate_cpe_sunat_button = fields.Boolean(compute='_compute_show_validate_cpe_sunat_button')
	# [ Registro de envios ]
	account_log_status_ids = fields.One2many("account.log.status", "account_move_id", string="Registro de Envíos", copy=False)
	current_log_status_id = fields.Many2one("account.log.status", copy=False)
	estado_emision = fields.Selection(string="Estado Emisión a SUNAT", related="current_log_status_id.status", store=True)
	# [Comunicacion de baja ]
	documento_baja_id = fields.Many2one("account.comunicacion_baja", copy=False)
	mostrar_btn_comunicacion_baja = fields.Boolean(string="Mostrar botón comunicación baja", compute="_compute_mostrar_btn_comunicacion_baja")
	documento_baja_state = fields.Selection(selection=[
			('A', 'Aceptado'),
			('E', 'Enviado a SUNAT'),
			('N', 'Envio Erróneo'),
			('O', 'Aceptado con Observación'),
			('R', 'Rechazado'),
			('P', 'Pendiente de envió a SUNAT')
		],string="Estado del Documento de Baja", compute="_compute_documento_baja_state", copy=False)
	anulacion_comprobante = fields.Char(string="Anulación de Comprobante", compute="_compute_obtener_estado_anulacion_comprobante")
	# #[ Nota de crédito ]
	# # credit_note_ids = fields.One2many("account.move", "reversed_entry_id")
	credit_note_count = fields.Integer(string="Número de notas de crédito", compute='_compute_credit_note_count')
	l10n_pe_edi_refund_reason = fields.Selection(
		selection_add=[
			('13', 'Corrección del monto neto, fechas de pago o montos de las cuotas'),
		],
		ondelete={
			'13': 'cascade',
		},
	)
	# [ Retenciones ]
	apply_retention = fields.Boolean(string="Aplicar Retención", default=False)
	retention_percentage = fields.Selection([('3','Tasa 3%'),('6','Tasa 6%'),('0','-')], string='Retención', default='0')
	retention_rate = fields.Float(string="Retención(%)", compute='_compute_retention_rate', store=True)
	amount_retention = fields.Monetary(string="Monto de retención", compute="_compute_amount_retention", default=0, store=True)
	retention_receipt = fields.Char(string="Comprobante de retención")
	retention_date = fields.Date(string="Fecha")
	# [ Detracciones ]
	is_detraction = fields.Boolean(string="Aplicar detracción", default=False)
	detraction_id = fields.Many2one('sunat.catalog.54', string="Concepto de detracción", compute="_compute_detraction", store=True)
	detraction_rate = fields.Float(string="Detracción(%)", compute="_compute_detraction", store=True)
	round_amount_detraction = fields.Boolean(string="Redondear importe de detracción", 
		tracking=True, help="Si esta activo se tomará el monto redondeado de la detracción."
	)
	amount_detraction = fields.Monetary(string="Monto de detracción", compute="_compute_amount_detraction", store=True)
	amount_detraction_signed = fields.Monetary(string="Monto de detracción (PEN)", compute="_compute_amount_detraction", store=True, currency_field='company_currency_id')
	amount_detraction_signed_rounded = fields.Monetary(string="Monto de detracción redondeado(PEN)", compute="_compute_amount_detraction", store=True, currency_field='company_currency_id')
	register_detraction_id = fields.Many2one('account.detraction', string="Registro de Detracción", copy=False)

	def _selection_tipo_nota_credito(self):
		return tnc

	def _selection_tipo_nota_debito(self):
		return tnd
	
	@api.constrains('apply_retention', 'is_detraction')
	def check_apply_tax_regime(self):
		for record in self:
			if record.apply_retention and record.is_detraction:
				raise UserError("No se puede aplicar retención y detracción sobre un mismo comprobante.")
	
	def validate_requeriment_apply_retention(self):
		errors = []
		for record in self:
			if not record.apply_retention:
				continue
			partner = record.partner_id
			if not partner:
				continue
			if record.is_detraction:
				errors.append("No se puede aplicar retención y detracción sobre un mismo comprobante.")
			if not partner.is_retention_agent:
				errors.append(
					f"El cliente {partner.name} no está configurado como agente de retención."
				)
			param = self.env['account.parameters'].search([
				('company_id', '=', record.company_id.id),
				('code', '=', 'minimum_retention_amount')
			], limit=1)
			
			amount = abs(record.amount_total_signed)
			max_amount = param.duration if param else MAX_AMOUNT
			if param and amount <= max_amount:
				errors.append(f"Para aplicar el régimen de retenciones el importe total del comprobante debe ser mayor a {max_amount} soles.")
		return errors

	@api.constrains("invoice_date_due", "paymentterm_line","paymentterm_line.date_due")
	def check_invoice_date_due_vs_cuotas(self):
		for record in self:
			if not record.invoice_date_due or not record.paymentterm_line:
				continue
			dates = [d for d in record.paymentterm_line.mapped("date_due") if d]
			if not dates:
				continue
			date_due_max = max(dates)
			if record.invoice_date_due < date_due_max:
				raise ValidationError(
					"Ninguna de las Fechas de Pago de las Cuotas debe ser mayor a la Fecha de Vencimiento del Documento.")

	# [ Métodos Computados ]
	@api.depends('move_type', 'company_id')
	def _compute_partner_bank_ids(self):
		for move in self:
			if move.move_type in ('out_invoice', 'out_refund'):
				banks = move.company_id.partner_id.bank_ids.filtered(
					lambda b: b.show_in_invoice
				)
				move.partner_bank_ids = [(6, 0, banks.ids)]
			else:
				move.partner_bank_ids = [(5, 0, 0)]

	@api.depends('company_id')
	def _compute_suitable_warehouse_ids(self):
		for record in self:
			company = record.company_id or self.env.company
			suitable_warehouses = self.env['stock.warehouse'].search([('company_id', '=', company.id)])
			record.suitable_warehouse_ids = [(6 ,0, suitable_warehouses.ids)]

	@api.depends('move_type', 'origin_payment_id', 'statement_line_id')
	def _compute_journal_id(self):
		for record in self:
			if record.is_sale_document():
				record.journal_id = False
			else:
				super()._compute_journal_id()

	@api.depends('company_id', 'invoice_filter_type_domain', 'journal_type', 'move_type', 'warehouse_id')
	def _compute_suitable_journal_ids(self):
		for record in self:
			journal_type = record.invoice_filter_type_domain or record.journal_type or 'general'
			if record.move_type in ['out_invoice','out_refund']:
				domain = [
					('company_id', '=', record.company_id.id),
					('invoice_type_code', '=', record.invoice_type_code),
					('type', '=', journal_type),
				]
				journal_ids = self.env["account.journal"].search(domain)
				# El almacén solo restringe la lista si tiene "Series permitidas"
				# configuradas explícitamente; si no, se listan todas las series
				# electrónicas de la compañía para ese tipo de comprobante.
				if record.warehouse_id and record.warehouse_id.journal_ids:
					journal_ids = journal_ids.filtered(lambda j: j in record.warehouse_id.journal_ids)
				record.suitable_journal_ids = journal_ids
			elif record.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
				domain = [('type','=',journal_type)]
				journal_ids = self.env["account.journal"].search(domain)
				record.suitable_journal_ids = journal_ids
			elif record.move_type in ['out_receipt']:
				#journal_type = self.env.context.get('default_journal_type') or record.journal_type or 'sale'
				domain = [('type','=',journal_type)]
				journal_ids = self.env["account.journal"].search(domain)
				record.suitable_journal_ids = journal_ids
			else:
				if record.origin_payment_id:
					record.suitable_journal_ids = record.journal_id
				else:
					domain = [('type', 'not in', ('sale', 'purchase'))]
					journal_ids = self.env["account.journal"].search(domain)
					record.suitable_journal_ids = journal_ids
	
	@api.depends("invoice_payment_term_id", "invoice_date_due")
	def _compute_invoice_payment_term_type(self):
		for record in self:
			record.invoice_payment_term_type = "Contado"
			if record.invoice_payment_term_id:
				record.invoice_payment_term_type = record.invoice_payment_term_id.type
			else:
				if record.invoice_date_due:
					if (record.invoice_date != False and record.invoice_date_due > record.invoice_date) or \
							(record.invoice_date == False and record.invoice_date_due > datetime.now(tz=timezone("America/Lima")).date()):
						record.invoice_payment_term_type = "Credito"
				else:
					record.invoice_payment_term_type = "Contado"
	
	# @api.depends('fiscal_position_id', 'partner_id', 'inv_supplier_ref', 'company_id', 'company_id.inv_supplier_ref_validation')
	# def _compute_inv_supplier_ref_validation(self):
	#     for record in self:
	#         record.inv_supplier_ref_validation = False
	#         if record.company_id.inv_supplier_ref_validation:
	#             if record.move_type in ["in_invoice", "in_refund", "in_receipt"]:
	#                 if record.inv_supplier_ref:
	#                     if record.fiscal_position_id and record.fiscal_position_id.id == self.env.ref('l10n_pe.1_local_peru').id:
	#                         record.inv_supplier_ref_validation = True
	
	@api.depends('journal_id')
	def _compute_invoice_type_for_journal(self):
		for record in self:
			code = record.journal_id.invoice_type_code
			record.jnq_invoice_type_code = ""
			for tupla in tdc:
				if tupla[0] == code:
					record.jnq_invoice_type_code = "[" + tupla[0] + "]" + " " + tupla[1]
	
	@api.depends('currency_id', 'company_id', 'invoice_date')
	def _compute_exchange_rate_sunat(self):
		CurrencyRate = self.env['res.currency.rate']
		for move in self:
			move.exchange_rate_warning = False
			company_currency = move.company_id.currency_id
			invoice_currency = move.currency_id

			if not invoice_currency or invoice_currency == company_currency:
				move.exchange_rate_sunat = 1
				continue

			date = move.invoice_date or fields.Date.context_today(self)

			rate_record = CurrencyRate.search([
				('currency_id', '=', invoice_currency.id),
				('company_id', '=', move.company_id.id),
				('name', '=', date),
			], limit=1)

			if not rate_record:
				move.exchange_rate_warning = True

			rate = invoice_currency._get_conversion_rate(
				from_currency=invoice_currency,
				to_currency=company_currency,
				company=move.company_id,
				date=date,
			)
			move.exchange_rate_sunat = float_round(rate, precision_digits=3)
		
	@api.depends(
		"paymentterm_line",
		"paymentterm_line.amount",
		"amount_total",
		"amount_retention",
		"round_amount_detraction",
		"amount_detraction_signed",
		"amount_detraction_signed_rounded"
	)
	def _compute_residual_credit_paymentterm(self):
		for move in self:
			amount_detraction = move.amount_detraction_signed_rounded if move.round_amount_detraction else move.amount_detraction_signed
			move.residual_credit_paymentterm = round(
				move.amount_total - amount_detraction - move.amount_retention - sum(move.paymentterm_line.mapped("amount")), 2)

	@api.depends_context('uid')
	@api.depends(
		'estado_comprobante_electronico',
		'journal_id',
		'journal_id.invoice_type_code',
		'reversed_entry_id',
		'reversed_entry_id.estado_comprobante_electronico',
		'reversed_entry_id.journal_id',
		'move_type'
	)
	def _compute_mostrar_btn_comunicacion_baja(self):
		for rec in self:
			rec.mostrar_btn_comunicacion_baja=False
			if rec.move_type in ['out_invoice','out_refund'] and rec.state in ['posted']:
				if rec.journal_id and rec.journal_id.invoice_type_code in ['01','03']:
						rec.mostrar_btn_comunicacion_baja = True
				elif rec.journal_id \
					and rec.journal_id.invoice_type_code in ['07','08'] and rec.reversed_entry_id and \
					rec.reversed_entry_id.estado_comprobante_electronico == '1_ACEPTADO' and rec.reversed_entry_id.journal_id and \
					rec.reversed_entry_id.journal_id.invoice_type_code == '03':
						rec.mostrar_btn_comunicacion_baja = True

				if rec.mostrar_btn_comunicacion_baja:
					user = self.env.user
					rec.mostrar_btn_comunicacion_baja = user.has_group('company_electronic_invoicing_base.res_groups_anulacion_buttons') or user.id == rec.invoice_user_id.id
				
				# Se validará los días máximos para dar de baja a los documentos electrónicos
				if rec.mostrar_btn_comunicacion_baja:
					day_maximum = self.env['account.parameters'].search([('company_id','=',rec.company_id.id),('code','=','low_communication')])
					if not day_maximum.id:
						rec.mostrar_btn_comunicacion_baja = False
						continue
					now =  datetime.date(datetime.now(tz=timezone(self.env.user.tz or "America/Lima")))
					if abs(rec.invoice_date - now).days > day_maximum.duration:
						rec.mostrar_btn_comunicacion_baja = False
	
	@api.depends('documento_baja_id')
	def _compute_documento_baja_state(self):
		for record in self:
			record.documento_baja_state = False
			if record.documento_baja_id:
				record.documento_baja_state = record.documento_baja_id.state
	
	@api.depends('documento_baja_id')
	def _compute_obtener_estado_anulacion_comprobante(self):
		for record in self:
			if record.documento_baja_id:
				record.anulacion_comprobante = record.documento_baja_state
			else:
				record.anulacion_comprobante = "-"

	@api.depends('reversed_entry_id')
	def _compute_credit_note_count(self):
		for move in self:
			move.credit_note_count = 0
			if move.move_type in ['out_invoice', 'out_refund']:
				credit_notes = self.env['account.move'].search([
					('reversed_entry_id', '=', move.id),
					('move_type', '=', 'out_refund')
				])
				move.credit_note_count = len(credit_notes)    

	# [ Retenciones ]
	#@api.onchange('apply_retention','retention_percentage')
	@api.depends('apply_retention','retention_percentage')
	def _compute_retention_rate(self):
		for record in self:
			if record.apply_retention and record.retention_percentage:
				record.retention_rate = float(record.retention_percentage)
			else:
				record.retention_rate = 0.0
	
	@api.onchange('partner_id')
	def onchange_retention_partner_id(self):
		for record in self:
			partner = record.partner_id
			is_retention_agent = bool(partner and partner.is_retention_agent)
			record.apply_retention = is_retention_agent
			record.retention_percentage = partner.retention_percentage if is_retention_agent else '0'
	
	@api.depends('apply_retention', 'retention_rate', 'amount_total')
	def _compute_amount_retention(self):
		for move in self:
			if move.apply_retention and move.retention_rate:
				move.amount_retention = (
					move.amount_total * move.retention_rate / 100
				)
			else:
				move.amount_retention = 0.0
	
	# [ Detracciones ]
	def validate_requeriment_apply_detraction(self):
		errors = []
		for move in self:
			if not move.is_detraction:
				continue

			if move.apply_retention:
				errors.append("No se puede aplicar retención y detracción sobre un mismo comprobante.")
			
			if not move.detraction_id:
				errors.append("El comprobante no tiene asignado el concepto de detracción.")

			detractions = move.line_ids.mapped('detraction_id').filtered(lambda d: d)
			if not detractions:
				errors.append(
					"El comprobante no contiene líneas afectas a detracción."
				)
			else:
				if len(detractions) > 1:
					errors.append(
						"El comprobante contiene productos con distintas categorías de detracción. Por favor, revisar y actualizar la información de las líneas."
					)

			param = self.env['account.parameters'].search([
				('company_id', '=', move.company_id.id),
				('code', '=', 'minimum_detraction_amount')
			], limit=1)
			
			amount = abs(move.amount_total_signed)
			max_amount = param.duration if param else MAX_AMOUNT
			if param and amount <= max_amount:
				errors.append(f"Para aplicar el régimen de detracciones el importe total del comprobante debe ser mayor a {max_amount} soles.")
			
			if move.invoice_type_code_catalog_51.code not in ["1001", "1002", "1003", "1004"]:
				errors.append("Si el comprobante esta sujeto a detracción, entonces el tipo de operación es 'Operación sujeta a detracción'")
		return errors

	@api.constrains('invoice_line_ids', 'invoice_line_ids.detraction_id', 'is_detraction')
	def _check_unique_detraction(self):
		for move in self:
			if not move.is_detraction:
				continue

			detractions = move.invoice_line_ids.mapped('detraction_id').filtered(lambda d: d)
			if len(detractions) > 1:
				raise ValidationError(
					"La factura contiene productos con distintas categorías de detracción."
				)
		
	@api.depends('is_detraction', 'line_ids.detraction_id', 'line_ids.detraction_id.rate')
	def _compute_detraction(self):
		for record in self:
			if not record.is_detraction:
				record.detraction_id = False
				record.detraction_rate = 0.0
				continue

			detractions = record.line_ids.mapped('detraction_id').filtered(lambda d: d)

			if not detractions:
				record.detraction_id = False
				record.detraction_rate = 0.0
			else:
				record.detraction_id = detractions[0]
				record.detraction_rate = detractions[0].rate or 0.0
		
	@api.depends(
		'is_detraction',
		'amount_total',
		'amount_total_signed',
		'detraction_rate',
		'currency_id'
	)
	def _compute_amount_detraction(self):
		for record in self:
			if not record.is_detraction or not record.detraction_rate:
				record.amount_detraction = 0.0
				record.amount_detraction_signed = 0.0
				continue
			base_amount = record.amount_total * record.detraction_rate / 100
			base_amount_signed = abs(record.amount_total_signed) * record.detraction_rate / 100
			record.amount_detraction = record.currency_id.round(base_amount)
			record.amount_detraction_signed = record.company_currency_id.round(base_amount_signed)
			record.amount_detraction_signed_rounded = round(record.amount_detraction_signed)
	
	def open_detraction_form(self):
		self.ensure_one()
		fecha_movimiento = self.invoice_date or fields.Date.context_today(self)
		fecha_registro = self.date or fields.Date.context_today(self)
		detraction_account = False
		if self.move_type in ["out_invoice", "out_refund"]:
			company = self.company_id
			if company.default_national_bank_account_id:
				detraction_account = company.default_national_bank_account_id
			else:
				detraction_account = company.partner_id.bank_ids.filtered(
					lambda b: b.is_bank_detraction_account
				)[:1]
		elif self.move_type in ["in_invoice", "in_refund"]:
			detraction_account = self.partner_id.bank_ids.filtered(
				lambda b: b.is_bank_detraction_account
			)[:1]
		return {
			'name': "Registro de Detracción",
			'view_mode': 'form',
			'view_type': 'form',
			'res_model': 'account.detraction',
			'type': 'ir.actions.act_window',
			'target': 'new',
			'context': {
				'default_origin_move_id': self.id,
				'default_detraccion_id' : self.detraction_id.id,
				'default_fecha_movimiento' : fecha_movimiento,
				'default_fecha_registro' : fecha_registro,
				'default_fecha_pago' : fecha_registro,
				'default_communication' : self.name or 'Registro de detraccion',
				'default_amount_real' : self.amount_detraction_signed,
				'default_amount' : self.amount_detraction_signed_rounded,
				'default_national_bank_account_id': detraction_account.id if detraction_account else False,
				'default_currency_id' : self.currency_id.id,
				'origin_move_id' : self.id,
			}
		}
	
	# Validez del cpe
	@api.depends('move_type', 'state')
	@api.depends_context('uid')
	def _compute_show_validate_cpe_sunat_button(self):
		user_has_sale_group = self.env.user.has_group(
			"company_electronic_invoicing_base.group_validate_cpe_sale_sunat"
		)
		for move in self:
			show = False
			# comprobantes de proveedor
			if move.move_type in ('in_invoice', 'in_refund') and move.state in ('draft', 'posted'):
				show = True
			# comprobantes de venta (solo si tiene grupo)
			elif move.move_type in ('out_invoice', 'out_refund') and user_has_sale_group and move.state == 'posted':
				show = True

			move.show_validate_cpe_sunat_button = show
	
	def action_validate_cpe(self):
		self.ensure_one()
		# if self.l10n_latam_document_type_id.code not in ('01', '03'):
		# 	raise ValidationError('Acción inválida: No esta permitido la validez del comprobante para este tipo de documento.')
		# [ Falta validar si el cpe es de venta que el comprobante este enviado a sunat ]
		if self.move_type == 'out_invoice' and self.state != 'posted':
			raise ValidationError(
				"Las facturas de venta deben estar en estado 'Publicado' para consultar su validez."
			)
		self._request_api_check_invoice_validity()
		#Generar pdf
		return self.env.ref('company_electronic_invoicing_base.action_report_validate_cpe').report_action(self)
	
	def _request_api_check_invoice_validity(self):
		company = self.env.company
		base_url = company.validate_cpe_url
		token = self._get_token_validez_comprobante()

		if not token:
			raise UserError("No se pudo obtener el token de SUNAT.")
		if not  base_url:
			raise UserError(f"La URL consulta de consulta de validez de comprobante no está configurada para la compañía {company.name}.")

		if not base_url.endswith("/"):
			base_url += "/"

		url = f"{base_url}{company.vat}/validarcomprobante"
		
		if self.move_type == 'in_invoice':
			ruc_emisor = self.partner_id.vat
			codComp = self.l10n_latam_document_type_id.code
		elif self.move_type == 'out_invoice':
			ruc_emisor = self.company_id.vat
			codComp = self.journal_id.invoice_type_code
		else:
			raise ValidationError('Acción inválida: No esta permitido la validez del comprobante para este tipo de movimiento.')
		
		if not self.invoice_date:
			raise ValidationError("La factura no tiene fecha de emisión definida.")
		
		if "-" not in self.name:
			raise ValidationError("El nombre del comprobante no tiene el formato correcto (SERIE-NÚMERO).")
		
		serie, numero = self.name.split("-", 1)
		serie_sin_espacios = re.sub(r"\s+", "", serie)
		numero_sin_espacios = re.sub(r"\s+", "", numero)
		payload = {
			"numRuc": ruc_emisor,
			"codComp": codComp,
			"numeroSerie": serie_sin_espacios,
			"numero": numero_sin_espacios,
			"fechaEmision": self.invoice_date.strftime("%d/%m/%Y"),
			"monto": str(round(self.amount_total,2))
		}

		headers = {
			'Authorization': f"Bearer {token}",
			'Content-Type': "application/json"
		}
		try:
			response = requests.post(url, headers=headers, json=payload, timeout=30)
			response.raise_for_status()
			result = response.json()
			if result.get("success") and "data" in result:
				data = result["data"]
				estado_cpe = str(data.get("estadoCp", "-"))
				estado_ruc = str(data.get("estadoRuc", "-"))
				cond_domi_ruc = str(data.get("condDomiRuc", "-"))
				self.estado_comprobante_electronico = estado_comprobante_electronico_sunat[estado_cpe]
				self.estado_contribuyente_ruc = estado_contribuyente_ruc[estado_ruc]
				self.condicion_domicilio_contribuyente = condicion_domicilio_ruc[cond_domi_ruc]
				observaciones = data.get("observaciones") or []
				if isinstance(observaciones, list):
					self.consulta_validez_observaciones = "; ".join(observaciones)
				else:
					self.consulta_validez_observaciones = str(observaciones)
			else:
				self.consulta_validez_observaciones = result.get("message","**Error**")
		except Exception as e:
			self.consulta_validez_observaciones = str(e)
	
	def _get_token_validez_comprobante(self):
		company = self.env.company
		client_id = company.sunat_client_id
		client_secret = company.sunat_client_secret
		base_url = company.validate_cpe_token_url

		if not (client_id and client_secret and base_url):
			raise UserError(f"Las credenciales del API de consulta de validez de comprobante no están configuradas para la compañía {company.name}.")
		
		if not base_url.endswith("/"):
			base_url += "/"
		
		url = f"{base_url}{client_id}/oauth2/token/"
		
		data = {
			"grant_type": "client_credentials",
			"scope": "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes",
			"client_id": client_id,
			"client_secret": client_secret
		}
		payload = urllib.parse.urlencode(data)
		headers = {
			'Content-Type': "application/x-www-form-urlencoded",
			'User-Agent': "Odoo-Sunat-Integration-v18/1.0"
			#'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'
		}
		try:
			response = requests.post(url, data=payload, headers=headers, timeout=30)
			response.raise_for_status()
			token_data = response.json()
			return token_data.get("access_token")
		except Exception as e:
			raise UserError(f"Error al obtener token de SUNAT: {e}")

	@api.model
	def cron_action_validez_comprobante_sunat(self, limit=False, start=False, end=False, ids=False):
		today = fields.Date.today()
		# Limite de documentos a obtener de la consulta 
		limit = limit if limit else 50
		# Dominio BASE
		domain = [
			("journal_id.electronic_invoice", "=", True), # Que el diario sea para envío a SUNAT
			("name", "not in", [False, "/"]), # Que tenga nombre o número establecido
			("journal_id.invoice_type_code", "in", ["01", "03", "07", "08"]), # Que el código sea para boletas, facturas, notas de crédito y débito
			("state", "in", ["posted","cancel"]), # Que esté publicado o cancelado                
		]
		# Fecha de inicio y fin del periodo a consultar
		if start and end:
			domain += [
				("invoice_date", ">=", start),
				("invoice_date", "<=", end)
			]
		else:
			domain.append(("invoice_date", "<=", today))
		# Identificadores
		if ids:
			domain.append(("id", "in", ids))
		else:
			domain += [
				'|',
					("estado_comprobante_electronico", "in", ["-", False]), # Que el estado electrónico sea -, no existe o simplemente no tenga (consulta a SUNAT)
					'&',
						("documento_baja_id", "!=", False), # Que tenga un documento de baja asociado
						("estado_comprobante_electronico", "!=", "2_ANULADO") # Que el estado electrónico no sea anulado (consulta a SUNAT)
			]    
		invoices = self.env["account.move"].sudo().search(domain, limit=limit, order="invoice_date asc")
		for invoice in invoices:
			try:
				# SUNAT
				invoice._request_api_check_invoice_validity()
				# Commit
				self.env.cr.commit()
			except Exception as e:
				_logger.error("Error procesando factura %s (%s): %s",invoice.name, invoice.id, e)
				self._cr.rollback()

	# [ Acciones de botones ]
	def action_reverse(self):
		if self.documento_baja_id:
			raise UserError(
				"El documento fue dado de baja y no es posible emitir una nota de crédito asociado a este documento anulado.")
		return super(AccountMove, self).action_reverse()
	
	def action_view_credit_notes(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': 'Notas de Crédito',
			'res_model': 'account.move',
			'view_mode': 'list,form',
			'domain': [('reversed_entry_id', '=', self.id)],
		}

	# [ Generación de secuencia ]

	def _must_check_constrains_date_sequence(self):
		return False

	def _get_starting_sequence(self):
		self.ensure_one()

		if self.journal_id.electronic_invoice:
			prefix = self.journal_id.code or ''
			starting_sequence = f'{prefix}-00000000'
			return starting_sequence
		
		return super()._get_starting_sequence()
	
	def _set_next_sequence(self):
		"""Generar número basado en journal.code y jnq_sequence_number."""
		for move in self:
			journal = move.journal_id

			if not journal or not journal.electronic_invoice:
				super(AccountMove, move)._set_next_sequence()
				continue

			prefix = journal.code
			seq_number  = journal.jnq_sequence_number or 1

			move.sequence_prefix = prefix
			move.sequence_number = seq_number 
			move.name = f"{prefix}-{str(seq_number ).zfill(8)}"
	
	def _post(self, soft=True):
		moves = super()._post(soft=soft)

		for move in moves:
			journal = move.journal_id

			if journal and journal.electronic_invoice:

				self.env.cr.execute(
					"SELECT id FROM account_journal WHERE id = %s FOR UPDATE",
					[journal.id]
				)
				journal.flush_recordset(['jnq_sequence_number'])

				move._set_next_sequence()

				# Incrementar correlativo del diario
				journal.jnq_sequence_number = (journal.jnq_sequence_number or 1) + 1

		return moves
	
	#Override _compute_name (para compras)
	@api.depends('posted_before', 'state', 'journal_id', 'date', 'prefix_code', 'invoice_number')
	def _compute_name(self):
		for record in self:
			if not record.journal_id:
				record.name = False
				continue

			if record.state == 'cancel':
				continue

			if record.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
				if record.prefix_code and record.invoice_number:
					record.name = f"{record.prefix_code}-{record.invoice_number}"
				# else:
				# 	record.name = record.l10n_latam_document_number or '/'
			else:
				super(AccountMove, record)._compute_name()
	
	# [ Funciones relacionadas con confirmar comprobante ]

	def check_paymenttermn_lines(self):
		for record in self:
			if record.move_type == 'out_invoice':
				# Validar comprobante gratuito
				tax_codes = set(record.invoice_line_ids.mapped("tax_ids.l10n_pe_edi_tax_code"))
				if tax_codes and tax_codes == {'9996'} and record.invoice_payment_term_type == "Credito":
					raise UserError("Los comprobantes gratuitos deben ser de pago inmediato.")

				fecha_factura = record.invoice_date if record.invoice_date else fields.Date.context_today(record)
				if record.invoice_payment_term_type != "Credito":
					continue

				lines = record.paymentterm_line

				# Validar fechas vacías
				dates = [d for d in lines.mapped("date_due") if d]
				if len(dates) != len(lines):
					raise UserError("Todas las cuotas deben tener fecha de vencimiento.")
				
				# monto detracción
				amount_detraction = (
					record.amount_detraction_signed_rounded
					if record.round_amount_detraction
					else record.amount_detraction_signed
				)
				# Validar totales
				amount_total_lines = sum(lines.mapped("amount")) + amount_detraction + record.amount_retention
				if float_compare(amount_total_lines, record.amount_total, precision_digits=2) != 0:
					raise UserError(
						"El monto total de los plazos de pago debe ser igual al total de la factura."
					)
				min_date_due = min(dates)
				max_date_due = max(dates)
				if min_date_due < fecha_factura:
					raise UserError(
						"La fecha de la cuota debe ser mayor o igual a la fecha de emisión del comprobante."
					)

				if record.invoice_date_due and max_date_due > record.invoice_date_due:
					raise UserError(
						"La fecha de la cuota no debe ser mayor a la fecha de vencimiento del comprobante."
					)
	
	def _validate_inv_supplier_ref(self):
		for move in self:
			number = move.l10n_latam_document_number
			if not number:
				raise UserError("Debe ingresar el número de comprobante del proveedor.")
			serie, correlativo = number.split('-', 1)
			if int(correlativo) <= 0:
				raise UserError("El número de comprobante debe ser mayor a 0.")
			duplicate = self.search([
				('partner_id', '=', move.partner_id.id),
				('l10n_latam_document_number', '=', number),
				('l10n_latam_document_type_id', '=', move.l10n_latam_document_type_id.id),
				('move_type', 'in', ('in_invoice','in_refund')),
				('id', '!=', move.id)
			], limit=1)

			if duplicate:
				raise UserError("Este proveedor ya tiene registrado un comprobante con el mismo número.")
	
	def validar_datos_compania(self):
		errors = []
		if not self.company_id.partner_id.vat:
			errors.append(
				"* No se tiene configurado el RUC de la empresa emisora")
		elif len(self.company_id.partner_id.vat) != 11:
			errors.append(
				"* El RUC de la empresa emisora debe contener 11 dígitos.")

		if not self.company_id.partner_id.l10n_latam_identification_type_id:
			errors.append(
				"* No se tiene configurado el tipo de documento de la empresa emisora")
		elif self.company_id.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code != '6':
			errors.append(
				"* El Tipo de Documento de la empresa emisora debe ser RUC")

		if not self.company_id.partner_id.ubigeo:
			errors.append(
				"* No se encuentra configurado el Ubigeo de la empresa emisora.")
		elif len(self.company_id.partner_id.ubigeo) != 6:
			errors.append(
				"* El ubigeo de la empresa emisora debe contener 6 dígitos.")

		if not self.company_id.partner_id.street:
			errors.append(
				"* No se encuentra configurado la dirección de la empresa emisora.")
		elif len(self.company_id.partner_id.street) > 200:
			errors.append(
				"* La dirección de la empresa emisora debe poseer hasta 200 caracteres.")
		
		if not self.company_id.partner_id.name:
			errors.append(
				"* No se encuentra configurado la Razón Social de la empresa emisora.")
		elif len(self.company_id.partner_id.name) > 1500:
			errors.append(
				"* La Razón Social de la empresa emisora debe poseer hasta 1500 caracteres.")
		
		if not self.company_id.l10n_pe_edi_address_type_code:
			errors.append(
				"* No se encuentra configurado el código de establecimiento asignado por SUNAT de la empresa emisora.")
		elif len(self.company_id.l10n_pe_edi_address_type_code) != 4:
			errors.append(
				"* El código de establecimiento asignado por SUNAT de la empresa emisora debe contener 4 dígitos.")
		
		return errors
	
	def validar_datos_cliente(self):
		errors = []
		customer = self.partner_id
		# Tipo de documento y nro de documento son validados 
		# por tipo de documento en su respectiva función
		razon_social = customer.name if not customer.parent_id else customer.parent_id.name
		if not razon_social:
			errors.append(
				"* La denominación o Razón social del cliente es obligatorio.")
		elif len(razon_social) > 1500:
			errors.append(
				"* La denominación o Razón social del cliente debe poseer hasta 1500 caracteres.")
		# if not customer.street:
		# 	errors.append(
		# 		"* La dirección del cliente es obligatorio.")
		# elif len(customer.street) > 200:
		# 	errors.append(
		# 		"* La dirección del cliente debe poseer hasta 200 caracteres.")
		return errors
	
	def validar_diario(self):
		errors = []
		if self.journal_id.submission_type != self.company_id.electronic_invoicing_type_environment:
			errors.append(
				"* El tipo de envío configurado en la compañía debe coincidir con el tipo de envío del Diario que ha seleccionado.")
		if self.journal_id.jnq_sequence_number > 99999999:
			errors.append(
				"* El correlativo del comprobante ha excedido el máximo permitido (8 dígitos).")
		return errors
	
	def validar_fecha_emision(self):
		errors = []
		today = fields.Date.context_today(self)

		if not self.invoice_date:
			self.invoice_date = today
		if today < self.invoice_date:
			errors.append(
				"* La fecha de la emisión del comprobante debe ser menor o igual a la fecha del día de hoy.")
		# [ Agregar configuracion de max de dias de envío ]
		# elif abs(self.invoice_date - now).days > 3:
		# 	errors.append(
		# 		"* La fecha de Emisión debe tener como máximo una antiguedad de 3 días.")
		return errors
	
	def is_alphanum_or_empty(self,cad):
		if cad.isalnum() or cad == '':
			return True
		else:
			return False
	
	def validacion_exportacion(self):
		errors = []

		if self.invoice_type_code_catalog_51.code in ["0200","0201","0202","0203","0204","0205","0206","0207","0208"]:
			if not ( self.is_alphanum_or_empty(self.partner_id.vat or '') and self.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code == "0"):
				errors.append("El cliente debe tener tipo de documento 'DOC.TRI.SIN.RUC' y número de documento alfanumérico")

			if "40" not in self.invoice_line_ids.mapped("tax_ids.tax_group_id.tipo_afectacion"):
				errors.append("El comprobante de exportación debe tener todas sus líneas con el impuesto de exportación.")
			for prod in self.invoice_line_ids.mapped("product_id"):
				if not prod.sunat_code or not bool(re.compile(r"\d{8}$").match(prod.sunat_code.code)):
					errors.append("El código sunat del producto {} no es válido.".format(prod.sunat_code.code))
		return errors

	def validacion_lineas_comprobante(self):
		errors = []
		for record in self:
			lines = record.invoice_line_ids.filtered(lambda r: r.display_type == 'product' and r.product_id != r.company_id.sale_discount_product_id)
			for i, line in enumerate(lines, start=1):
				if not line.product_id:
					errors.append(f"* La linea nro {i} no tiene producto seleccionado.")
					continue
				code = line.product_id.default_code or ""
				name = line.product_id.name or ""
				if not code:
					errors.append(
						f"* El item {name} no tiene configurado el código de producto.")
				elif len(code) > 30:
					errors.append(
						f"* El código del producto {name} debe tener hasta 30 caracteres.")
				
				if len(name) > 500:
					errors.append(
						f"* El nombre del producto {name} debe tener hasta 500 caracteres.")
				
				# Unidades de medida
				# Los productos tipo Servicio siempre se envían con código 'ZZ'
				# (ver pecano_fact/utils.py), sin importar la unidad de medida
				# elegida, así que no exigimos el código SUNAT en la unidad acá.
				uom = line.product_uom_id
				if line.product_id.type == 'service':
					pass
				elif not uom:
					errors.append(f"* El producto {name} no tiene unidad de medida seleccionada.")
				else:
					sunat_uom_code = (uom.l10n_pe_edi_measure_unit_code.code or '').strip()
					if not sunat_uom_code:
						errors.append(
							f"* El producto {name} no tiene código SUNAT de unidad de medida.")
					elif len(sunat_uom_code) > 3:
						errors.append(
							f"* El código SUNAT de la UDM del producto {name} debe tener hasta 3 caracteres.")
				# Impuestos
				if not line.tax_ids:
					errors.append(
						"* El producto {name} debe tener al menos un tipo de impuesto asociado.")
				for tax in line.tax_ids:
					if not tax.l10n_pe_edi_affectation_reason:
						errors.append(
							"* El tipo de afectación al IGV no esta configurado para el IMPUESTO %s del item %s" % (tax.name, line.name))
		return errors
				
	def validacion_factura(self):
		errors = []
		for record in self:
			partner = record.partner_id
			identification_type = partner.l10n_latam_identification_type_id
			vat = partner.vat or ""

			if not identification_type:
				errors.append(
					"* El tipo de documento de identidad del cliente es obligatorio.")

			if not vat:
				errors.append(
					"* El número de identificación del cliente es obligatorio.")
			
			if not record.invoice_type_code_catalog_51:
				errors.append(
					"* El tipo de operación del comprobante es obligatorio.")
				continue
			
			code = record.invoice_type_code_catalog_51.code
			vat_code = identification_type.l10n_pe_vat_code if identification_type else False
		
			# Validar formato RUC
			if vat_code == "6":
				if not vat.isdigit() or len(vat) != 11:
					errors.append("* El RUC del cliente debe tener 11 dígitos.")
			# Validar operacion 'Venta interna'
			if code == "0101":
				amount = abs(record.amount_total_signed)
				param = self.env['account.parameters'].search([
					('company_id', '=', record.company_id.id),
					('code', '=', 'mandatory_identification')
				], limit=1)
				max_amount_total = param.duration if param else MAX_AMOUNT
				if amount <= max_amount_total:
					# 0: Doc.trib.no.dom.sin.ruc 
					# 4: Carnet de extranjería
					# 6: RUC
					# 7: Pasaporte
					if vat_code not in ["0","4","6","7"]:
						errors.append(
							"* El tipo de documento del cliente no es válido para la emisión de este comprobante.")
				else:
					if vat_code != "6":
						errors.append(
							f"* El cliente seleccionado debe tener como tipo de documento RUC para emitir FACTURAS mayores o iguales a {max_amount_total} soles."
						)
			# Validar lineas de factura
			if code not in ["0200","0201","0202","0203","0204","0205","0206","0207","0208","0101"]:
				errors.extend(record.validacion_lineas_comprobante())			
		return errors
	
	def validacion_boleta(self):
		errors = []
		# 0: Doc.trib.no.dom.sin.ruc
		# 1: DNI
		# 4: Carnet de extranjería
		# 6: RUC
		# 7: Pasaporte
		# -: Cliente varios
		for record in self:
			partner = record.partner_id
			identification_type = partner.l10n_latam_identification_type_id
			vat = partner.vat or ""

			if not identification_type:
				errors.append(
					"* El tipo de documento de identidad del cliente es obligatorio.")

			if not vat:
				errors.append(
					"* El número de identificación del cliente es obligatorio.")
			
			if not record.invoice_type_code_catalog_51:
				errors.append(
					"* El tipo de operación del comprobante es obligatorio.")
				continue
			
			code = record.invoice_type_code_catalog_51.code
			vat_code = identification_type.l10n_pe_vat_code if identification_type else False
			
			if code not in ["0200","0201","0202","0203","0204","0205","0206","0207","0208"]:
				param = self.env['account.parameters'].search([
					('company_id', '=', record.company_id.id),
					('code', '=', 'mandatory_identification')
				], limit=1)
				max_amount_total = param.duration if param else MAX_AMOUNT

				if abs(record.amount_total_signed) >= max_amount_total:
					if vat_code not in ["1", "4", "6", "7"]:
						errors.append(
							f"* El tipo de documento de identidad del cliente debe ser DNI/RUC/CE/Pasaporte. Obligatorio para BOLETAS de venta mayores o iguales a {max_amount_total} soles.")
						continue

					if vat_code == '1':
						if not vat.isdigit() or len(vat) != 8:
							errors.append(
								"* El DNI del cliente debe tener 8 dígitos.")
					elif vat_code == '6':
						if not vat.isdigit() or len(vat) != 11:
							errors.append(
								"* El RUC del cliente debe tener 11 dígitos.")
				else:
					if vat_code not in ["0", "1", "4", "6", "7", "-"]:
						errors.append(
							"* Tipo de documento no permitido para boletas."
						)
						continue
					if vat_code == '1':
						if not vat.isdigit() or len(vat) != 8:
							errors.append(
								"* El DNI del cliente selecionado debe tener 8 dígitos.")
					elif vat_code == '6':
						if not vat.isdigit() or len(vat) != 11:
							errors.append(
								"* El RUC del cliente debe tener 11 dígitos.")
				errors.extend(record.validacion_lineas_comprobante())
		return errors
	
	def validacion_nota_credito(self):
		errors = []
		lines = self.invoice_line_ids.filtered(lambda r: r.product_id == r.company_id.sale_discount_product_id)
		if lines:
			errors.append(
				"* No es posible aplicar un descuento global a una Nota de crédito. Esta opción solo esta disponible para Facturas y Boletas")
		return errors
	
	def action_generate_and_signed_xml(self):
		# [ PENDIENTE IMPLEMENTACIÓN ]
		pass

	def action_send_invoice(self):
		# [ PENDIENTE IMPLEMENTACIÓN ]
		pass

	def btn_comunicacion_baja(self):
		# [ PENDIENTE IMPLEMENTACIÓN ]
		pass

	def action_validez_comprobante(self):
		self.ensure_one()
		if self.state not in ('posted', 'cancel'):
			raise ValidationError("Solo se puede realizar la consulta de validez de documentos publicados.")
		if self.current_log_status_id:
			self.current_log_status_id.action_request_status_invoice()

	def action_post(self):
		for move in self:
			if move.journal_id not in move.suitable_journal_ids:
				raise ValidationError("La serie no es valida para este documento, verifica que este en 'Series permitidas'")
			move.check_paymenttermn_lines()
			if not move.company_id.sunat_provider or move.journal_id.invoice_type_code not in ['01', '03', '07', '08', '09', '31']:
				return super(AccountMove, move).action_post()
			else:
				if move.move_type in ["in_invoice", "in_refund", "in_receipt"]:
					move._validate_inv_supplier_ref()
					return super(AccountMove, move).action_post()

				if not move.journal_id.electronic_invoice:
					return super(AccountMove, move).action_post()
				else:
					msg_error = []
					# [ Validar retencion ]
					msg_error += move.validate_requeriment_apply_retention()
					# [ Validar detraccion ]
					msg_error += move.validate_requeriment_apply_detraction()
					msg_error += move.validar_datos_compania()
					msg_error += move.validar_datos_cliente()
					msg_error += move.validar_diario()

					####### GROUP_USER PARA EMISIÓN FUERA DE PLAZO #######
					current_user = self.env.user

					if not current_user.has_group('company_electronic_invoicing_base.group_user_sunat_send_out_date'):
						msg_error += move.validar_fecha_emision()
					###############################

					msg_error += move.validacion_exportacion()

					if move.journal_id.invoice_type_code == "01":
						msg_error += move.validacion_factura()
						if len(msg_error) > 0:
							msg = "\n\n".join(msg_error)
							raise UserError(msg)

					if move.journal_id.invoice_type_code == "03":
						msg_error += move.validacion_boleta()
						if len(msg_error) > 0:
							msg = "\n\n".join(msg_error)
							raise UserError(msg)

					if move.journal_id.invoice_type_code == "07":
						msg_error += move.validacion_nota_credito()
						if len(msg_error) > 0:
							msg = "\n\n".join(msg_error)
							raise UserError(msg)
					
					# [ Registro de detraccion ]
					if move.is_detraction:
						if not move.register_detraction_id:
							return move.open_detraction_form()

					result = super(AccountMove, move).action_post()

					move.action_generate_and_signed_xml()

					if not move.journal_id.send_async:
						move.action_send_invoice()

					return result

	def get_amount_totals(self):
		self.ensure_one()
		totals = self.tax_totals

		total_gravada = 0.0
		total_inafecta = 0.0
		total_exonerada = 0.0
		total_igv = 0.0
		total_isc = 0.0
		total_impuestos_bolsas = 0.0
		total_gratuita = 0.0 
		total_otros_cargos = 0.0
		total_descuento_por_lineas = 0.0

		total_descuento_global = sum(
			line.quantity * abs(line.price_subtotal)
			for line in self.invoice_line_ids
			if line.display_type == 'product' and line.product_id == line.company_id.sale_discount_product_id
		)

		base_sin_descuento = sum(
			abs(line.price_subtotal)
			for line in self.invoice_line_ids
			if (
				line.display_type == 'product'
				and line.price_unit > 0
				and line.product_id != line.company_id.sale_discount_product_id
			)
		)

		porcentaje_descuento_global = 0.0
		importe_descuento_global_con_igv = 0.0
		if base_sin_descuento > 0:
			porcentaje_descuento_global = round(
				(total_descuento_global / base_sin_descuento), 2
			)
		if total_descuento_global > 0:
			igv_descuento = total_descuento_global * 0.18
			importe_descuento_global_con_igv = round(
				total_descuento_global + igv_descuento,
				2
			)

		for subtotals in totals.get('subtotals', []):
			for tax_group in subtotals.get('tax_groups', []):
				tax_group_id = self.env['account.tax.group'].browse(tax_group['id'])
				edi_code = tax_group_id.l10n_pe_edi_code.upper()
				base = tax_group.get('base_amount', 0.0)
				amount = tax_group.get('tax_amount', 0.0)

				if edi_code == 'IGV':
					total_gravada += base
					total_igv += amount
				elif edi_code == 'EXO':
					total_exonerada += base
				elif edi_code == 'INA':
					total_inafecta += base
				elif edi_code == 'FACTURA GRATUITA':
					total_gratuita += base
				elif edi_code == 'ISC':
					total_isc += amount
				elif edi_code == 'ICBPER':
					total_impuestos_bolsas += amount

		total = self.currency_id.round(self.amount_total)
		lines = self.invoice_line_ids.filtered(lambda r: r.display_type == 'product' and r.product_id != r.company_id.sale_discount_product_id)
		for line in lines:
			compute_all_origin = line.tax_ids.compute_all(
				line.price_unit,
				currency=line.move_id.currency_id,
				quantity=line.quantity,
				product=line.product_id,
				partner=line.move_id.partner_id,
				is_refund=line.is_refund,
				handle_price_include=True,
				include_caba_tags=line.move_id.always_tax_exigible,
				# fixed_multiplicator=sign,
			)
			descuento_linea = round(compute_all_origin['total_excluded'],2) - abs(round(line.price_subtotal,2))
			total_descuento_por_lineas += descuento_linea
		
		total_descuento = total_descuento_por_lineas + total_descuento_global

		return {
			'total_gravada': total_gravada,
			'total_inafecta': total_inafecta,
			'total_exonerada': total_exonerada,
			'total_igv': total_igv,
			'total_isc': total_isc,
			'total_impuestos_bolsas': total_impuestos_bolsas,
			'total_gratuita': total_gratuita,
			'total_otros_cargos': total_otros_cargos,
			'total_descuento': total_descuento,
			'total_descuento_global': abs(total_descuento_global),
			'porcentaje_descuento_global': porcentaje_descuento_global,
			'total_descuento_global_con_igv': importe_descuento_global_con_igv,
			'total': total
		}

	# [ Cron Facturación Electrónica]
	# @api.model
	# def cron_actualizacion_estado_emision_sunat(self):
	# 	comprobantes = self.env["account.move"].sudo().search([
	# 		["estado_comprobante_electronico", "=", "1_ACEPTADO"]
	# 	]).mapped("current_log_status_id")
	# 	comprobantes.sudo().write({"status": "A"})
	# 	return True

class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	detraction_id = fields.Many2one('sunat.catalog.54',
		string="Detracción",
		compute="_compute_detraccion_type", 
		store=True
	)

	@api.depends('product_id', 'product_id.product_tmpl_id.detraction_id')
	def _compute_detraccion_type(self):
		for line in self:
			line.detraction_id = (
				line.product_id.product_tmpl_id.detraction_id
				if line.product_id
				else False
			)

class AccountMoveReversal(models.TransientModel):
	_inherit = 'account.move.reversal'

	tipo_comprobante_a_rectificar = fields.Selection(selection=[("00", "Otros"), ("01", "Factura"), ("03", "Boleta")])
	journal_type = fields.Selection(selection=[("sale", "Ventas"), ("purchase", "Compras")], string="Tipo de diario")
	l10n_pe_edi_refund_reason = fields.Selection(
		selection_add=[
			('13', 'Corrección del monto neto, fechas de pago o montos de las cuotas'),
		],
		ondelete={
			'13': 'cascade',
		},
	)

	@api.constrains("reason")
	def _check_reason(self):
		for record in self:
			reason = (record.reason or "").strip()
			if not reason:
				raise UserError('El motivo de la nota de crédito es obligatorio.')
			elif len(reason) > 500:
				raise UserError('El motivo de la nota de crédito debe tener hasta 500 carácteres.')

	@api.model
	def default_get(self, fields):
		res = super(AccountMoveReversal, self).default_get(fields)
		move_ids = self.env['account.move'].browse(self.env.context['active_ids']) if self.env.context.get('active_model') == 'account.move' else self.env['account.move']
		# res['refund_method'] = (len(move_ids) > 1 or move_ids.move_type == 'entry') and 'cancel' or 'refund'
		res['residual'] = len(move_ids) == 1 and move_ids.amount_residual or 0
		res['currency_id'] = len(move_ids.currency_id) == 1 and move_ids.currency_id.id or False
		res['move_type'] = len(move_ids) == 1 and move_ids.move_type or False
		res['move_ids'] = move_ids if move_ids else False
		res['tipo_comprobante_a_rectificar'] = move_ids[0].journal_id.invoice_type_code if move_ids else False
		res['journal_type'] = move_ids[0].journal_id.type if move_ids else False

		if move_ids.exists():
			journals = self.env["account.journal"].sudo().search(
				[('tipo_comprobante_a_rectificar', '=', res['tipo_comprobante_a_rectificar']), 
				("invoice_type_code", "=", "07"),
				("company_id", "=", self.env.company.id),
				("type", "=", res['journal_type'])]).ids
			res['journal_id'] = journals[0] if len(journals) > 0 else False
		else:
			res['journal_id'] = False

		return res

	def _prepare_default_reversal(self, move):
		values = super()._prepare_default_reversal(move)
		values.update({
			"sustento_nota": self.reason,
			"tipo_nota_credito": self.l10n_pe_edi_refund_reason,
			"invoice_type_code": "07"
		})
		# if self.l10n_pe_edi_refund_reason in ["04"]:
		#     res.update({"line_ids": []})
		return values
	
	# def refund_moves(self):
	#     if self.l10n_pe_edi_refund_reason in ['02', '03', '10', '11', '12']:
	#         raise UserError("Este tipo de nota de crédito requiere una modificación, no una anulación.")
	#     return self.reverse_moves(is_modify=False)

	# def modify_moves(self):
	#     if self.l10n_pe_edi_refund_reason not in ['02', '03', '10', '11', '12']:
	#         raise UserError("Este tipo de nota de crédito no requiere una nueva factura, debe usarse el botón de anulación o devolución.")
	#     return self.reverse_moves(is_modify=True)