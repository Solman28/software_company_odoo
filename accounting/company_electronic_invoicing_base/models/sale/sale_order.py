from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import re
from pytz import timezone
from odoo.tools import float_compare

patron_dni = re.compile(r"\d{8}$")
patron_ruc = re.compile(r"[12]\d{10}$")

valid_codes_boleta = ["-", "1", "4", "7"]

class SaleOrder(models.Model):
	_inherit = "sale.order"

	suitable_journal_ids = fields.Many2many('account.journal', string="Series permitidas", compute="_compute_suitable_journal_ids")
	journal_id = fields.Many2one(
		'account.journal', 
		string="Diario de facturación",
		compute="_compute_journal_id",
		required=True,
		store=True, 
		readonly=False, 
		precompute=True,
		domain="[('id', 'in', suitable_journal_ids)]", 
		check_company=True,
		tracking=True,
		help="Si se establece, los pedidos de venta se facturarán en este diario. De lo "
			"contrario, se utilizará el diario de ventas con la secuencia más baja.")
	warehouse_id = fields.Many2one(
		'stock.warehouse', string='Sede/Planta', required=True,
		compute='_compute_warehouse_id', store=True, readonly=False, precompute=True,
		check_company=True, tracking=True)
	tipo_documento = fields.Selection(
		string="Tipo de Documento",
		selection=[('01', 'Factura'), ('03', 'Boleta')],
		compute='_compute_tipo_documento',
		store=True
	)
	# Plazos de pago
	paymentterm_line = fields.One2many("sale.paymentterm.line", "order_id")
	residual_credit_paymentterm = fields.Monetary(string="Saldo restante de plazos de pago a crédito", compute="_compute_residual_credit_paymentterm")
	payment_term_type = fields.Char(compute="_compute_payment_term_type", string="Término de pago", store=True)
	payment_date_due_estimated = fields.Date(
		string="Fecha de vencimiento estimada",
		help="Fecha estimada de vencimiento del pago de la venta",
		compute="_compute_payment_due_estimated",
		store=True
	)

	# [ Métodos computados sobreescritos ]
	@api.depends('suitable_journal_ids')
	def _compute_journal_id(self):
		super()._compute_journal_id()
		for order in self:
			if order.suitable_journal_ids:
				order.journal_id = order.suitable_journal_ids[0]
	
	# [ Métodos computados ]
	@api.depends('warehouse_id', 'company_id', 'tipo_documento')
	def _compute_suitable_journal_ids(self):
		for order in self:
			if not order.tipo_documento:
				order.suitable_journal_ids = False
				continue
			domain = [
				('company_id', '=', order.company_id.id),
				('invoice_type_code', '=', order.tipo_documento),
				('type', '=', 'sale'),
			]
			journal_ids = self.env['account.journal'].search(domain)
			# El almacén solo restringe la lista si tiene "Series permitidas"
			# configuradas explícitamente; si no, se listan todas las series
			# electrónicas de la compañía para ese tipo de comprobante.
			if order.warehouse_id and order.warehouse_id.journal_ids:
				journal_ids = journal_ids.filtered(lambda j: j in order.warehouse_id.journal_ids)
			order.suitable_journal_ids = journal_ids
	
	@api.depends('partner_id', 'partner_invoice_id.l10n_latam_identification_type_id.l10n_pe_vat_code')
	def _compute_tipo_documento(self):
		for order in self:
			doc_code = order.partner_invoice_id.l10n_latam_identification_type_id.l10n_pe_vat_code
			if doc_code == '6':
				order.tipo_documento = '01'
			elif doc_code in valid_codes_boleta:
				order.tipo_documento = '03'
			else:
				order.tipo_documento = False
	
	@api.depends(
		"paymentterm_line",
		"paymentterm_line.amount",
		"amount_total"
	)
	def _compute_residual_credit_paymentterm(self):
		for order in self:
			order.residual_credit_paymentterm = round(order.amount_total - sum(order.paymentterm_line.mapped("amount")), 2)

	@api.depends("payment_term_id", "date_order")
	def _compute_payment_term_type(self):
		for record in self:
			record.payment_term_type = "Contado"
			if record.payment_term_id:
				record.payment_term_type = record.payment_term_id.type
				continue
	
	@api.depends("payment_term_id", "date_order", "amount_total")
	def _compute_payment_due_estimated(self):
		for order in self:

			if not order.date_order:
				order.payment_date_due_estimated = False
				continue

			date_ref = fields.Datetime.context_timestamp(order, order.date_order).date()
			#date_ref = order.date_order.astimezone(timezone('America/Lima')).date()
			due_date = date_ref

			if order.payment_term_id:
				result = order.payment_term_id._compute_terms(
					date_ref=date_ref,
					currency=order.currency_id,
					company=order.company_id,
					tax_amount=0.0,
					tax_amount_currency=0.0,
					untaxed_amount=order.amount_total,
					untaxed_amount_currency=order.amount_total,
					sign=1,
				)

				if result and result.get("line_ids"):
					due_date = result["line_ids"][-1]["date"]

			order.payment_date_due_estimated = due_date
	
	@api.constrains('payment_date_due_estimated', 'paymentterm_line', 'paymentterm_line.date_due')
	def check_date_cuotas_vs_date_due(self):
		for record in self:
			if not record.payment_date_due_estimated or not record.paymentterm_line:
				continue
			dates = [d for d in record.paymentterm_line.mapped('date_due') if d]
			if not dates:
				continue
			date_due_max = max(dates)
			if date_due_max > record.payment_date_due_estimated:
				raise ValidationError("La Fecha de las cuotas no puede ser mayor a la fecha de vencimiento estimada de la orden.")
	
	def validate_paymenttermn_lines(self):
		for record in self:
			if record.payment_term_type == "Credito":
				if record.amount_total > 0 and not record.paymentterm_line:
					raise UserError(
						"* No tiene registrado ningún plazo de pago. El monto total de los plazos de pago debe ser igual al total de la venta.")
				lines = record.paymentterm_line
				# validar fechas vacías
				dates = lines.mapped("date_due")
				if any(not d for d in dates):
					raise UserError(
						"* Debe ingresar una fecha de vencimiento de pago en la pestaña Plazos de pago")
				# validar montos
				amount_total_lines = sum(lines.mapped("amount"))
				if float_compare(amount_total_lines, record.amount_total, precision_digits=2) != 0:
					raise UserError(
						"* El monto total de los plazos de pago debe ser igual al total de la venta.")
				# validar fecha mínima
				min_date_due = min(dates)
				base_date = (
					record.date_order.astimezone(timezone('America/Lima')).date()
					if record.date_order
					else fields.Date.context_today(record)
				)
				if min_date_due < base_date:
					raise UserError(
						"* La fecha de vencimiento de la cuota debe ser mayor o igual a la fecha de la venta."
					)

	# [ Funciones sobreescritas ]
	def action_confirm(self):
		self.validate_paymenttermn_lines()
		return super().action_confirm()
	
	def _prepare_invoice(self):
		res = super()._prepare_invoice()
		res['journal_type'] = 'sale'
		res['invoice_type_code'] = self.tipo_documento
		res['sale_order_reference'] = self.name

		# [ Plazos de pago ]
		if self.payment_term_type == "Credito" and self.paymentterm_line:
			payment_lines = [
				(0, 0, {
					'amount': line.amount,
					'date_due': line.date_due,
				})
				for line in self.paymentterm_line
			]
			res['paymentterm_line'] = payment_lines
			res['invoice_date_due'] = self.payment_date_due_estimated

		warehouse = self.warehouse_id
		if warehouse:
			res["warehouse_id"] = warehouse.id

		# [ Retenciones ]
		partner = self.partner_id
		is_retention_agent = bool(partner and partner.is_retention_agent)
		res['apply_retention'] = is_retention_agent
		res['retention_percentage'] = partner.retention_percentage if is_retention_agent else '0'
		return res
	
class SalePaymenttermLine(models.Model):
	_name = "sale.paymentterm.line"
	_order = "date_due ASC"
	_description = "Líneas de término de pago de ventas"

	currency_id = fields.Many2one("res.currency", related="order_id.currency_id", string="Moneda", store=True)
	order_id = fields.Many2one("sale.order", string="Orden de venta")
	date_due = fields.Date("Fecha de vencimiento")
	amount = fields.Float("Monto")