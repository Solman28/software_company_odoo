# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare

import logging
_logger = logging.getLogger(__name__)

class AccountDetraction(models.Model):
	_name = "account.detraction"
	_inherit = ['mail.thread', 'mail.activity.mixin']
	_description = "Registro de Detracciones"

	@api.model
	def _get_operation_type_selection(self):
		type = [
			('01', '01 - Venta de bienes o prestación de servicios'),
			('02', '02 - Retiro de bienes'),
			('03', '03 - Traslados que no son venta'),
			('04', '04 - Venta bolsa de productos'),
			('05', '05 - Venta de Bienes exonerados del IGV')
		]
		return type

	# compute_residual para casos donde detraction_journal_id.account_id == destination_account_id
	def _get_aml_for_amount_residual(self):
		""" Get the aml to consider to compute the amount residual of invoices """
		#self.ensure_one()
		aml_counterparts = self.sudo().move_id.line_ids.filtered(lambda l: l.account_id != self.destination_account_id) or \
			self.sudo().move_id.line_ids.filtered(lambda l: l.account_id == self.destination_account_id and l.balance>0)
		return aml_counterparts
	##################################################################
	@api.depends(
		'state', 'currency_id',
		'move_id.line_ids.amount_residual',
		'move_id.line_ids.currency_id')
	def _compute_residual(self):
		#self.ensure_one()
		for rec in self:
			residual = 0.0
			residual_company_signed = 0.0

			if rec.move_id:

				for line in rec._get_aml_for_amount_residual():

					residual_company_signed += line.amount_residual
					if line.currency_id == rec.currency_id:
						residual += line.amount_residual_currency if line.currency_id else line.amount_residual
					else:
						if line.currency_id:
							residual += line.currency_id._convert(line.amount_residual_currency, 
								rec.currency_id, line.company_id, line.date or fields.Date.today())

						else:
							residual += line.company_id.currency_id._convert(line.amount_residual, rec.currency_id, 
								line.company_id, line.date or fields.Date.today())

				rec.residual = abs(residual)
				digits = rec.currency_id.rounding
				if float_is_zero(rec.residual, precision_rounding=digits):
					rec.reconciled = True
				else:
					rec.reconciled = False


	journal_id = fields.Many2one('account.journal',
		string="Diario", 
		required=True, tracking=True,
		domain="[('detraction', '=', True), ('company_id', '=', company_id)]"
	)
	currency_id = fields.Many2one('res.currency', 
		string='Moneda',
		readonly=True
	)
	company_currency_id = fields.Many2one('res.currency', 
		string='Moneda compañía',
		readonly=True, required=True, 
		default=lambda self: self.env.user.company_id.currency_id
	)
	company_id = fields.Many2one('res.company', 
		compute='_compute_company_id', 
		string='Compañía', 
		store=True
	)
	round_amount_detraction = fields.Boolean(string="Redondear importe de detracción", 
		related="origin_move_id.round_amount_detraction",
		tracking=True, 
		help="Si esta activo se tomará el monto redondeado de la detracción."
	)
	amount_real = fields.Monetary(string='Monto Detracción', 
		related="origin_move_id.amount_detraction_signed",
		required=True,
		tracking=True,
		currency_field='company_currency_id'
	)
	amount = fields.Monetary(string='Monto Detracción redondeado', 
		related="origin_move_id.amount_detraction_signed_rounded",
		required=True, tracking=True,
		currency_field='company_currency_id'
	)
	nro_constancia = fields.Char(string="Nro. de Constancia", 
		tracking=True, copy=False
	)
	fecha_pago = fields.Date(string="Fecha de pago", 
		tracking=True, copy=False
	)
	fecha_registro = fields.Date(string="Fecha de registro", 
		tracking=True, required=True
	)
	detraccion_id = fields.Many2one('sunat.catalog.54',
		related="origin_move_id.detraction_id",
		string="Detracción", 
		readonly=True, required=True
	)
	fecha_movimiento = fields.Date(string="Fecha de movimiento", 
		tracking=True, required=True
	)
	communication = fields.Char(string='Concepto', 
		tracking=True, required=True
	)
	origin_move_id = fields.Many2one('account.move', 
		string="Documento",
		tracking=True, copy=False
	)
	state_origin_move_id = fields.Selection(related="origin_move_id.state", string="Estado del documento origen")
	partner_id = fields.Many2one('res.partner', 
		related="origin_move_id.partner_id",
		string="Empresa"
	)
	move_id = fields.Many2one('account.move', 
		string="Asiento contable", 
		readonly=True, copy=False
	)
	state = fields.Selection(selection=[('draft','Borrador'),('posted','Publicado'),('cancel','Cancelado')],
		string="Estado", 
		default="draft",
		tracking=True, readonly=True
	)
	pay_state = fields.Selection(selection=[('to_pay', ' A Pagar'), ('paid','Pagado')], 
		string="Estado de Pago", 
		default='to_pay',
		tracking=True
	)
	destination_account_id = fields.Many2one('account.account', 
		string="Cuenta destino", 
		tracking=True
	)
	residual = fields.Monetary(string="Importe adeudado",
		compute='_compute_residual', 
		store=True, 
		currency_field='company_currency_id'
	)
	reconciled = fields.Boolean(string="reconciled", 
		compute="_compute_residual", 
		store=True
	)
	operation_type = fields.Selection(selection=_get_operation_type_selection,
		string="Tipo de Operación", 
		required=True, default='01',
		tracking=True
	)
	suitable_national_bank_account_ids = fields.Many2many(
		"res.partner.bank", "acc_detraction_partner_bank_rel",
		"acc_detraction_id", "partner_bank_id",
		compute="_compute_suitable_national_bank_account_ids"
	)
	national_bank_account_id = fields.Many2one(
		"res.partner.bank", 
		string="Número de cuenta", 
		domain="[('id', 'in', suitable_national_bank_account_ids)]",
		tracking=True, required=True
	)
	payment_method_id = fields.Many2one("sunat.catalog.59", 
		string="Medio de Pago", 
		default=lambda self: self.env.ref("company_electronic_invoicing_base.catalog_59_001", raise_if_not_found=False),
		tracking=True
	)

	@api.depends('origin_move_id')
	def _compute_company_id(self):
		for record in self:
			company = self.env.company
			if record.origin_move_id and record.origin_move_id.company_id:
				company = record.origin_move_id.company_id
			record.company_id = company
	
	@api.depends('origin_move_id', 'origin_move_id.state', 'company_id.default_national_bank_account_id', 'partner_id.bank_ids')
	def _compute_suitable_national_bank_account_ids(self):
		for record in self:
			move = record.origin_move_id
			company = record.company_id
			if move and move.move_type in ["out_invoice", "out_refund"]:
				if company.default_national_bank_account_id:
					detraction_account_ids = company.default_national_bank_account_id
				else:
					detraction_account_ids = company.partner_id.bank_ids.filtered(
						lambda b: b.is_bank_detraction_account
					)
			elif move and move.move_type in ["in_invoice", "in_refund"]:
				detraction_account_ids = record.partner_id.bank_ids.filtered(
					lambda b: b.is_bank_detraction_account
				)
			else:
				if company.default_national_bank_account_id:
					detraction_account_ids = company.default_national_bank_account_id
				else:
					detraction_account_ids = company.partner_id.bank_ids.filtered(
						lambda b: b.is_bank_detraction_account
					)
			record.suitable_national_bank_account_ids = detraction_account_ids

	def action_open_view_move(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': self.move_id.name,
			'res_model': 'account.move',
			'view_type': 'form',
			'view_mode': 'form',
			'res_id': self.move_id.id,
			'context': {
				'create': False,
				'delete':False,
			}
		}    

	@api.onchange('origin_move_id')
	def _onchange_destination_account(self):
		origin_move_id = self.origin_move_id
		if origin_move_id:
			if origin_move_id.move_type == 'out_invoice':
				self.destination_account_id = origin_move_id.partner_id.property_account_receivable_id
			elif origin_move_id.move_type == 'in_invoice':
				self.destination_account_id = origin_move_id.partner_id.property_account_payable_id

			self.amount_real = origin_move_id.amount_detraction_signed
			self.amount = origin_move_id.amount_detraction_signed_rounded
			self.fecha_registro = origin_move_id.date or fields.Date.context_today(self)
			self.fecha_movimiento = origin_move_id.invoice_date

	def action_cancel_detraccion(self):
		for record in self:
			if record.origin_move_id.state == 'posted':
				raise ValidationError("No se puede cancelar una detraccion asociada a una factura en estado Publicado.")
			
			if record.move_id and record.move_id.line_ids:
				move_id = record.move_id.id
				record.move_id = self.env["account.move"]
				self._cr.execute("DELETE FROM account_move_line WHERE move_id=%s"%(move_id))
				self._cr.execute("DELETE FROM account_move WHERE id=%s"%(move_id))

			record.write({'state':'cancel'})
			record.origin_move_id.register_detraction_id = False

	def action_draft_detraccion(self):
		self.ensure_one()
		self.write({'state':'draft'})

	def unlink (self):
		for line in self:
			if line.move_id and line.move_id.line_ids:
				line_move_id = line.move_id.id
				self._cr.execute("DELETE FROM account_move_line WHERE move_id=%s"%line_move_id)
				self._cr.execute("DELETE FROM account_move WHERE id=%s"%line_move_id)
			
			return super(AccountDetraction,line).unlink()

	def action_validate_detraction(self):
		self.ensure_one()
		errors = []
		if self.state != 'draft':
			errors.append("Solo se puede publicar el registro de detracción en estado Borrador.")
		if self.round_amount_detraction:
			detraccion_amount = self.amount
		else:
			detraccion_amount = self.amount_real
		if detraccion_amount <= 0:
			errors.append("El monto de la detracción debe ser mayor a cero")
		if not self.nro_constancia:
			errors.append("Es obligatorio establecer el número de constancia.")
		if not self.fecha_pago:
			errors.append("Es obligatorio establecer la fecha de pago.")
		if not self.journal_id:
			errors.append("Es obligatorio establecer el diario.")
		else:
			if not self.journal_id.default_account_id:
				errors.append("No esta configurado la cuenta predeterminada del diario de detracciones.")
		if not self.national_bank_account_id:
			errors.append("Es obligatorio establecer el nro de cuenta.")
		if errors:
			raise UserError("Se detectaron los siguientes errores:\n" + "\n".join(errors))
		if not self.currency_id:
			self.currency_id = self.company_currency_id
		# Create the journal entry
		origin_move_id = self.origin_move_id
		sign = origin_move_id.direction_sign
		amount = detraccion_amount * sign
		move = self._create_detraction_entry(amount)
		self.pay_state = 'paid'
		self.write({'state': 'posted', 'residual': detraccion_amount})
		return True

	def _get_move_vals(self, journal=None):
		journal = journal or self.journal_id
		move_vals = {
			'date': self.fecha_registro,
			'ref': self.communication,
			'company_id': self.company_id.id,
			'journal_id': journal.id,
			'move_type':'entry',
		}
		return move_vals

	def _create_detraction_entry(self, amount):
		aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
		debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.origin_move_id.invoice_date or self.fecha_pago)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)
		move = self.move_id
		if not move:
			move = self.env['account.move'].create(self._get_move_vals())
			self.move_id = move.id
		invoice_id = self.origin_move_id
		if not invoice_id:
			raise UserError("Para publicar el registro de detracción se necesita una factura de origen.")
		# Write line corresponding to invoice payment
		aml_dict = {}
		if invoice_id.move_type in ["in_invoice","in_refund"]:
			aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, invoice_id)
		elif invoice_id.move_type in ["out_invoice"]:
			aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, invoice_id)
		aml_dict.update(account_id=self.destination_account_id.id)
		#counterpart_aml = aml_obj.create(aml_dict)
		# Write counterpart lines
		liquit = False
		if not self.currency_id.is_zero(amount):
			if invoice_id.move_type in ["in_invoice","in_refund"]:
				liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, invoice_id)
			elif invoice_id.move_type in ["out_invoice"]:
				liquidity_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, invoice_id)
			liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
			#liquit = aml_obj.create(liquidity_aml_dict)
		move.write({
			"line_ids":[
				(5,0,0),
				(0,0,liquidity_aml_dict),
				(0,0,aml_dict)
			]
		})
		if move.state == 'draft':
			move.action_post()
		return move

	def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
		line_vals = {
			'partner_id': self.env['res.partner']._find_accounting_partner(self.partner_id).id or False,
			'move_id': move_id,
			'debit': debit,
			'credit': credit,
			'amount_currency': amount_currency or False,
			'journal_id': self.journal_id.id,
			'detraction_id' : self.id,
			'nro_constancia' : self.nro_constancia,
			'name': self.communication or invoice_id.name or _('Detracción %s') % self.nro_constancia,
			'currency_id' : self.currency_id.id, # != self.company_id.currency_id and self.currency_id.id or False,
		}
		return line_vals

	def _get_liquidity_move_line_vals(self, amount):
		account_id = self.journal_id.default_account_id.id #(self.origin_move_id.move_type in ['in_invoice', 'out_refund'] and self.journal_id.default_debit_account_id.id) or (self.origin_move_id.move_type in ['out_invoice', 'in_refund'] and self.journal_id.default_account_id.id)
		vals = {
			'account_id': account_id,
			'journal_id': self.journal_id.id,
			'currency_id': self.currency_id.id #self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
		}
		return vals
	
	@api.depends('origin_move_id', 'origin_move_id.name', 'fecha_pago', 'detraccion_id')
	def _compute_display_name(self):
		for record in self:
			if record.origin_move_id and record.origin_move_id.name:
				record.display_name = f"{record.origin_move_id.name} ({record.fecha_pago or ''}) - {record.detraccion_id.name}"
			else:
				record.display_name = f"Detracción ({record.fecha_pago or ''}) - {record.detraccion_id.name}"

	@api.model_create_multi
	def create(self, vals_list):
		detractions = super().create(vals_list)
		for detraction, vals in zip(detractions, vals_list):
			origin_move_id = vals.get('origin_move_id')
			if origin_move_id:
				invoice = self.env['account.move'].browse(origin_move_id)
				invoice.write({
					'register_detraction_id': detraction.id
				})
		return detractions

	def action_detraction_paid(self):
		detractions = self.filtered(lambda d: d.pay_state != 'paid')
		if detractions.filtered(lambda d: not d.reconciled):
			raise UserError(_("You cannot pay an detraction to pay which is partially paid. You neet to reconcile payment entries first."))
		for d in detractions:
			vals = {
				'pay_state': 'paid',
			}
			if not d.nro_constancia:
				move_line = d.move_id.line_ids.filtered(lambda aml: aml.account_id != d.destination_account_id)
				if move_line.full_reconcile_id:
					move_line_cpart = move_line.full_reconcile_id.reconciled_line_ids.filtered(lambda aml: aml.move_id != d.move_id)
					vals.update(
						nro_constancia = move_line_cpart[0].move_id.nro_constancia,
						fecha_pago = move_line_cpart[0].move_id.date)
					move_line.move_id.write({'nro_constancia': move_line_cpart[0].move_id.nro_constancia})
			d.write(vals)

	def action_detraction_re_open(self):
		if self.filtered(lambda d: d.pay_state != 'paid'):
			raise UserError(_('Detraction must be paid in order to set it register payment'))
		return self.write({'pay_state':'to_pay'})
	
	def _write(self, vals):
		pre_not_reconciled = self.filtered(lambda d: not d.reconciled)
		pre_reconciled = self - pre_not_reconciled
		res = super(AccountDetraction, self)._write(vals)
		reconciled = self.filtered(lambda d: d.reconciled)
		not_reconciled = self - reconciled
		(reconciled & pre_reconciled).filtered(lambda d: d.state == 'posted' and d.pay_state == 'to_pay').action_detraction_paid()
		(not_reconciled & pre_not_reconciled).filtered(lambda d: (d.state == 'posted' and d.pay_state == 'paid' and not d.origin_move_id) or (d.state == 'posted' and d.pay_state == 'paid' and d.origin_move_id.move_type in ['in_invoice','out_refund','out_invoice'])).action_detraction_re_open()
		return res