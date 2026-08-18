# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api
import base64
import json
from ..utils import get_request_guide_body, get_log_status_guide, get_guide_status, get_guide_files, get_pdf_link_guide
import requests,re
import logging
_logger = logging.getLogger(__name__)

class TransferReason(models.Model):
	
	_inherit = "transfer.reason"
	
	jnq_code_pecanofact = fields.Char('Código PecanoFact')

class TransportType(models.Model):

	_inherit = "transport.type"
	  
	jnq_code_pecanofact = fields.Char('Código PecanoFact')

class RelatedDocument(models.Model):

	_inherit = "related.document"
	  
	jnq_code_pecanofact = fields.Char('Código PecanoFact')

class GuiaRemision(models.Model):

	_inherit = "guia.remision"

	guide_document_id = fields.Many2one('ir.attachment', string='Documento electrónico', copy=False)
	guide_pdf_file = fields.Binary(
		related='guide_document_id.datas',
		string='PDF',
		readonly=True,
	)
	guide_pdf_file_name = fields.Char(
		related='guide_document_id.name',
		string='Nombre de PDF'
	)
	xml_guide_id = fields.Many2one('ir.attachment',string='Documento electrónico(XML)',copy=False)
	guide_xml_file = fields.Binary(
		related='xml_guide_id.datas',
		string='XML',
		readonly=True,
	)
	guide_xml_file_name = fields.Char(
		related='xml_guide_id.name',
		string='Nombre de XML'
	)
	cdr_guide_id = fields.Many2one('ir.attachment',string='Documento electrónico(CDR)',copy=False)
	guide_cdr_file = fields.Binary(
		related='cdr_guide_id.datas',
		string='CDR',
		readonly=True,
	)
	guide_cdr_file_name = fields.Char(
		related='cdr_guide_id.name',
		string='Nombre de CDR'
	)
	attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'guia.remision')], string='Adjuntos')
	submitted_pecanofact = fields.Boolean(string='Enviado por PecanoFact', default=False, copy=False)
	status_pecanofact = fields.Selection(string="Estado de CPE en Pecanofact", related="current_log_status_id.status_pecanofact", store=True)

	def get_token_pecanofact(self):
		return self.env.company.get_token_pecanofact()
	
	def create_log_status_observation(self, log, code, message):
		if log:
			self.env["account.log.status.observation"].create({
				"code": code,
				"description": message,
				"account_log_status_id": log.id,
			})
	
	def generar_log_envio(self):
		self.ensure_one()
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			token = self.get_token_pecanofact()
			pecano_base_url = self.company_id.pecano_base_url_prod if self.company_id.electronic_invoicing_type_environment == '1' else self.company_id.pecano_base_url_test
			if self.journal_id.invoice_type_code == '09' or self.gre_type == 'remitente':
				url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/guiaremitente"
			else:
				url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/guiatransportista"
			headers = {
				"Content-Type": "application/json",
				"TOKEN-PSE-PECANOFACT": token,
			}
			body = get_request_guide_body(self)
			log_data = get_log_status_guide(self, body) # [ OBTENER: INFORMACIÓN PARA EL LOG ]
			guide_log_status = self.env["account.log.status"].create(log_data) # [ CREAR: LOG ]
			guide_log_status.action_set_last_log() # [ SETEAR: LOG ]
			self.request_json = json.dumps(body, indent=4, ensure_ascii=False) # [ ACTUALIZAR: INFORMACIÓN DE LA GUÍA DE REMISIÓN ]
			_logger.info("JSON enviado a PecanoFact (GRE %s):\n%s", self.name, self.request_json)
			try:
				# [ Envío de GRE ]
				response = requests.post(url, headers=headers, json=body, timeout=60)
				if response.status_code == 200:
					response_json = response.json()
					self.submitted_pecanofact = True
					digest_value = response_json.get('DigestValue', '')
					guide_log_status.write({"digest_value": digest_value})
					# [ Si el envío no es asíncrono, consultar el estado ]
					if not self.journal_id.send_async:
						try:
							result = get_guide_status(self)
							guide_log_status.write(result)
						except UserError as e:
							self.create_log_status_observation(guide_log_status, "CONSULTA_ESTADO_CPE", str(e))
						try:
							result = get_guide_files(self) # [ OBTENER: INFORMACIÓN DEL LOG ACTUAL ]
							guide_log_status.write(result)
						except UserError as e:
							self.create_log_status_observation(guide_log_status, "CONSULTA_ARCHIVOS_CPE", str(e))
				elif response.status_code in (400, 404):
					error_msg = response.json().get("MensajeError", "Error desconocido")
					self.create_log_status_observation(guide_log_status, "VALIDATION_ERROR",error_msg)
					raise UserError(error_msg)
				elif response.status_code == 500:
					error_code = response.json().get("CodigoError", "Error desconocido")
					error_msg = f"Error interno del servidor PecanoFact. Código: {error_code}"
					self.create_log_status_observation(guide_log_status, "SERVER_ERROR", error_msg)
					raise UserError(error_msg)
				else:
					error_msg = f"Error inesperado HTTP al enviar GRE. Código: {response.status_code}"
					self.create_log_status_observation(guide_log_status, "HTTP_ERROR", error_msg)
					raise UserError(error_msg)

			except requests.exceptions.Timeout:
				error_msg = "Tiempo de espera agotado al enviar GRE a PecanoFact."
				self.create_log_status_observation(guide_log_status, "TIMEOUT", error_msg)
				raise UserError(error_msg)
			except requests.exceptions.ConnectionError:
				error_msg = "No se pudo conectar con el servidor de PecanoFact."
				self.create_log_status_observation(guide_log_status, "CONNECTION_ERROR", error_msg)
				raise UserError(error_msg)
			except Exception as e:
				error_msg = f"Ocurrió un error inesperado: {str(e)}"
				self.create_log_status_observation(guide_log_status, "UNEXPECTED_ERROR", error_msg)
				raise UserError(error_msg)
		else:
			return super(GuiaRemision,self).generar_log_envio()
	
	def send_gr_xml(self):
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			if not self.current_log_status_id: # [ EVALUAR: LOG ACTUAL ]
				self.generar_log_envio()
			try:
				result = get_guide_files(self) # [ OBTENER: INFORMACIÓN DEL LOG ACTUAL ]
				self.current_log_status_id.write(result) # [ ACTUALIZAR: INFORMACIÓN DEL LOG ACTUAL ]
				return result
			except Exception as e:
				raise UserError(f"Ocurrió un error al enviar la guía a PecanoFact: {str(e)}")
		else:
			return super(GuiaRemision,self).send_gr_xml()
	
	# [ Validez de GRE ]
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

	def action_check_gre(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Consulta Validez GRE' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Consulta Validez GRE' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		# ConsultaCPE x NumeroDocumento
		result = get_guide_status(self)
		self.current_log_status_id.write(result)
		# ConsultaArchivoCpe x Documento 
		result = get_guide_files(self)
		self.current_log_status_id.write(result)
		pdf = self.current_log_status_id.signed_xml
		if pdf and not self.guide_document_id:
			attachment = self._get_or_create_attachment(
				name=f"{self.name}.pdf",
				base64_data=pdf,
				mimetype='application/pdf'
			)
			self.sudo().write({
				'guide_document_id': attachment.id,
				'attachment_ids': [(4,attachment.id,0)]
			})
		xml = self.current_log_status_id.xml_base64
		xml_name = self.current_log_status_id.xml_name
		if xml and not self.xml_guide_id:
			attachment = self._get_or_create_attachment(
				name=xml_name or f"{self.name}.xml",
				base64_data=xml,
				mimetype='application/xml'
			)
			self.sudo().write({
				'xml_guide_id': attachment.id,
				'attachment_ids': [(4,attachment.id,0)]
			})
		if self.estado_gre_sunat in ["A", "O"]:
			cdr = self.current_log_status_id.cdr_base64
			cdr_name = self.current_log_status_id.cdr_name
			if cdr and not self.cdr_guide_id:
				attachment = self._get_or_create_attachment(
					name=cdr_name or f"R-{self.name}.xml",
					base64_data=cdr,
					mimetype='application/xml'
				)
				self.sudo().write({
					'cdr_guide_id': attachment.id,
					'attachment_ids': [(4,attachment.id,0)]
				})
		#self.env.cr.commit()
		# ConsultaEnlacePDFxDocumento
		# pdf_link = get_pdf_link_guide(self)
		# self.current_log_status_id.write({'pdf_link_pecanofact': pdf_link})
	
	# [ GENERAR: PDF DE DOCUMENTO ELECTRÓNICO ]
	def generate_pdf(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Generar PDF' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Generar PDF' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		pdf = self.current_log_status_id.signed_xml
		if not pdf:
			raise UserError("No se puede generar el pdf(puede ocurrir porque se rechazó el documento electrónico o porque aún no ha sido enviado a PECANOFACT). Por favor, revise la información correspondiente.")
		if not self.guide_document_id:
			attachment = self._get_or_create_attachment(
				name=f"{self.name}.pdf",
				base64_data=pdf,
				mimetype='application/pdf'
			)
			self.sudo().write({
				'guide_document_id': attachment.id,
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
	
	# [ PREVISUALIZAR: PDF DE DOCUMENTO ELECTRÓNICO ]
	def preview_pdf(self):
		self.ensure_one()
		if not self.env.company.sunat_provider == 'pecanofact' or not self.company_id.sunat_provider == 'pecanofact':
			raise UserError("La acción 'Visualizar PDF' solo puede ser realizada por una empresa que tiene como proveedor de facturación a PECANOFACT.")
		if not self.submitted_pecanofact:
			raise UserError("La acción 'Visualizar PDF' solo puede ser realizada para aquellos documentos electrónicos que han sido enviados con los servicios del proveedor de facturación PECANOFACT.")
		url = self.current_log_status_id.pdf_link_pecanofact if self.current_log_status_id.pdf_link_pecanofact else False
		if url:
			return {
				'type': 'ir.actions.act_url',
				'target': 'new',
				'url': url,
			}
		else:
			raise UserError("No se puede visualizar el pdf(puede ocurrir porque se rechazó el documento electrónico o aún no ha sido enviado a PECANOFACT). Por favor, revise la información correspondiente.")
	
	@api.model
	def cron_action_validez_gre_pecano(self, limit=False, start=False, end=False, ids=False):
		today = fields.Date.today()
		# Limite de documentos a obtener de la consulta 
		limit = limit if limit else 50
		# Dominio BASE
		domain = [
			("journal_id.electronic_invoice", "=", True), # Que el diario sea para envío a SUNAT
			("name", "not in", [False, "/"]), # Que tenga nombre o número establecido
			("journal_id.invoice_type_code", "in", ["09", "31"]), # Que el código sea gre remitente, gre transportista
			("state", "in", ["validated","cancel"]), # Que esté publicado o cancelado                
		]
		# Fecha de inicio y fin del periodo a consultar
		if start and end:
			domain += [
				("fecha_emision", ">=", start),
				("fecha_emision", "<=", end)
			]
		else:
			domain.append(("fecha_emision", "<=", today))
		
		# Identificadores
		if ids:
			domain.append(("id", "in", ids))
		else:
			domain += [
				("status_pecanofact", "in", ["0", "2", False]), # Que el estado electrónico sea 0 (En proceso), 2(Anulado), o simplemente no tenga (consulta a Pecanofact)
			]    
		guides = self.env["guia.remision"].sudo().search(domain, limit=limit, order="fecha_emision asc")

		for guide in guides:
			try:
				# PecanoFact
				result = get_guide_status(guide)
				guide.current_log_status_id.write(result)
				# Commit
				self.env.cr.commit()
			except Exception as e:
				_logger.error("Error procesando guia %s (%s): %s",guide.name, guide.id, e)
				self._cr.rollback()