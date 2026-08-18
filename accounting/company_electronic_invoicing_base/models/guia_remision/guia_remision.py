from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re

patron_dni = re.compile(r"^\d{8}$")
patron_ruc = re.compile(r"^[12]\d{10}$")

codigo_unidades_de_medida = [
	"DAY", #DIAS
	"CY",  #CILINDRO
	"HUR",
	"LTR", #LITRO
	"NIU", #UNIDAD
	"CMT", #CENTIMETRO
	"GLL", #GALON
	"GRM", #GRAMO
	"KGM", #KILOGRAMO
	"LBR", #LIBRA
	"MTR", #METRO
	"ONZ", #ONZA COMERCIAL
	"FOT",
	"INH",
	"DPC",
	"TNE",
	"KTM",
	"M52",
	"OZ",  #ONZA METALES PRECIOSOS
	"QTI"
]

codigo_dam = [
	"126",
	"12U",
	"2U",
	"2U6",
	"AM",
	"BAL",
	"BID",
	"BLS",
	"BOB",
	"BOT",
	"BRR",
	"CAJ",
	"CIL",
	"CM",
	"CM2",
	"CM3",
	"CON",
	"CRT",
	"FDO",
	"FRC",
	"GAL",
	"GLE",
	"GR",
	"GRU",
	"HL",
	"HOJ",
	"JGS",
	"KG",
	"KG3",
	"KG6",
	"KGA",
	"KI",
	"KI6",
	"KIT",
	"KL6",
	"KL9",
	"KM",
	"KW3",
	"KW6",
	"KWH",
	"L",
	"L 6",
	"LAT",
	"LB",
	"M",
	"M 6",
	"M2",
	"M26",
	"M3",
	"M36",
	"MGA",
	"MGR",
	"ML",
	"MLL",
	"MM",
	"MM2",
	"MM3",
	"MU",
	"MWH",
	"OZ",
	"PAI",
	"PAL",
	"PAQ",
	"PL",
	"PLC",
	"PLG",
	"PS",
	"PS2",
	"PS3",
	"PST",
	"PUL",
	"PZA",
	"QQ",
	"QUT",
	"RAM",
	"RES",
	"ROL",
	"SAC",
	"SET",
	"TAM",
	"TC",
	"TCS",
	"TIR",
	"TL",
	"TLS",
	"TM",
	"TM3",
	"TMS",
	"TUB",
	"U",
	"U 3",
	"U 6",
	"U2",
	"U3",
	"U6",
	"YD",
	"YD2",
]

estado_comprobante_electronico = [
	("0_NO_EXISTE", "NO EXISTE"),
	("1_ACEPTADO", "ACEPTADO"),
	("2_ANULADO", "ANULADO"),
	("3_AUTORIZADO", "AUTORIZADO"),
	("4_NO_AUTORIZADO", "NO AUTORIZADO"),
	("-", "-")
]

ISSUING_ENTITY = [
	'01',
	'02',
	'03',
	'04',
	'05',
	'06',
	'07',
	'08',
	'09',
	'10',
	'11',
	'12',
]

catalogo_61 = [
	"01",
	"03",
	"04",
	"09",
	"12",
	"31",
	"48",
	"49",
	"50",
	"52",
	"65",
	"66",
	"67",
	"68",
	"69",
	"71",
	"72",
	"73",
	"74",
	"75",
	"76",
	"77",
	"78",
	"80",
	"81",
	"82",
	"91"
]

guide_name_draft = [
	'GUÍA DE REMISIÓN ELECTRÓNICA REMITENTE',
	'GUÍA DE REMISIÓN ELECTRÓNICA TRANSPORTISTA',
	'GUÍA DE REMISIÓN ELECTRÓNICA'
]

class TransportType(models.Model):
	_name = "transport.type"
	_description = "Modalidad de Transporte"

	code = fields.Char("Código")
	name = fields.Char("Descripción")

class TransferReason(models.Model):
	_name = "transfer.reason"
	_description = "Motivo de traslado"

	code = fields.Char("Código")
	name = fields.Char("Descripción")
	active = fields.Boolean("Activo", default=True)

class RelatedDocument(models.Model):
	_name = "related.document"
	_description = "Documento relacionado"

	code = fields.Char("Código")
	name = fields.Char("Descripción")
	active = fields.Boolean("Activo", default=True)

