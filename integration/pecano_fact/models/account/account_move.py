from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api
from ..utils import get_request_invoice_body, vals_log_cpe, get_invoice_status, get_invoice_files, get_pdf_link_invoice
import requests,re
import base64
import json
from datetime import datetime
from pytz import timezone
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
	_inherit = "account.move"

	#estado_comprobante_electronico = fields.Selection(selection_add=[('0_EN_PROCESO', 'EN PROCESO'), ('3_RECHAZADO', 'RECHAZADO')])
	status_pecanofact = fields.Selection(string="Estado de CPE en Pecanofact", related="current_log_status_id.status_pecanofact", store=True)
	invoice_document_id = fields.Many2one('ir.attachment', string='Documento electrónico', copy=False)
	invoice_pdf_file = fields.Binary(
		related='invoice_document_id.datas',
		string='PDF',
		readonly=True,
	)
	invoice_pdf_file_name = fields.Char(
		related='invoice_document_id.name',
		string='Nombre de PDF'
	)
	xml_document_id = fields.Many2one('ir.attachment',string='Documento electrónico(xml)',copy=False)
	invoice_xml_file = fields.Binary(
		related='xml_document_id.datas',
		string='XML',
		readonly=True,
	)
	invoice_xml_file_name = fields.Char(
		related='xml_document_id.name',
		string='Nombre de XML'
	)
	cdr_invoice_id = fields.Many2one('ir.attachment',string='Documento electrónico(CDR)',copy=False)
	invoice_cdr_file = fields.Binary(
		related='cdr_invoice_id.datas',
		string='CDR',
		readonly=True,
	)
	invoice_cdr_file_name = fields.Char(
		related='cdr_invoice_id.name',
		string='Nombre de CDR'
	)
	submitted_pecanofact = fields.Boolean(string='Enviado por PecanoFact', default=False, copy=False)
	sunat_observacion_venta = fields.Char(
		string="Observación de la venta",
		size=100,
		help="Observación opcional",
	)
	consulta_validez_observaciones_pecano = fields.Text(related="current_log_status_id.sunat_observaciones", string="Observaciones PECANO")

	def validar_moneda(self):
		errors = []
		if not self.currency_id:
			errors.append(
				"* La moneda del documento es obligatorio.")
			return errors
		pecano_code = (self.currency_id.jnq_code_pecanofact or "").strip()
		if not pecano_code:
			errors.append(
				"* La moneda seleccionada no tiene configurado el código PecanoFact.")
		elif pecano_code not in ("1", "2"):
			errors.append(
				"* El código PecanoFact de la moneda seleccionada no es un valor válido.")
		return errors

	# [ FORM: CONFIRMAR ]        
	def action_post(self):
		# 01 : FACTURA ELECTRÓNICA
		# 03 : BOLETA ELECTRÓNICA
		# 07 : NOTA DE CRÉDITO
		# 08 : NOTA DE DÉBITO
		# 09 : GRE REMITENTE
		# 31 : GRE TRANSPORTISTA
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact':
			for move in self:
				if move.journal_id not in move.suitable_journal_ids:
					raise ValidationError("La serie no es valida para este documento, verifica que este en 'Series permitidas'")
				move.check_paymenttermn_lines()
				if not move.company_id.sunat_provider or move.journal_id.invoice_type_code not in ['01', '03', '07', '08', '09', '31']:
					return super(AccountMove, move).action_post()
				else:
					# [ COMPROBANTES DE PROVEEDOR ]
					if move.move_type in ["in_invoice", "in_refund", "in_receipt"]:
						move._validate_inv_supplier_ref()
						return super(AccountMove, move).action_post()

					if not move.journal_id.electronic_invoice:
						return super(AccountMove, move).action_post()
					else:
						# [ COMPROBANTES DE VENTA ]
						msg_error = []
						# [ Validar retencion ]
						msg_error += move.validate_requeriment_apply_retention()
						# [ Validar detraccion ]
						msg_error += move.validate_requeriment_apply_detraction()
						msg_error += move.validar_datos_compania()
						msg_error += move.validar_datos_cliente()
						msg_error += move.validar_diario()

						# [ VALIDACION PARA PECANO ]
						msg_error += move.validar_moneda()

						current_user = self.env.user
						if not current_user.has_group('electronic_invoicing_base.group_user_sunat_send_out_date'):
							msg_error += move.validar_fecha_emision()

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

						res = super(AccountMove, move).action_post()
						if type(res) == dict and res.get('type') == 'ir.actions.act_window':
							return res
						
						move.action_generate_and_signed_xml()

						if not move.journal_id.send_async:
							move.action_send_invoice()

						move.submitted_pecanofact = True
		else:
			return super(AccountMove,self).action_post() # [ CONTINUAR CON LA EJECUCIÓN DE CONFIRMAR / PUBLICAR DOCUMENTO ELECTRÓNICO ]
		
	def get_token_pecanofact(self):
		return self.env.company.get_token_pecanofact()
	
	def create_log_status_observation(self, log, code, message):
		if log:
			self.env["account.log.status.observation"].create({
				"code": code,
				"description": message,
				"account_log_status_id": log.id,
			})
	
	def action_send_invoice(self):
		self.ensure_one()
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			if not (self.current_log_status_id and (self.journal_id.invoice_type_code == "01" or self.journal_id.tipo_comprobante_a_rectificar == "01")): # [ EVALUAR LOG ACTUAL ]
				self.action_generate_and_signed_xml()
			if self.current_log_status_id.status in ["P", "N", False]: # [ EVALUAR: ESTADO DEL LOG ACTUAL ]
				invoice_log_status = self.current_log_status_id
				token = self.get_token_pecanofact()
				pecano_base_url = self.company_id.pecano_base_url_prod if self.company_id.electronic_invoicing_type_environment == '1' else self.company_id.pecano_base_url_test
				url = ''
				if self.journal_id.invoice_type_code == '01':
					url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/factura"
				elif self.journal_id.invoice_type_code == '03':
					url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/boleta"
				elif self.journal_id.invoice_type_code == '07':
					url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/notacredito"
				if not url:
					raise ValidationError(f"No se estableció la URL de envío para el tipo de comprobante {self.journal_id.name}.")
				headers = {
					"Content-Type": "application/json",
					"TOKEN-PSE-PECANOFACT": token,
				}
				body = get_request_invoice_body(self)
				try:
					# [ Envío del comprobante ]
					response = requests.post(url, headers=headers, json=body, timeout=60)
					if response.status_code == 200:
						response_json = response.json()
						self.submitted_pecanofact = True						
						digest_value = response_json.get('DigestValue', '')
						invoice_log_status.write({"digest_value": digest_value})
						try:
							result = get_invoice_status(self)
							invoice_log_status.write(result)
						except UserError as e:
							self.create_log_status_observation(invoice_log_status, "CONSULTA_ESTADO_CPE", str(e))
						try:
							result = get_invoice_files(self) # [ OBTENER: INFORMACIÓN DEL LOG ACTUAL ]
							invoice_log_status.write(result)
						except UserError as e:
							self.create_log_status_observation(invoice_log_status, "CONSULTA_ARCHIVOS_CPE", str(e))
					elif response.status_code in (400, 404):
						error_msg = response.json().get("MensajeError", "Error desconocido")
						self.create_log_status_observation(invoice_log_status, "VALIDATION_ERROR",error_msg)
						raise UserError(error_msg)
					elif response.status_code == 500:
						error_code = response.json().get("CodigoError", "Error desconocido")
						error_msg = f"Error interno del servidor PecanoFact. Código: {error_code}"
						self.create_log_status_observation(invoice_log_status, "SERVER_ERROR", error_msg)
						raise UserError(error_msg)
					else:
						error_msg = f"Error inesperado HTTP al enviar comprobante. Código: {response.status_code}"
						self.create_log_status_observation(invoice_log_status, "HTTP_ERROR", error_msg)
						raise UserError(error_msg)
				except requests.exceptions.Timeout:
					error_msg = "Tiempo de espera agotado al enviar comprobante a PecanoFact."
					self.create_log_status_observation(invoice_log_status, "TIMEOUT", error_msg)
					raise UserError(error_msg)
				except requests.exceptions.ConnectionError:
					error_msg = "No se pudo conectar con el servidor de PecanoFact."
					self.create_log_status_observation(invoice_log_status, "CONNECTION_ERROR", error_msg)
					raise UserError(error_msg)
				except Exception as e:
					error_msg = f"Ocurrió un error inesperado: {str(e)}"
					self.create_log_status_observation(invoice_log_status, "UNEXPECTED_ERROR", error_msg)
					raise UserError(error_msg)
		else:
			return super(AccountMove,self).action_send_invoice()
	
	def action_generate_and_signed_xml(self):
		self.ensure_one()
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact':
			if not self.current_log_status_id:
				body = get_request_invoice_body(self) # [ OBTENER: CUERPO ]
				log_status = vals_log_cpe(self, body) # [ OBTENER: OBTENER VALORES DE LOG DE ENVIO ]
				account_log_status = self.env["account.log.status"].create(log_status) # [ CREAR: LOG ]
				account_log_status.action_set_last_log() # [ "SETEAR": LOG ]
		else:
			return super(AccountMove,self).action_generate_and_signed_xml()
	
	# [ Validez de CPE ]
	def _get_or_create_attachment(self, name, base64_data, mimetype):
		self.ensure_one()

		attachment = self.env['ir.attachment'].search([
			('res_model', '=', self._name),
			('res_id', '=', self.id),
			('name', '=', name),
		], limit=1)

		if attachment:
			return attachment

		return self.env['ir.attachment'].sudo().create({
			'name': name,
			'type': 'binary',
			'datas': base64_data,
			'res_model': self._name,
			'res_id': self.id,
			'mimetype': mimetype,
		})
	
	def action_check_invoice(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Consulta Validez CPE' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Consulta Validez CPE' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		# ConsultaCPE x NumeroDocumento
		result = get_invoice_status(self)
		self.current_log_status_id.write(result)
		# ConsultaArchivoCpe x Documento 
		result = get_invoice_files(self)
		self.current_log_status_id.write(result)
		pdf = self.current_log_status_id.signed_xml
		if pdf and not self.invoice_document_id:
			type = ''
			if self.journal_id.invoice_type_code == '01':
				type = 'Factura Electrónica'
			if self.journal_id.invoice_type_code == '03':
				type = 'Boleta Electrónica'
			if self.journal_id.invoice_type_code == '07':
				type = 'Nota de Crédito Electrónica'
			if self.journal_id.invoice_type_code == '08':
				type = 'Nota de Débito Electrónica'
			attachment = self._get_or_create_attachment(
				name= f"{type} {self.name}.pdf",
				base64_data=pdf,
				mimetype='application/pdf'
			)
			self.sudo().write({
				'invoice_document_id': attachment.id,
				'attachment_ids': [(4,attachment.id,0)]
			})
		xml = self.current_log_status_id.xml_base64
		xml_name = self.current_log_status_id.xml_name
		if xml and not self.xml_document_id:
			attachment = self._get_or_create_attachment(
				name=xml_name or f"{self.name}.xml",
				base64_data=xml,
				mimetype='application/xml'
			)
			self.sudo().write({
				'xml_document_id': attachment.id,
				'attachment_ids': [(4,attachment.id,0)]
			})
		if self.estado_emision in ["A", "O"]:
			cdr = self.current_log_status_id.cdr_base64
			cdr_name = self.current_log_status_id.cdr_name
			if cdr and not self.cdr_invoice_id:
				attachment = self._get_or_create_attachment(
					name=cdr_name or f"R-{self.name}.xml",
					base64_data=cdr,
					mimetype='application/xml'
				)
				self.sudo().write({
					'cdr_invoice_id': attachment.id,
					'attachment_ids': [(4,attachment.id,0)]
				})
	
	# [ PREVISUALIZAR: PDF DE DOCUMENTO ELECTRÓNICO ]
	# def preview_pdf(self):
	# 	self.ensure_one()
	# 	if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
	# 		raise UserError("La acción 'Visualizar PDF' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
	# 	if not self.submitted_pecanofact:
	# 		raise UserError("La acción 'Visualizar PDF' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
	# 	try:
	# 		pdf_link = get_pdf_link_invoice(self)
	# 		self.current_log_status_id.write({'pdf_link_pecanofact': pdf_link})
	# 		if pdf_link:
	# 			return {
	# 				'type': 'ir.actions.act_url',
	# 				'target': 'new',
	# 				'url': pdf_link,
	# 			} 
	# 	except Exception as e:
	# 		raise UserError(f"Ocurrió un error al obtener el enlace PDF del comprobante: {str(e)}")
	
	# [ GENERAR: PDF DE DOCUMENTO ELECTRÓNICO ]
	def generate_pdf(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Generar PDF' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Generar PDF' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		pdf = self.current_log_status_id.signed_xml # [ BASE64 PDF ]
		if not pdf:
			raise UserError("No se puede generar el pdf(puede ocurrir porque se rechazó el documento electrónico o porque aún no ha sido enviado a PECANOFACT). Por favor, revise la información correspondiente.")
		if not self.invoice_document_id:
			type = ''
			if self.journal_id.invoice_type_code == '01':
				type = 'Factura Electrónica'
			if self.journal_id.invoice_type_code == '03':
				type = 'Boleta Electrónica'
			if self.journal_id.invoice_type_code == '07':
				type = 'Nota de Crédito Electrónica'
			if self.journal_id.invoice_type_code == '08':
				type = 'Nota de Débito Electrónica'
			attachment = self._get_or_create_attachment(
				name= f"{type} {self.name}.pdf",
				base64_data=pdf,
				mimetype='application/pdf'
			)
			self.sudo().write({
				'invoice_document_id': attachment.id,
				'attachment_ids': [(4,attachment.id,0)]
			})
	
	# [ IMPRIMIR: PDF DE DOCUMENTO ELECTRÓNICO]
	def print_pdf(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Imprimir PDF' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Imprimir PDF' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		pdf = self.current_log_status_id.signed_xml # [ BASE64 PDF ]
		if pdf:
			return {
				'type': 'ir.actions.client',
				'tag': 'print',
				'id': self.id,
				'params': { 'file64': pdf }
			}
		else:
			raise UserError("No se puede imprimir el pdf(puede ocurrir porque se rechazó el documento electrónico o porque aún no ha sido enviado a PECANOFACT). Por favor, revise la información correspondiente.")
			
	# [ BOTÓN: ANULAR COMPROBANTE ]
	def btn_comunicacion_baja(self):
		self.ensure_one()
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact':
			tz = self.env.user.tz or "America/Lima"
			if self.estado_comprobante_electronico == "2_ANULADO":
				raise UserError("Este comprobante ya se encuentra ANULADO.")
			
			if re.match(r"^F\w{3}-\d{1,8}$", self.name) or re.match(r"^B\w{3}-\d{1,8}$", self.name):
				if self.documento_baja_id:
					ref = self.env.ref("company_electronic_invoicing_base.view_comunicacion_baja_form")
					return {
						"type": "ir.actions.act_window",
						"res_model": "account.comunicacion_baja",
						"target": "self",
						"res_id": self.documento_baja_id.id,
						"view_mode": "form",
						"view_id": ref.id,
					}
				else:
					ref = self.env.ref("company_electronic_invoicing_base.view_comunicacion_baja_form_simple")
					return {
						"type": "ir.actions.act_window",
						"res_model": "account.comunicacion_baja",
						"name": "Comunicación de baja o Anulación de comprobante",
						"target": "new",
						"view_id": ref.id,
						"view_mode": "form",
						"context": {
							'default_company_id': self.company_id.id,
							'default_invoice_type_code_id': self.journal_id.invoice_type_code,
							'default_date_invoice': self.invoice_date,
							'default_voided_date': datetime.now(tz=timezone(tz)),
							'default_invoice_id': self.id,
						}
					}
		else:
			raise ValidationError(f"La compañía {self.company_id.name} no tiene configurado a PECANOFACT como empresa facturadora. Por favor, contacte con el usuario administrador para más información.")

	# [ CRON ]
	@api.model
	def cron_action_validez_comprobante_pecano(self, limit=False, start=False, end=False, ids=False):
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
					("status_pecanofact", "in", ["0", False]), # Que el estado electrónico sea 0 (En proceso), o simplemente no tenga (consulta a Pecanofact)
					'&',
						("documento_baja_id", "!=", False), # Que tenga un documento de baja asociado
						("status_pecanofact", "!=", "2"), # Que el estado electrónico no sea anulado (consulta a Pecanofact)
			]    
		invoices = self.env["account.move"].sudo().search(domain, limit=limit, order="invoice_date asc")
		for invoice in invoices:
			try:
				# PecanoFact
				result = get_invoice_status(invoice)
				invoice.current_log_status_id.write(result)
				# Commit
				self.env.cr.commit()
			except Exception as e:
				_logger.error("Error procesando factura %s (%s): %s",invoice.name, invoice.id, e)
				self._cr.rollback()