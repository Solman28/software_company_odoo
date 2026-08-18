from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging
import re
from pytz import timezone
_logger = logging.getLogger(__name__)


class AccountComunicacionBaja(models.Model):
	_name = "account.comunicacion_baja"
	_description = "Documento de baja"
	_rec_name = "identificador_anulacion"

	date_invoice = fields.Date(string='Fecha de emisión de factura', required=True, copy=False)
	voided_date = fields.Date(string='Fecha de anulación', required=True, copy=False)
	user_id = fields.Many2one('res.users', string='Usuario', readonly=True, required=True, default=lambda self: self.env.user)
	company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Moneda de la compañía", readonly=True)
	json_comprobante = fields.Text(string="JSON de envio")
	json_respuesta = fields.Text(string="JSON de respuesta")
	json_estado_comunicacion_baja = fields.Text(string="JSON estado de Comunicación de Baja")
	descripcion_estado_com_baja = fields.Text(string="Descripción de estado de Comunicación de Baja")
	ticket = fields.Char(string="Ticket")
	current_log_status_id = fields.Many2one('account.log.status',copy=False)
	account_log_status_ids = fields.One2many("account.log.status", "account_voided_id", string="Registro de Envíos", copy=False)
	voided_ticket = fields.Char(string="Ticket",related="current_log_status_id.voided_ticket",store=True)
	identificador_anulacion = fields.Char(string="Identificador de anulación", related="current_log_status_id.name")
	state = fields.Selection(string="Estado Emision a SUNAT", copy=False, related="current_log_status_id.status", store="True")
	voided_sequence = fields.Integer(string="Sec. de envío del día")
	motivo = fields.Text(string="Motivo de Baja", required=True)
	invoice_id = fields.Many2one('account.move', string='Comprobante')
	invoice_ids = fields.One2many('account.move', 'documento_baja_id', string='Comprobantes relacionados', compute="_compute_invoice_ids", store=True, help='Comprobantes relacionados al comprobante a anular.', domain="[('state', '=', 'posted'),('estado_comprobante_electronico','=','1_ACEPTADO')]", readonly=False)
	#invoice_ids = fields.One2many('account.move', "documento_baja_id")
	invoice_type_code_id = fields.Selection(string="Tipo de Comprobante", selection=[('01', 'Factura'), ('03', 'Boleta'), ('07', 'Nota de crédito'), ('08', 'Nota de débito')], readonly=True)
	company_id = fields.Many2one('res.company', string='Compañia',required=True, readonly=True,default=lambda self: self.env.company.id)
	
	@api.constrains("motivo")
	def _check_motivo(self):
		for record in self:
			motivo = (record.motivo or "").strip()
			if not motivo:
				raise UserError('El motivo de la anulación es obligatorio.')
			elif len(motivo) < 3 or len(motivo) > 100:
				raise UserError('El motivo de la anulación debe tener entre 3 a 100 carácteres.')
	
	def validate_invoice_ids(self, day_maximum):
		errors = []
		for record in self:
			now =  datetime.date(datetime.now(tz=timezone(self.env.user.tz or "America/Lima")))
			for invoice in record.invoice_ids:
				if now < invoice.invoice_date:
					errors.append(f"* {invoice.name}: La fecha de emisión del comprobante debe ser menor o igual a la fecha del día de hoy.")
				elif abs(invoice.invoice_date - now).days > day_maximum.duration:
					errors.append(f"* {invoice.name}: No se puede enviar documentos con más de {day_maximum.duration} días de antiguedad. De ser el caso genere una Nota de Crédito.")
		return errors
	
	# [ OBTENER: DOCUMENTOS ELECTRÓNICOS RELACIONADOS AL COMPROBANTE PADRE ]
	@api.depends('invoice_id')
	def _compute_invoice_ids(self):
		for record in self:
			record.invoice_ids = [(6,0,[])]
			if record.invoice_id:
				invoices = record.invoice_id
				domain = [('state','=','posted'), ('estado_comprobante_electronico', 'not in', ('0_NO_EXISTE', '2_ANULADO', '-', '4_NO_AUTORIZADO'))]
				# [ BUSCAR: NOTAS DE CRÉDITO ASOCIADA ]
				credits_domain = domain + [('invoice_type_code', '=', '07'), ('reversed_entry_id', '=', record.invoice_id.id)]
				related_invoices = self.env['account.move'].search(credits_domain)
				invoices = invoices + related_invoices
				# [ BUSCAR: NOTAS DE DÉBITO ASOCIADA ]
				debits_domain = domain + [('invoice_type_code', '=', '08'),('debit_origin_id', '=', record.invoice_id.id)]
				related_invoices = self.env['account.move'].search(debits_domain)
				invoices = invoices + related_invoices
				record.invoice_ids = [(6,0,invoices.ids)]
	
	def post(self):
		self.ensure_one()
		day_maximum = self.env['account.parameters'].search([('company_id', '=', self.company_id.id), ('code', '=', 'low_communication')])
		if not day_maximum.id:
			raise ValidationError("No existe un parámetro configurado para el envío de comunicación de baja. Por favor, revise su configuración.")
		if len(self.invoice_ids) == 0:
			raise UserError("Al menos debe existir 1 comprobante para anular.")
		errors = []
		errors += self.validate_invoice_ids(day_maximum)
		if errors:
			raise UserError("Se detectaron los siguientes errores:\n" + "\n".join(errors))
		cancel_invoices = self.invoice_ids
		# [ Cancelar comprobantes ]
		for invoice in cancel_invoices:
			invoice.write({'state': 'cancel'})
		# [ Cancelar pagos ]
		for invoice in cancel_invoices:			
			invoice_lines = invoice.line_ids.filtered(lambda l: l.account_type == 'asset_receivable') #Comprobante
			# Buscar conciliaciones
			partial_reconciles = self.env['account.partial.reconcile'].search([
				'|',
				('debit_move_id', 'in', invoice_lines.ids),
				('credit_move_id', 'in', invoice_lines.ids),
			])
			for reconcile in partial_reconciles:
				payment = reconcile.credit_move_id.payment_id
				# Si hay un pago, verificar si solo tiene un comprobante conciliado
				if payment:
					related_invoices = payment.reconciled_invoice_ids
					if len(related_invoices) == 1 and related_invoices.id == invoice.id:
						# Si solo tenía este comprobante, cancelarlo
						if payment.state != "cancel":
							payment.action_cancel()
				# Romper conciliación
				reconcile.unlink()
			# [ Cancelar toda la operación cuando es de Pvo ]
			if hasattr(invoice, 'pos_order_ids'):
				invoice.pos_order_ids._cancel_sales_order()  
		self.action_send_voided()
	
	def action_send_voided(self):
		# [ PENDIENTE IMPLEMENTACIÓN ]
		pass

	def action_generate_and_signed_xml(self):
		# [ PENDIENTE IMPLEMENTACIÓN ]
		pass

	def action_request_status_ticket(self):
		if not self.voided_ticket:
			raise UserError("El campo de ticket esta vacío")
		response = self.current_log_status_id.action_request_status_ticket_voided()
		if response.get("status") == "A":
			self.invoice_ids.write({'estado_comprobante_electronico':'2_ANULADO'})

	def cron_enviar_comunicacion_baja(self):
		voided_ids = self.env["account.comunicacion_baja"].search([("state", "in", ["P","N",False])])
		for voided in voided_ids:
			if all(voided.invoice_ids.mapped(lambda inv: inv.estado_comprobante_electronico == "1_ACEPTADO")):
				try:
					voided.action_send_voided()
				except Exception as E:
					pass

	def unlink(self):
		for voided in self:
			if voided.state:
				raise UserError("La anulación no puede ser eliminada.")
		return super(AccountComunicacionBaja, self).unlink()