class GuiaRemision(models.Model):
	_name = "guia.remision"
	_rec_name = "name"
	_description = "Guía de Remisión Electrónica"
	_inherit = ['mail.thread', 'mail.activity.mixin']


	def _list_transfer_reason(self):
		list_transfer_reasons = self.env["transfer.reason"].search([('active', '=', True)])
		return [(tr.code, tr.name) for tr in list_transfer_reasons]
	
	def _domain_related_document(self):
		domain = []
		gre_type = self._context.get('default_gre_type') or self.gre_type
		if gre_type == 'remitente':
			domain = [('code', 'not in', ['31', '65', '66', '67', '68', '69', '82'])]
		elif gre_type == 'transportista':
			domain = [('code', 'not in', ['49', '71', '72', '73', '74', '75', '76', '77', '78', '81', '91'])]
		return domain
	
	def _list_transport_type(self):
		list_transport_types = self.env["transport.type"].search([])
		return [(mt.code, mt.name) for mt in list_transport_types]
	

	name = fields.Char(string="Nombre", readonly=True, copy=False, default="GUÍA DE REMISIÓN ELECTRÓNICA", tracking=True)
	# [ Información general ]
	warehouse_id = fields.Many2one('stock.warehouse', 'Almacén', help='Local asignado para facturación', tracking=True)
	journal_id = fields.Many2one("account.journal", string="Serie", domain="[('id', 'in', suitable_journal_ids)]", compute="_compute_journal_id", store=True, tracking=True)
	suitable_journal_ids = fields.Many2many("account.journal", string="Series permitidas", compute="_compute_suitable_journal_ids")
	motivo_traslado = fields.Selection(selection=_list_transfer_reason, string="Motivo de Traslado", tracking=True)
	state = fields.Selection(selection=[('draft', 'Borrador'), ('validated', 'Registrado'), ('cancel', 'Cancelado')], string="Estado", default="draft", tracking=True)
	company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company.id)
	company_partner_id = fields.Many2one("res.partner", related="company_id.partner_id")
	note = fields.Text('Observaciones', tracking=True)
	# [ Destinatario ]
	destinatario_partner_id = fields.Many2one("res.partner", string="Destinatario", tracking=True)
	destinatario_tipo_documento_identidad = fields.Char(string="Tipo de Documento", tracking=True)
	destinatario_numero_documento_identidad = fields.Char(string="Número de Documento", tracking=True)
	destinatario_direccion = fields.Char(string="Dirección", tracking=True)
	destinatario_ubigeo = fields.Char(string="Ubigeo", tracking=True)
	# [ Proveedor ]
	proveedor_partner_id = fields.Many2one("res.partner", string="Proveedor", tracking=True)
	proveedor_tipo_documento_identidad = fields.Char(string="Tipo de Documento", tracking=True)
	proveedor_numero_documento_identidad = fields.Char(string="Número de Documento", tracking=True)
	proveedor_direccion = fields.Char(string="Dirección", tracking=True)
	proveedor_ubigeo = fields.Char(string="Ubigeo", tracking=True)
	# [ Documento relacionado ]
	related_document = fields.Many2one(
		'related.document',
		string="Documento relacionado",
		domain=lambda self: self._domain_related_document()
	)
	related_document_code = fields.Char(string="Código de doc relacionado", related="related_document.code", store=True)
	related_document_name = fields.Char(string="Número del documento relacionado", tracking=True)
	related_document_ruc = fields.Char(string="RUC del emisor del documento relacionado", tracking=True)
	documento_asociado = fields.Selection([
		("movimiento_stock", "Movimiento de stock"),
		('comprobante_pago', 'Factura/Boleta'),
		("other", "Otro")		
	], string="Documento interno", tracking=True)
	used_related_document = fields.Char(string="Usado como documento relacionado", help="Indica si la guia fue usado como documento relacionado.")
	# [ Relaciones ]
	guia_remitente_id = fields.Many2one('guia.remision', string="Guia Remitente", copy=False, tracking=True)
	comprobante_pago_ids = fields.Many2many("account.move", string="Comprobante de Pagos")
	picking_ids = fields.Many2many("stock.picking", string="Movimiento")
	sale_order_ids = fields.Many2many("sale.order", string="Ventas")
	# [ Detalle de lineas]
	guia_remision_line_ids = fields.One2many("guia.remision.line", "guia_remision_id", string="Detalle de líneas")
	# [ Envío ]
	fecha_emision = fields.Date(string="Fecha de Emisión", help="Fecha y hora de emisión del comprobante", copy=False, default=fields.Date.context_today, tracking=True)
	fecha_inicio_traslado = fields.Date(string="Fecha inicio de traslado", copy=False, default=fields.Date.context_today, tracking=True)
	peso_bruto_uom = fields.Selection(
		string='Udm del Peso Bruto',
		selection=[
			('KGM', 'Kilogramos'),
			('TNE', 'Toneladas'),
		],
		default="KGM",
		copy=False,
		required=True,
		tracking=True
	)
	#peso_bruto_total = fields.Float(string="Peso Bruto Total", compute="_compute_peso_bruto_total", store=True, tracking=True, recursive=True)
	peso_bruto_total = fields.Float(string="Peso Bruto Total", tracking=True)
	numero_bultos = fields.Integer(string="Número de bultos", tracking=True)
	transport_type = fields.Selection(
		string='Modalidad de transporte',
		selection=_list_transport_type,
		copy=False,
		help="Seleccione si el transporte es interno (privado: empresa propia) o externo (público: empresa de transporte).",
		tracking=True
	)
	# [ Ruta ]
	partner_direccion_partida_id = fields.Many2one("res.partner", tracking=True)
	direccion_partida_id = fields.Many2one("res.partner", tracking=True)
	lugar_partida_direccion = fields.Char(string="Lugar de Partida - Dirección", tracking=True)
	lugar_partida_distrito = fields.Many2one('l10n_pe.res.city.district', string="Partida", tracking=True)
	lugar_partida_ubigeo = fields.Char(string="Ubigeo Partida", tracking=True)
	# Obligatorio si el motivo de traslado es 'Traslado entre establecimientos de la misma empresa'.
	codigo_sunat_partida = fields.Char(string="Código de establecimiento de partida", help="Código de establecimiento de punto de partida", default="0000", size=4)
	partner_direccion_llegada_id = fields.Many2one("res.partner", tracking=True)
	direccion_llegada_id = fields.Many2one("res.partner", tracking=True)
	lugar_llegada_direccion = fields.Char(string="Lugar de llegada - Dirección", tracking=True)
	lugar_llegada_distrito = fields.Many2one('l10n_pe.res.city.district', string="Llegada", tracking=True)
	lugar_llegada_ubigeo = fields.Char(string="Ubigeo Llegada", tracking=True)
	# Obligatorio si el motivo de traslado es 'Traslado entre establecimientos de la misma empresa'.
	codigo_sunat_llegada = fields.Char(string="Código de establecimiento de llegada", help="Código de establecimiento de punto de llegada", default="0000", size=4)
	# [ Transporte ]
	# [ Privado ]
	conductor_privado_id = fields.Many2one("res.partner", string="Conductor", tracking=True)
	conductor_privado_secundario_id = fields.Many2one("res.partner", string="Conductor secundario", tracking=True)
	vehiculo_privado_id = fields.Many2one("l10n_pe_edi.vehicle", string="Vehículo", check_company=True, tracking=True)
	# tuce_chv_vehiculo_privado = fields.Char(string="TUCE o CHV(vehículo privado)", help="Tarjeta Única de Circulación Electrónica (TUCE) o Certificado de Habilitación Vehicular (CHV)")
	vehiculo_privado_mtc_id = fields.Many2one('res.partner.mtc', string="Numero de autorizacion especial", domain="[('id', 'in', suitable_vehiculo_privado_mtc_ids)]")
	vehiculo_privado_secundario_id = fields.Many2one("l10n_pe_edi.vehicle", string="Vehículo secundario", tracking=True)
	# tuce_chv_vehiculo_privado_secundario = fields.Char(string="TUCE o CHV(vehículo privado secundario)", help="Tarjeta Única de Circulación Electrónica (TUCE) o Certificado de Habilitación Vehicular (CHV)")
	vehiculo_privado_secundario_mtc_id = fields.Many2one('res.partner.mtc', string="Numero de autorizacion especial", domain="[('id', 'in', suitable_vehiculo_secundario_mtc_ids)]")
	suitable_vehiculo_privado_mtc_ids = fields.Many2many('res.partner.mtc', compute="_compute_suitable_vehiculo_privado_mtc_ids")
	suitable_vehiculo_secundario_mtc_ids = fields.Many2many('res.partner.mtc', compute="_compute_suitable_vehiculo_secundario_mtc_ids")
	# [ Público ]
	transporte_partner_id = fields.Many2one("res.partner", string="Empresa Transportista", tracking=True)
	transporte_partner_mtc_id = fields.Many2one('res.partner.mtc', string="Número de registro MTC", domain="[('id', 'in', suitable_transporte_partner_mtc_ids)]")
	autorization_number_transporte_partner_id = fields.Many2one('res.partner.mtc', string="Número de autorización", domain="[('id', 'in', suitable_transporte_partner_mtc_ids)]")
	suitable_transporte_partner_mtc_ids = fields.Many2many('res.partner.mtc', compute="_compute_suitable_transporte_partner_mtc_ids")
	conductor_publico_id = fields.Many2one("res.partner", string="Conductor", tracking=True)
	conductor_publico_secundario_id = fields.Many2one("res.partner", string="Conductor secundario", tracking=True)
	vehiculo_publico_id = fields.Many2one("l10n_pe_edi.vehicle", string="Vehículo", domain="[('transporte_partner_id', '=', transporte_partner_id)]", tracking=True)
	tuce_chv_vehiculo_publico = fields.Char(string="TUCE o CHV(vehículo público)", help="Tarjeta Única de Circulación Electrónica (TUCE) o Certificado de Habilitación Vehicular (CHV)")
	vehiculo_publico_mtc_id = fields.Many2one('res.partner.mtc', string="Numero de autorizacion especial", domain="[('id', 'in', suitable_vehiculo_publico_mtc_ids)]")
	suitable_vehiculo_publico_mtc_ids = fields.Many2many('res.partner.mtc', compute="_compute_suitable_vehiculo_publico_mtc_ids")
	vehiculo_publico_secundario_id = fields.Many2one("l10n_pe_edi.vehicle", string="Vehículo secundario", domain="[('transporte_partner_id', '=', transporte_partner_id)]", tracking=True)
	tuce_chv_vehiculo_publico_secundario = fields.Char(string="TUCE o CHV(vehículo público secundario)", help="Tarjeta Única de Circulación Electrónica (TUCE) o Certificado de Habilitación Vehicular (CHV)")
	vehiculo_publico_secundario_mtc_id = fields.Many2one('res.partner.mtc', string="Numero de autorizacion especial", domain="[('id', 'in', suitable_vehiculo_publico_secundario_mtc_ids)]")
	suitable_vehiculo_publico_secundario_mtc_ids = fields.Many2many('res.partner.mtc', compute="_compute_suitable_vehiculo_publico_secundario_mtc_ids")
	# suitable_vehiculo_publico_ids = fields.Many2many("res.partner", string="Vehiculos publicos permitidos", compute="_compute_suitable_vehiculo_publico_ids")
	# [ Tipo de GRE ]
	gre_type = fields.Selection(selection=[("remitente", "Remitente"), ("transportista", "Transportista")], string="Tipo de GRE")
	# [ Facturación electrónica ]
	account_log_status_ids = fields.One2many("account.log.status", "guia_remision_id", string="Registro de Envíos", copy=False)
	current_log_status_id = fields.Many2one("account.log.status", copy=False)
	request_json = fields.Text(string="Petición JSON")
	response_json = fields.Text(string="Respuesta JSON")
	estado_gre_sunat = fields.Selection(
		related="current_log_status_id.status",
		string="Estado Emisión a SUNAT",
		store=True
	)
	#estado_sunat = fields.Selection(selection=estado_comprobante_electronico, default="-", copy=False, tracking=True)
	consulta_validez_observaciones = fields.Text(related="current_log_status_id.sunat_observaciones", string="Observaciones SUNAT")
	# [ Campos auxiliares ]
	short_name = fields.Char(
		string="Número corto",
		compute="_compute_short_name",
	)

	@api.constrains('peso_bruto_total')
	def _check_peso_bruto_total(self):
		for record in self:
			if record.peso_bruto_total < 0:
				raise UserError("El peso bruto total del envío debe ser mayor a 0.")
	
	# [ Métodos computados ]
	@api.depends('name')
	def _compute_short_name(self):
		for record in self:
			if record.name and '-' in record.name:
				serie, numero = record.name.split('-')
				record.short_name = f"{serie}-{numero.lstrip('0')}"
			else:
				record.short_name = record.name

	@api.depends('gre_type', 'company_id', 'warehouse_id')
	def _compute_suitable_journal_ids(self):
		for record in self:
			domain = [
				('company_id', '=', record.company_id.id), 
				('electronic_invoice', '=', True)
			]
			if record.gre_type == 'remitente':
				domain.append(('invoice_type_code', '=', '09'))
			elif record.gre_type == 'transportista':
				domain.append(('invoice_type_code', '=', '31'))

			all_journal_ids = self.env['account.journal'].search(domain)
			if record.warehouse_id:
				wh_journal_ids = record.warehouse_id.journal_ids.filtered(lambda j:j.id in all_journal_ids.ids)
				record.suitable_journal_ids = wh_journal_ids
			else:
				record.suitable_journal_ids = all_journal_ids
	
	@api.depends('suitable_journal_ids')
	def _compute_journal_id(self):
		for record in self:
			record.journal_id = record.suitable_journal_ids[:1]
	
	@api.depends('guia_remision_line_ids.qty', 'guia_remision_line_ids.product_id.weight', 'peso_bruto_uom', 'guia_remitente_id.peso_bruto_total')
	def _compute_peso_bruto_total(self):
		for record in self:
			if record.guia_remitente_id:
				record.peso_bruto_total = record.guia_remitente_id.peso_bruto_total
				continue
			if record.state != 'draft':
				# No recalcular si no está en borrador
				continue
			if record.peso_bruto_uom == 'KGM':
				total = sum(
					(line.qty or 0.0) * (line.product_id.weight or 0.0)
					for line in record.guia_remision_line_ids
				)
			else:
				total = 0.0
			record.peso_bruto_total = total

	@api.depends('transporte_partner_id')
	def _compute_suitable_vehiculo_publico_ids(self):
		for record in self:
			if record.transporte_partner_id:
				domain = [
					('is_public_vehicle', '=', True),
					('transporte_partner_id', '=', record.transporte_partner_id.id)
				]
				vehicles = self.env['l10n_pe_edi.vehicle'].search(domain)
				record.suitable_vehiculo_publico_ids = [(6, 0, vehicles.ids)]
				
			else:
				record.suitable_vehiculo_publico_ids = False
		
	# [ Secuencia de GRE ]
	@api.model
	def default_get(self, fields_list):
		res = super().default_get(fields_list)
		gre_type = self.env.context.get('default_gre_type')
		if gre_type == 'remitente':
			res.update({"name": "GUÍA DE REMISIÓN ELECTRÓNICA REMITENTE"})
		elif gre_type == "transportista":
			res.update({"name": "GUÍA DE REMISIÓN ELECTRÓNICA TRANSPORTISTA"})
		else:
			res.update({"name": "GUÍA DE REMISIÓN ELECTRÓNICA"})
		return res
	
	@api.onchange("transport_type")
	def _onchange_transport_type(self):
		for record in self:
			if record.transport_type == "02":
				record.transporte_partner_id = False
	
	@api.onchange('vehiculo_publico_id')
	def _onchange_vehiculo_publico(self):
		if self.vehiculo_publico_id:
			self.tuce_chv_vehiculo_publico = self.vehiculo_publico_id.tuce_chv
			if self.vehiculo_publico_mtc_id and self.vehiculo_publico_mtc_id not in self.vehiculo_publico_id.mtc_ids:
				self.vehiculo_publico_mtc_id = False
		else:
			self.tuce_chv_vehiculo_publico = False
	
	@api.onchange('vehiculo_publico_secundario_id')
	def _onchange_vehiculo_publico_secundario(self):
		if self.vehiculo_publico_secundario_id:
			self.tuce_chv_vehiculo_publico_secundario = self.vehiculo_publico_secundario_id.tuce_chv
			if self.vehiculo_publico_secundario_mtc_id and self.vehiculo_publico_secundario_mtc_id not in self.vehiculo_publico_secundario_id.mtc_ids:
				self.vehiculo_publico_secundario_mtc_id = False
		else:
			self.tuce_chv_vehiculo_publico_secundario = False
	
	# @api.onchange('vehiculo_privado_id')
	# def _onchange_vehiculo_privado(self):
	# 	if self.vehiculo_privado_id:
	# 		self.tuce_chv_vehiculo_privado = self.vehiculo_privado_id.tuce_chv
	# 		if self.vehiculo_privado_mtc_id and self.vehiculo_privado_mtc_id not in self.vehiculo_privado_id.mtc_ids:
	# 			self.vehiculo_privado_mtc_id = False
	# 	else:
	# 		self.tuce_chv_vehiculo_publico = False
	
	# @api.onchange('vehiculo_privado_secundario_id')
	# def _onchange_vehiculo_privado_secundario(self):
	# 	if self.vehiculo_privado_secundario_id:
	# 		self.tuce_chv_vehiculo_privado_secundario = self.vehiculo_privado_secundario_id.tuce_chv
	# 		if self.vehiculo_privado_secundario_mtc_id and self.vehiculo_privado_secundario_mtc_id not in self.vehiculo_privado_secundario_id.mtc_ids:
	# 			self.vehiculo_privado_secundario_mtc_id = False
	# 	else:
	# 		self.tuce_chv_vehiculo_privado_secundario = False

	def default_direccion_llegada_id(self):
		if "direccion_entrega" in self._context and self._context["direccion_entrega"] != False:
			return self._context["direccion_entrega"]
		elif len(self.destinatario_partner_id):
			return self.destinatario_partner_id
		else:
			return False

	def default_direccion_partida_id(self):
		if "direccion_partida" in self._context and self._context["direccion_partida"] != False:
			return self._context["direccion_partida"]
		elif len(self.company_partner_id.child_ids):
			direcciones = self.company_partner_id.child_ids.filtered(lambda x: x.type in ('contact','other','delivery') and x.es_conductor != True)
			if len(direcciones) != 0:
				return direcciones[0].id
			else:
				return False
		else:
			return False
	
	@api.onchange('lugar_partida_distrito')
	def _onchange_lugar_partida_distrito(self):
		if self.lugar_partida_distrito:
			self.lugar_partida_ubigeo = self.lugar_partida_distrito.code or ''
		else:
			self.lugar_partida_ubigeo = ''
	
	@api.onchange('lugar_llegada_distrito')
	def _onchange_lugar_llegada_distrito(self):
		if self.lugar_llegada_distrito:
			self.lugar_llegada_ubigeo = self.lugar_llegada_distrito.code or ''
		else:
			self.lugar_llegada_ubigeo = ''
	
	@api.onchange("motivo_traslado")
	def _onchange_transfer_reason(self):
		for record in self:
			if not record.partner_direccion_partida_id:
				record.partner_direccion_partida_id = False
			if not record.partner_direccion_llegada_id:
				record.partner_direccion_llegada_id = False
			if not record.proveedor_partner_id:
				record.proveedor_partner_id = False
			if not record.direccion_llegada_id:
				record.direccion_llegada_id = False
			if not record.direccion_partida_id:
				record.direccion_partida_id = False
		   
			if record.motivo_traslado in ['01', '09', '19']:
				record.partner_direccion_partida_id = record.company_partner_id
				record.partner_direccion_llegada_id = record.destinatario_partner_id
				record.direccion_partida_id = record.default_direccion_partida_id()
				record.direccion_llegada_id = record.default_direccion_llegada_id()
			if record.motivo_traslado in ['04', '18']:
				record.partner_direccion_llegada_id = record.company_partner_id
				record.partner_direccion_partida_id = record.company_partner_id
				record.direccion_partida_id = record.company_partner_id
				record.direccion_llegada_id = record.company_partner_id
				record.destinatario_partner_id = record.company_partner_id
			if record.motivo_traslado in ['02']:
				record.destinatario_partner_id = record.company_partner_id
				record.partner_direccion_llegada_id = record.company_partner_id
	
	@api.onchange("destinatario_partner_id")
	def _onchange_destinatario_partner(self):
		for record in self:
			record.destinatario_tipo_documento_identidad = record.destinatario_partner_id.l10n_latam_identification_type_id.name
			record.destinatario_numero_documento_identidad = record.destinatario_partner_id.vat
			record.destinatario_direccion = record.destinatario_partner_id.street
			record.destinatario_ubigeo = record.destinatario_partner_id.ubigeo
			if not record.proveedor_partner_id:
				record.proveedor_partner_id = False
			# 01 - VENTA
			# 09 - EXPORTACIÓN
			# 19 - TRASLADO A ZONA PRIMARIA
			# 13 - OTROS
			if record.motivo_traslado in ['01', '09', '19']:
				record.partner_direccion_llegada_id = record.destinatario_partner_id.id
				record.partner_direccion_partida_id = record.company_partner_id.id
				record.direccion_llegada_id = record.default_direccion_llegada_id()
			# 04 - TRASLADO ENTRE ESTABLECIMIENTOS DE LA MISMA EMPRESA
			# 18 - TRASLADO A EMISOR ITINERANTE CP
			if record.motivo_traslado in ['04', '18']:
				record.partner_direccion_llegada_id = record.company_partner_id.id
				record.partner_direccion_partida_id = record.company_partner_id.id
			# 08-EXPORTACIÓN
			if record.motivo_traslado in ['09']:
				record.partner_direccion_partida_id = record.company_partner_id.id
				record.direccion_llegada_id = False
				record.partner_direccion_llegada_id = record.destinatario_partner_id.id
			# 08-IMPORTACIÓN
			if record.motivo_traslado in ['08']:
				record.partner_direccion_partida_id = record.proveedor_partner_id.id
				record.direccion_llegada_id = False
				record.partner_direccion_llegada_id = record.destinatario_partner_id.id
	
	@api.onchange("proveedor_partner_id")
	def _onchange_proveedor_partner(self):
		for record in self:
			record.proveedor_tipo_documento_identidad = record.proveedor_partner_id.l10n_latam_identification_type_id.name
			record.proveedor_numero_documento_identidad = record.proveedor_partner_id.vat
			record.proveedor_direccion = record.proveedor_partner_id.street
			record.proveedor_ubigeo = record.proveedor_partner_id.ubigeo

			# 02-COMPRA
			if record.motivo_traslado in ['02']:
				record.direccion_partida_id = False
				if not record.partner_direccion_llegada_id:
					record.partner_direccion_llegada_id = record.company_partner_id.id
				if not record.partner_direccion_partida_id:
					record.partner_direccion_partida_id = record.proveedor_partner_id.id
			# 08-IMPORTACIÓN
			if record.motivo_traslado in ['08']:
				record.direccion_partida_id = False
				record.partner_direccion_partida_id = record.proveedor_partner_id.id
				record.partner_direccion_llegada_id = record.destinatario_partner_id.id
	
	@api.onchange("picking_ids")
	def _onchange_movimiento_stock(self):
		for record in self:
			if record.documento_asociado != "movimiento_stock" or record.gre_type == 'transportista':
				continue

			record.guia_remision_line_ids = [(6, 0, [])]

			guia_remision_lines_temp = {}

			for picking in record.picking_ids:
				for move in picking.move_ids_without_package.filtered(lambda m: m.product_id.type in ('product', 'consu')):
					# Obtener identificadores (lotes)
					lot_names = [ml.lot_id.name for ml in move.move_line_ids if ml.lot_id]
					identificador = f" ({', '.join(lot_names)})" if lot_names else ""

					# Calcular peso
					factor = move.product_uom.factor_inv / move.product_id.uom_id.factor_inv
					line_weight = move.product_id.weight * move.quantity * factor

					key = (move.product_id.id, move.product_uom.id)
					if key not in guia_remision_lines_temp:
						guia_remision_lines_temp[key] = {
							"product_id": move.product_id.id,
							"description": move.product_id.name + identificador,
							"qty": move.quantity,
							"uom_id": move.product_uom.id,
							"stock_picking_id": picking.id,
							#"weight": line_weight,
						}
					else:
						guia_remision_lines_temp[key]["qty"] += move.quantity
						guia_remision_lines_temp[key]["weight"] += line_weight

			record.guia_remision_line_ids = [(0, 0, vals) for vals in guia_remision_lines_temp.values()]

	
	# @api.onchange("sale_order_ids")
	# def _onchange_sale_orders(self):
	# 	for record in self:
	# 		guia_remision_lines = []
	# 		guia_remision_lines_temp = {}
	# 		if record.documento_asociado == "sale":
	# 			record.guia_remision_line_ids = [(6, 0, [])]
	# 			#-------------------------------------------
	# 			# Solo productos de tipo almacenable (product)
	# 			#-------------------------------------------
	# 			for sale_order in record.sale_order_ids:
	# 				guia_remision_lines += [{
	# 					"product_id": line.product_id.id,
	# 					"description": line.name,
	# 					"qty": line.product_uom_qty,
	# 					"uom_id": line.product_uom.id,
	# 					"stock_picking_id": False
	# 				} for line in sale_order.order_line.filtered(lambda a:a.product_id.detailed_type == 'product')]
	# 			index = 0
	# 			for line in guia_remision_lines:
	# 				if (line["product_id"], line["uom_id"]) not in list(map(lambda x: (guia_remision_lines_temp[x]['product_id'], guia_remision_lines_temp[x]['uom_id']), guia_remision_lines_temp)):
	# 					guia_remision_lines_temp[index] = line
	# 				else:
	# 					product_index = list(filter(lambda x: (guia_remision_lines_temp[x]['product_id'], guia_remision_lines_temp[x]['uom_id']) == (
	# 						line["product_id"], line["uom_id"]), guia_remision_lines_temp))
	# 					guia_remision_lines_temp[product_index[0]]["qty"] += line["qty"]
	# 				index += 1

	# 			guia_remision_lines = list(guia_remision_lines_temp.values())
	# 			# [ OBTENIENDO LAS ORDENES DE COMPRA ASOCIADAS A FACTURAS/BOLETAS ]
	# 			pickings = record.sale_order_ids.picking_ids
	# 			for item in guia_remision_lines:
	# 				product = item['product_id']
	# 				old_description = item['description']
	# 				for move in pickings.move_ids_without_package:
	# 					if move.product_id.id == product:
	# 						identificador = ""
	# 						for line_id in move.move_line_ids:
	# 							if line_id.lot_id:
	# 								identificador = identificador + str(line_id.lot_id.name) + ","
	# 						if identificador[-1:] == ",":
	# 							identificador = " ("  + identificador[0:len(identificador)-1] +")"
	# 						item['description'] = old_description +  identificador
	# 			record.guia_remision_line_ids = [(0, 0, grl) for grl in guia_remision_lines]
	# 			record.guia_remision_line_ids._compute_weight()

	@api.onchange("guia_remitente_id")
	def _onchange_guia_remitente(self):
		for record in self:
			if record.related_document_code != "09" or not record.guia_remitente_id:
				continue

			record.guia_remision_line_ids = [(5, 0, 0)]
			grt_lines = []
			guia_remitente = record.guia_remitente_id

			for line in guia_remitente.guia_remision_line_ids:
				grt_lines.append((0, 0, {
					"product_id": line.product_id.id,
					"description": line.description,
					"qty": line.qty,
					"uom_id": line.uom_id.id,
					"stock_picking_id": False,
				}))
			
			record.guia_remision_line_ids = grt_lines
			record.destinatario_partner_id = guia_remitente.destinatario_partner_id
			record.peso_bruto_uom = guia_remitente.peso_bruto_uom
			record.peso_bruto_total = guia_remitente.peso_bruto_total
			record.partner_direccion_partida_id = guia_remitente.partner_direccion_partida_id
			record.direccion_partida_id = guia_remitente.direccion_partida_id
			record.partner_direccion_llegada_id = guia_remitente.partner_direccion_llegada_id
			record.direccion_llegada_id = guia_remitente.direccion_llegada_id
			record.transporte_partner_id = guia_remitente.transporte_partner_id
			record.transporte_partner_mtc_id = guia_remitente.transporte_partner_mtc_id
			# record.conductor_publico_id = guia_remitente.conductor_publico_id
			# record.vehiculo_publico_id = guia_remitente.vehiculo_publico_id

	
	@api.onchange("direccion_partida_id")
	def _onchange_direccion_partida(self):
		for record in self:
			record.lugar_partida_direccion = record.direccion_partida_id.street
			record.lugar_partida_distrito = record.direccion_partida_id.l10n_pe_district.id
	
	@api.onchange("direccion_llegada_id")
	def _onchange_direccion_llegada(self):
		for record in self:
			record.lugar_llegada_direccion = record.direccion_llegada_id.street
			record.lugar_llegada_distrito = record.direccion_llegada_id.l10n_pe_district.id
	
	@api.depends('vehiculo_privado_id')
	def _compute_suitable_vehiculo_privado_mtc_ids(self):
		for record in self:
			if record.vehiculo_privado_id and record.vehiculo_privado_id.mtc_ids:
				record.suitable_vehiculo_privado_mtc_ids = [(6, 0, record.vehiculo_privado_id.mtc_ids.ids)]
			else:
				record.suitable_vehiculo_privado_mtc_ids = False
	
	@api.depends('vehiculo_privado_secundario_id')
	def _compute_suitable_vehiculo_secundario_mtc_ids(self):
		for record in self:
			if record.vehiculo_privado_secundario_id and record.vehiculo_privado_secundario_id.mtc_ids:
				record.suitable_vehiculo_secundario_mtc_ids = [(6, 0, record.vehiculo_privado_secundario_id.mtc_ids.ids)]
			else:
				record.suitable_vehiculo_secundario_mtc_ids = False
	
	@api.depends('transporte_partner_id')
	def _compute_suitable_transporte_partner_mtc_ids(self):
		for record in self:
			if record.transporte_partner_id and record.transporte_partner_id.mtc_ids:
				record.suitable_transporte_partner_mtc_ids = [(6, 0, record.transporte_partner_id.mtc_ids.ids)]
			else:
				record.suitable_transporte_partner_mtc_ids = False
	
	@api.depends('vehiculo_publico_id')
	def _compute_suitable_vehiculo_publico_mtc_ids(self):
		for record in self:
			if record.vehiculo_publico_id and record.vehiculo_publico_id.mtc_ids:
				record.suitable_vehiculo_publico_mtc_ids = [(6, 0, record.vehiculo_publico_id.mtc_ids.ids)]
			else:
				record.suitable_vehiculo_publico_mtc_ids = False
	
	@api.depends('vehiculo_publico_secundario_id')
	def _compute_suitable_vehiculo_publico_secundario_mtc_ids(self):
		for record in self:
			if record.vehiculo_publico_secundario_id and record.vehiculo_publico_secundario_id.mtc_ids:
				record.suitable_vehiculo_publico_secundario_mtc_ids = [(6, 0, record.vehiculo_publico_secundario_id.mtc_ids.ids)]
			else:
				record.suitable_vehiculo_publico_secundario_mtc_ids = False

	def validar_datos_compania(self):
		errors = []
		company = self.company_id
		if not company.partner_id.vat:
			errors.append(
				"* No se tiene configurado el RUC de la empresa emisora.")
		elif not patron_ruc.match(company.partner_id.vat):
			errors.append(
				"* El RUC de la empresa emisora no tiene un formato válido.")

		if not company.partner_id.l10n_latam_identification_type_id or not company.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code:
			errors.append(
				"* No se encuentra configurado el tipo de documento de la empresa emisora.")
		elif company.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code != '6':
			errors.append(
				"* El tipo de documento de la empresa emisora debe ser RUC.")
		if not company.partner_id.ubigeo:
			errors.append(
				"* No se encuentra configurado el Ubigeo de la empresa emisora.")
		if not company.partner_id.street:
			errors.append(
				"* No se encuentra configurado la dirección de la empresa emisora.")
		if not company.partner_id.name:
			errors.append(
				"* No se encuentra configurado la Razón Social de la empresa emisora.")
		if not company.partner_id.email:
			errors.append(
				"* No se encuentra configurado el Correo de la empresa emisora.")
		return errors

	def validar_datos_destinatario(self):
		errors = []
		destinatario = self.destinatario_partner_id
		if not destinatario.l10n_latam_identification_type_id or not destinatario.l10n_latam_identification_type_id.l10n_pe_vat_code:
			errors.append(
				"* El tipo de Documento del destinatario es obligatorio")
		else:
			if destinatario.l10n_latam_identification_type_id.l10n_pe_vat_code == "6":
				if not destinatario.vat:
					errors.append(
						"* El Número de documento del destinatario esta vacío.")
				elif not patron_ruc.match(destinatario.vat):
					errors.append(
						"* El RUC del destinatario no tiene un formato válido.")
			elif destinatario.l10n_latam_identification_type_id.l10n_pe_vat_code == "1":
				if not destinatario.vat:
					errors.append(
						"* El Número de documento del destinatario esta vacío.")
				elif not patron_dni.match(destinatario.vat):
					errors.append(
						"* El DNI del destinatario no tiene un formato válido.")
			elif destinatario.l10n_latam_identification_type_id.l10n_pe_vat_code in ("0","4","7"):
				if not destinatario.vat:
					errors.append(
						"* El Número de documento del destinatario esta vacío.")
			else:
				errors.append(
					"* El tipo de Documento del Destinatario no es válido, seleccion un RUC, DNI")

		if not destinatario.name:
			errors.append(
				"* El nombre o razón social del destinatario esta vacío.")
		elif destinatario.name.strip() == "":
			errors.append(
				"* El nombre o razón social del destinatario no puede contener solo espacios en blanco.")
		elif len(destinatario.name) > 250:
			errors.append(
				"* El nombre o razón social del destinatario debe poseer hasta 250 caracteres.")
		return errors

	def validar_motivo_traslado(self):
		errors = []
		motivo_traslado = self.motivo_traslado

		if not motivo_traslado:
			errors.append("* El Motivo de Traslado es obligatorio.")
			return errors

		# 09 Exportación
		if motivo_traslado == "09":
			if self.numero_bultos is None or self.numero_bultos <= 0:
				errors.append(
					"* El número de bultos o pallets debe ser mayor a 0 para motivo de traslado 'Exportación'.")
			elif self.numero_bultos > 999999:
				errors.append(
					"* El número de bultos o pallets no puede superar los 6 dígitos (máximo 999999).")

		# 02 Compra
		# 07 Recojo de bienes transformados
		if motivo_traslado in ("02", "07") and not self.proveedor_partner_id:
			errors.append(
				"* Es obligatorio seleccionar el proveedor para los motivos de traslado 'Compra' y 'Recojo de bienes transformados'.")
		# Validar comprador Solo para los motivos de traslado 'Venta con entrega a terceros' y 'Otros'.
		# Validar 18 Traslado emisor itinerante CP
		# 04 Traslado entre establecimientos de la misma empresa
		if motivo_traslado == '04':
			if not self.codigo_sunat_partida:
				errors.append(
					"* El Código de establecimiento de punto de partida es obligatorio para el motivo de traslado 'Traslado entre establecimientos de la misma empresa'.")
			if not self.codigo_sunat_llegada:
				errors.append(
					"* El Código de establecimiento de punto de llegada es obligatorio para el motivo de traslado 'Traslado entre establecimientos de la misma empresa'.")

		return errors
	
	def validar_fechas(self):
		errors = []

		if not self.fecha_emision:
			errors.append("* La Fecha de Emisión es obligatoria.")
		if not self.fecha_inicio_traslado:
			errors.append("* La Fecha de Traslado es obligatoria.")

		# Validar que traslado >= emisión
		if self.fecha_emision and self.fecha_inicio_traslado:
			if self.fecha_inicio_traslado < self.fecha_emision:
				errors.append("* La Fecha de Traslado debe ser mayor o igual que la Fecha de Emisión.")

		return errors

	def validar_datos_envio(self):
		errors = []
		if self.peso_bruto_total == 0:
			errors.append("* El peso bruto total debe ser mayor a 0.")
		return errors

	def validar_guia_remision_lineas(self):
		errors = []
		if not self.guia_remision_line_ids:
			errors.append(
				"* La guía debe tener al menos un elemento en el detalle de envío.")
			return errors

		for line in self.guia_remision_line_ids:
			# Producto
			if not line.product_id:
				errors.append(
					"* El producto de una de las líneas del detalle está vacío.")
				continue
			
			# Descripción
			if not line.description:
				errors.append("* La descripción del producto [{}] está vacía.".format(line.product_id.name))
			elif len(line.description) < 3 or len(line.description) > 500:
				errors.append(
					"* La longitud de la descripción del producto [{}] debe poseer entre 3 a 500 caracteres.".format(line.product_id.name))
			
			# Unidad de medida
			uom = line.uom_id
			if not uom:
				errors.append(
					"* La unidad de medida del producto [{}] esta vacía".format(line.product_id.name))
			else:
				code = (uom.l10n_pe_edi_measure_unit_code or '').upper()
				if not code:
					errors.append(
						"* La unidad de medida del producto [{}] no tiene un código asociado. Comuníquese con su Administrador del Sistema.".format(line.product_id.name))
				elif not re.match(r'^[A-Z0-9]{1,3}$', code):
					errors.append("* El código de la unidad de medida del producto [{}] tiene un formato inválido.".format(line.product_id.name))
				elif code not in codigo_unidades_de_medida:
					errors.append("* El código de la unidad de medida del producto [{}] no pertenece al Catálogo 03 SUNAT. Comuníquese con su Administrador del Sistema.".format(line.product_id.name))
				
				if line.guia_remision_id.gre_type == 'remitente' and line.guia_remision_id.motivo_traslado in ('08', '09'):
					# Exportación / Importación
					if not uom.code_dam:
						errors.append(
							"* La unidad de medida del producto [{}] no tiene asignado el código DAM o DS. Comuníquese con su Administrador del Sistema.".format(line.product_id.name))
					elif uom.code_dam not in codigo_dam:
						errors.append("* El código DAM o DS de la unidad de medida del producto [{}] no pertenece al Catálogo 65 SUNAT. Comuníquese con su Administrador del Sistema.".format(line.product_id.name))
			
			if not line.product_id.default_code:
				errors.append("* El producto [{}] no tiene asignado su código de producto.".format(line.product_id.name))
			elif len(line.product_id.default_code) > 30:
				errors.append("* El codigo del producto [{}] debe poseer hasta 30 caracteres.".format(line.product_id.name))
			
			if line.qty == 0:
				errors.append("* La cantidad del producto [{}], debe ser mayor a 0".format(line.product_id.name))

		return errors
	
	def validar_lugar_partida(self):
		errors = []
		if not self.lugar_partida_direccion:
			errors.append(
				"* La dirección del lugar de partida es obligatorio.")
		elif len(self.lugar_partida_direccion) < 3 or len(self.lugar_partida_direccion) > 500:
			errors.append(
				"* La dirección del lugar de partida debe poseer entre 3 a 500 caracteres.")

		if not self.lugar_partida_ubigeo:
			errors.append("* El ubigeo del lugar de partida es obligatorio.")
		elif not self.validar_ubigeo(self.lugar_partida_ubigeo):
			errors.append("* El ubigeo de la dirección de partida no existe.")

		return errors

	def validar_ubigeo(self, ubigeo):
		return bool(self.env["l10n_pe.res.city.district"].sudo().search_count([("code", "=", ubigeo)]))
	
	def validar_lugar_llegada(self):
		errors = []
		if self.motivo_traslado != '18':
			if not self.lugar_llegada_direccion:
				errors.append(
					"* La dirección del lugar de llegada es obligatorio.")
			elif len(self.lugar_llegada_direccion) < 3 or len(self.lugar_llegada_direccion) > 500:
				errors.append(
					"* La dirección del lugar de llegada debe poseer entre 3 a 500 caracteres.")

			if not self.lugar_llegada_ubigeo:
				errors.append("* El ubigeo del lugar de llegada es obligatorio.")
			elif self.lugar_llegada_ubigeo and len(self.lugar_llegada_ubigeo) > 6:
				errors.append("* El ubigeo de llegada no puede superar los 6 dígitos.")
			elif not self.validar_ubigeo(self.lugar_llegada_ubigeo):
				errors.append("* El ubigeo de la dirección de llegada no existe.")

		return errors

	def validar_modalidad_transporte(self):
		errors = []
		if not self.transport_type:
			errors.append(
				"* La modalidad de transporte no ha sido seleccionado.")
		elif self.transport_type not in ["01", "02"]:
			errors.append(
				"* La modalidad de transporte seleccionado es incorrecto. Las modalidades de transporte permitidos son 01 - Transporte Público y 02 - Transporte Privado")
		return errors

	def validar_transporte_publico(self):
		errors = []
		if self.transport_type == "01":
			if not self.transporte_partner_id:
				errors.append(
					"* Debe seleccionar una Empresa de Transporte público.")
			else:
				if not self.transporte_partner_id.name:
					errors.append(
						"* La empresa de transporte seleccionada no tiene Nombre o Razón Social.")
				elif len(self.transporte_partner_id.name) < 4 or len(self.transporte_partner_id.name) > 250:
					errors.append(
						"* El nombre de la empresa de transporte seleccionada debe tener entre 4 a 250 caracteres.")

				if not self.transporte_partner_id.l10n_latam_identification_type_id or not self.transporte_partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code:
					errors.append(
						"* La empresa de transporte seleccionada no tiene tipo de documento.")
				elif not self.transporte_partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code == "6":
					errors.append(
						"* El tipo de documento de la empresa de transporte seleccionada debe ser de tipo 'RUC'")

				if not self.transporte_partner_id.vat:
					errors.append(
						"* La empresa de transporte seleccionada no tiene número de documento (RUC).")
				elif not patron_ruc.match(self.transporte_partner_id.vat):
					errors.append(
						"* El RUC de la empresa de transporte seleccionada tiene un formato incorrecto.")
				
				if not self.transporte_partner_mtc_id:
					errors.append(
						"* Debe seleccionar el número de registro del MTC de la empresa de transporte.")
				elif not re.match(r'^[A-Z0-9]{1,20}$', self.transporte_partner_mtc_id.mtc_number):
					errors.append("* El número de registro del MTC debe contener solo letras mayúsculas y números (máx. 20 caracteres).")

				if self.gre_type == 'transportista':
					if not self.transporte_partner_id.street:
						errors.append(
							"* No se encuentra configurado la dirección de la empresa transportista.")
					elif len(self.transporte_partner_id.street) > 200:
						errors.append(
						"* La dirección de la empresa de transporte seleccionada debe tener máximo 200 caracteres.")
					
					if not self.transporte_partner_id.ubigeo:
						errors.append(
							"* No se encuentra configurado el Ubigeo de la empresa transportista.")
					
					if not self.transporte_partner_id.l10n_pe_edi_authorization_issuing_entity:
						errors.append(
							"* La empresa de transporte seleccionada no tiene configurado la Entidad Emisora de Autorización.")
					elif self.transporte_partner_id.l10n_pe_edi_authorization_issuing_entity not in ISSUING_ENTITY:
						errors.append("* La Entidad Emisora de Autorización no pertenece al Catálogo D-37. Comuníquese con su Administrador del Sistema.")
					
					# Se consideró que el número de registro MTC es igual al número de autorización especial
					# if not self.transporte_partner_id.l10n_pe_edi_authorization_number:
					# 	errors.append(
					# 		"* La empresa de transporte seleccionada no tiene configurado el número de autorización especial.")
					# elif not re.match(r'^[A-Za-z0-9]{3,50}$', self.transporte_partner_id.l10n_pe_edi_authorization_number):
					# 	errors.append("* El número de autorización especial debe ser alfanumérico y tener entre 3 y 50 caracteres.")
		return errors

	def validar_transporte_privado(self):
		errors = []
		if self.transport_type == "02":
			if not self.conductor_privado_id:
				errors.append("* Debe seleccionar el conductor del traslado.")
			else:
				errors.extend(self.validar_conductor(self.conductor_privado_id))
			
			if not self.vehiculo_privado_id:
				errors.append("* Debe seleccionar el vehículo del traslado.")
			else:
				errors.extend(self.validar_vehiculo(self.vehiculo_privado_id, self.vehiculo_privado_mtc_id))
			
			#Conductor secundario
			if self.conductor_privado_secundario_id:
				errors.extend(self.validar_conductor(self.conductor_privado_secundario_id))
			#Vehículo secundario
			if self.vehiculo_privado_secundario_id:
				errors.extend(self.validar_vehiculo(self.vehiculo_privado_secundario_id, self.vehiculo_privado_secundario_mtc_id))
		return errors
	
	def validar_conductor(self, conductor):
		errors = []
		if not conductor.name:
			errors.append(
				"* El conductor seleccionado no tiene Nombre.")
		elif len(conductor.name) < 4 or len(conductor.name) > 250:
			errors.append(
				"* El nombre del conductor seleccionado debe tener entre 4 a 250 caracteres.")

		if not conductor.l10n_latam_identification_type_id or not conductor.l10n_latam_identification_type_id.l10n_pe_vat_code:
			errors.append(
				"* El conductor seleccionado no tiene tipo de documento.")
		if not conductor.vat:
			errors.append(
				"* El conductor seleccionado no tiene número de documento.")
		if not conductor.l10n_pe_edi_operator_license:
			errors.append(
				"* El conductor seleccionado no tiene asignado el número de licencia de conducir.")
		elif not re.match(r'^[A-Z0-9]{9,10}$', conductor.l10n_pe_edi_operator_license):
			errors.append("* El número de licencia de conducir debe ser alfanumérico, solo con letras mayúsculas y números (9 a 10 caracteres).")
		return errors
	
	def validar_vehiculo(self, vehiculo, vehiculo_mtc_number):
		errors = []
		if not vehiculo.license_plate:
			errors.append(
				"* El vehículo seleccionado no tiene Número de Placa.")
		elif not re.match(r'^[A-Z0-9]{6,8}$', vehiculo.license_plate):
			errors.append("* El número de placa debe ser alfanumérico, solo con letras mayúsculas y números (6 a 8 caracteres).")
		if not vehiculo.authorization_issuing_entity:
			errors.append(
				"* El vehículo seleccionado no tiene asignado la Entidad emisora de autorización especial.")
		if not vehiculo_mtc_number:
			errors.append(
				"* Debe seleccionar el Número de autorización especial del vehículo.")
		elif len(vehiculo_mtc_number.mtc_number) < 3 or len(vehiculo_mtc_number.mtc_number) > 50:
			errors.append(
				"* El Número de autorización especial debe tener entre 3 a 50 caracteres.")
		return errors
	
	def validar_vehiculo_conductor_publico(self):
		errors = []

		if not self.conductor_publico_id:
			errors.append("* Debe seleccionar el conductor del traslado.")
		else:
			errors.extend(self.validar_conductor(self.conductor_publico_id))
		
		if self.conductor_publico_secundario_id:
			errors.extend(self.validar_conductor(self.conductor_publico_secundario_id))

		if not self.vehiculo_publico_id:
			errors.append("* Debe seleccionar el vehículo del traslado.")
		else:
			errors.extend(self.validar_vehiculo(self.vehiculo_publico_id, self.vehiculo_publico_mtc_id))

		if self.vehiculo_publico_secundario_id:
			errors.extend(self.validar_vehiculo(self.vehiculo_publico_secundario_id, self.vehiculo_publico_secundario_mtc_id))
		
		return errors
	
	def validad_documento_relacionado(self):
		errors = []

		if not self.related_document:
			errors.append("* El documento relacionado es obligatorio.")
			return errors
		# Por el momento solo permitido para Factura, Boleta, Guía de Remisión Remitente
		if self.related_document_code not in ('01', '03', '09'):
			errors.append("* El documento relacionado seleccionado no está permitido.")
			return errors

		patterns = {
			# Factura
			"01": [
				r"^F[A-Z0-9]{3}-[0-9]{1,8}$",
				r"^E001-[0-9]{1,8}$",
				r"^[0-9]{1,4}-[0-9]{1,8}$",
			],
			# Boleta
			"03": [
				r"^B[A-Z0-9]{3}-[0-9]{1,8}$",
				r"^EB01-[0-9]{1,8}$",
				r"^[0-9]{1,4}-[0-9]{1,8}$",
			],
			# Liquidación de compra
			"04": [
				r"^L[A-Z0-9]{3}-[0-9]{1,8}$",
				r"^E001-[0-9]{1,8}$",
				r"^[0-9]{1,4}-[0-9]{1,8}$",
			],
			# DUA / DSI
			"50": [r"^[0-9]{3}-[0-9]{4}-[0-9]{2}-[0-9]{1,6}$"],
			"52": [r"^[0-9]{3}-[0-9]{4}-[0-9]{2}-[0-9]{1,6}$"],
			# RUC 80
			"80": [r"^[0-9]{1,15}$"],
			# Otros documentos
			"12": [r"^[A-Za-z0-9-]{1,20}-[A-Za-z0-9-]{1,20}$"],
			"48": [r"^[0-9]{1,4}-[0-9]{1,7}$"],
			# Guía de remisión remitente
			"09": [
				r"^T[A-Z0-9]{3}-[0-9]{1,8}$",
				r"^EG07-[0-9]{1,8}$",
				r"^EG02-[0-9]{1,8}$",
				r"^[0-9]{1,4}-[0-9]{1,8}$",
			],
			# Guía de remisión transportista
			"31": [
				r"^V[A-Z0-9]{3}-[0-9]{1,8}$",
				r"^EG03-[0-9]{1,8}$",
				r"^EG04-[0-9]{1,8}$",
			],
			# Alfanumérico sin espacios (hasta 100 caracteres)
			"82": [r"^[^\s]{1,100}$"],
			"65": [r"^[^\s]{1,100}$"],
			"66": [r"^[^\s]{1,100}$"],
			"67": [r"^[^\s]{1,100}$"],
			"68": [r"^[^\s]{1,100}$"],
			"69": [r"^[^\s]{1,100}$"],
		}
		code = self.related_document_code

		if code not in catalogo_61:
			errors.append("* El documento relacionado seleccionado no pertenece al Catálogo 61 SUNAT. Comuníquese con su Administrador del Sistema.")
			return errors
		
		# Caso especial: Guía de remisión remitente
		if code == '09':
			patrones = patterns.get(code, [])
			if not self.guia_remitente_id:
				errors.append("* Si el documento relacionado es '[09] Guía de Remisión Remitente' es obligatorio seleccionar una guia remitente válida.")
			else:
				doc_name = self.guia_remitente_id.name or ""
				if not any(re.match(p, doc_name) for p in patrones):
					errors.append(
						f"* El número de documento relacionado '{doc_name}' no cumple el formato definido para '[09] Guía de Remisión Remitente'."
					)

			ruc_emisor_cp = self.guia_remitente_id.company_id.vat
			if not ruc_emisor_cp:
				errors.append("* El RUC del emisor del comprobante relacionado es obligatorio.")
			elif not patron_ruc.match(ruc_emisor_cp):
				errors.append(
					"* El RUC del emisor del comprobante relacionado  no tiene un formato válido.")
			
			return errors
		
		# Para otros tipos de documentos
		numero_doc = (self.related_document_name or "").strip()
		ruc_emisor = (self.related_document_ruc or "").strip()

		if not ruc_emisor:
				errors.append("* El RUC del emisor del comprobante relacionado es obligatorio.")
		elif not patron_ruc.match(ruc_emisor):
			errors.append(
				"* El RUC del emisor del comprobante relacionado  no tiene un formato válido.")
		
		if not numero_doc:
			errors.append("* El número de documento relacionado es obligatorio.")
		else:
			patrones = patterns.get(code, [])
			if not patrones:
				return errors  # No requiere validación especial

			# Validar formato del número
			if not any(re.match(p, numero_doc) for p in patrones):
				errors.append(f"* El número de documento relacionado '{numero_doc}' no cumple el formato definido para el tipo {code}.")

			# Validación de correlativo > 0 para ciertos tipos
			if code in ["01", "03", "04", "09", "31", "48"]:
				partes = numero_doc.split("-")
				if len(partes) >= 2:
					try:
						numero = int(partes[-1])
						if numero <= 0:
							errors.append(f"* El número correlativo '{numero}' debe ser mayor que cero para el tipo {code}.")
					except ValueError:
						errors.append(f"* El número correlativo del documento '{numero_doc}' debe ser numérico.")

			# Validación numérica específica para tipo 80
			if code == "80":
				try:
					numero = int(numero_doc)
					if numero <= 0:
						errors.append("* El número de documento tipo 80 debe ser mayor a cero.")
				except ValueError:
					errors.append("* El número de documento tipo 80 debe ser numérico.")

		return errors
	
	def validar_restricciones_remitente(self):
		errors = []
		errors += self.validar_datos_compania()
		errors += self.validar_datos_destinatario()
		errors += self.validar_motivo_traslado()
		errors += self.validar_fechas()
		errors += self.validar_datos_envio()
		errors += self.validar_guia_remision_lineas()
		errors += self.validar_lugar_partida()
		errors += self.validar_lugar_llegada()
		errors += self.validar_modalidad_transporte()
		errors += self.validar_transporte_privado()
		errors += self.validar_transporte_publico()
		return errors
	
	def validar_restricciones_transportista(self):
		errors = []
		errors += self.validar_datos_compania()
		errors += self.validar_datos_destinatario()
		errors += self.validar_fechas()
		errors += self.validar_datos_envio()
		errors += self.validar_guia_remision_lineas()
		errors += self.validar_lugar_partida()
		errors += self.validar_lugar_llegada()
		errors += self.validar_transporte_publico()
		errors += self.validar_vehiculo_conductor_publico()
		errors += self.validad_documento_relacionado()
		return errors
	
	def validar_comprobante(self):
		for record in self:
			# Validar serie de facturacion
			if not record.journal_id:
				raise ValidationError("Es obligatorio ingresar la serie del comprobante.")
			
			journal = record.journal_id

			if not journal.invoice_type_code:
				raise UserError("La serie no tiene configurado el tipo de comprobante.")
			elif journal.invoice_type_code not in ('09', '31'):
				raise UserError("Tipo de comprobante no válido para la emisión de guias de remisión.")

			if not journal.electronic_invoice:
				raise ValidationError("La serie de facturación seleccionada no está configurado como documento electrónico.")
			
			# Generación de secuencia
			if not record.name or record.name in guide_name_draft:
				serie = journal.code
				seq = journal.jnq_sequence_number or 1
				name = f"{serie}-{str(seq).zfill(8)}"
				exists = self.env["guia.remision"].search_count([
					("name", "=", name),
					("state", "=", "validated"),
				])
				if exists:
					raise UserError(f"Ya existe una guía de remisión validada con el número {name}.")
				# Asignamos el nombre y avanzamos la secuencia
				record.name = name
				journal.sudo().write({ 'jnq_sequence_number': seq + 1 })
			record.state = "validated"
		
	def generar_log_envio(self):
		# Actualizar cuando se implemente la FE con SUNAT
		pass

	def send_gr_xml(self):
		# Actualizar cuando se implemente la FE con SUNAT
		pass
	
	def action_validate(self):
		self.ensure_one()
		if self.gre_type == 'remitente':
			errors = self.validar_restricciones_remitente()
		elif self.gre_type == 'transportista':
			current_company = self.env.company
			if not current_company.partner_id.is_transport_company:
				raise ValidationError(f"La compañía {current_company.name} no esta configurada como empresa de transporte.")
			errors = self.validar_restricciones_transportista()
		if errors:
			raise UserError("Se detectaron los siguientes errores:\n" + "\n".join(errors))
		self.validar_comprobante()
		if not self.company_id.sunat_provider:
			raise ValidationError(f"La compañia {self.company_id.name} no tiene asignado el proveedor de servicios electrónicos.")
		self.generar_log_envio()
		if self.journal_id.send_async:
			self.send_gr_xml()
	
	def action_cancel(self):
		self.ensure_one()
		if self.state != 'draft': 
			raise UserError("Solo se puede cancelar guias en estado Borrador")
		self.write({'state': 'cancel'})

class GuiaRemisionLine(models.Model):
	_name = "guia.remision.line"
	_description = "Líneas de guía de remisión"

	guia_remision_id = fields.Many2one("guia.remision", string="Guia de remision", ondelete='cascade')
	product_id = fields.Many2one("product.product")
	qty = fields.Float(string="Cantidad", digits='Product Unit of Measure')
	uom_id = fields.Many2one("uom.uom", string="UM", required=True)
	description = fields.Char(string="Descripción", required=True)
	stock_picking_id = fields.Many2one("stock.picking", "Movimiento de Stock")
	#weight = fields.Float(string='Peso total (Kg)', default=0.0)

	# @api.constrains('uom_id')
	# def _check_uom_id(self):
	#     for record in self:
	#         if record.uom_id.code not in codigo_unidades_de_medida:
	#             raise UserError("La unidad de medida seleccionada no posee un código válido.")

	@api.constrains('description')
	def _check_description(self):
		for record in self:
			if len(record.description) < 3 or len(record.description) > 500:
				raise UserError("La descripción del producto debe tener entre 3 a 500 caracteres.")

	@api.onchange('description')
	def _onchange_description(self):
		if self.description:
			self.description = self.description.strip().replace("\n", "")

	@api.onchange('product_id')
	def _onchange_product(self):
		for record in self:
			record.description = record.product_id.name
			record.uom_id = record.product_id.uom_id.id

	@api.constrains('qty')
	def _check_qty(self):
		for record in self:
			if record.qty < 0:
				raise UserError("La cantidad de las líneas de producto no pueden ser negativas.")
	
	# @api.onchange('product_id','qty','uom_id')
	# def _compute_weight(self):
	# 	for record in self:
	# 		record.weight = record.product_id.weight*record.qty*(record.uom_id.factor_inv / record.product_id.uom_id.factor_inv) if record.product_id.uom_id.factor_inv > 0 else 0
