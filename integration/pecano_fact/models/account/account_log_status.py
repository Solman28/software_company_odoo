# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api
from ..utils import get_request_check_invoice
import requests
import json

class AccountLogStatus(models.Model):
	_inherit = "account.log.status"

	pdf_link_pecanofact = fields.Char(string="Enlace PDF PecanoFact")
	status_pecanofact = fields.Selection(
		string="Estado de CPE en Pecanofact",
		selection=[
			('0', 'En Proceso'),
			('1', 'Aceptado'),
			('2', 'Anulado'),
			('3', 'Rechazado'),
		]
	)
	submitted_pecanofact = fields.Boolean(string='Enviado por PecanoFact', default=False, copy=False)

	def get_token_pecanofact(self):
		return self.env.company.get_token_pecanofact()
	
	# [ VALIDEZ DEL COMPROBANTE ]
	def _request_api_check_invoice_validity(self):
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			try:
				token = self.get_token_pecanofact()
				company_id = self.company_id
				
				pecano_base_url = company_id.pecano_base_url_prod if company_id.electronic_invoicing_type_environment == '1' else company_id.pecano_base_url_test
				url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/consulta/archivo/documento"
				
				headers = {
					"Content-Type": "application/json",
					"TOKEN-PSE-PECANOFACT": token,
				}
				# ConsultaArchivoCpe x Documento 
				body = get_request_check_invoice(self)
				response = requests.post(url, json=body, headers=headers, timeout=20)
				if response.status_code == 200:
					response = json.loads(response.text)
					estado_documento = response.get("EstadoDocumento", "")
					if estado_documento == 0:
						status_receipt = '0_EN_PROCESO'
						estado_emision = 'E'
					if estado_documento == 1:
						status_receipt = '1_ACEPTADO'
						estado_emision = 'A'
					elif estado_documento == 2:
						status_receipt = '2_ANULADO'
						estado_emision = 'A'
					elif estado_documento == 3:
						status_receipt = '3_RECHAZADO'
						estado_emision = 'R'
					else:
						status_receipt = '-'
					self.account_move_id.consulta_validez_observaciones = ""
					self.status = estado_emision
					self.account_move_id.estado_comprobante_electronico = status_receipt
					self.status_pecanofact = str(estado_documento)
				elif response.status_code in (400, 404):
					error = response.get("MensajeError", "Error desconocido")
					self.account_move_id.consulta_validez_observaciones = error
				elif response.status_code == 500:
					code_error = response.get("CodigoError", "Error desconocido")
					self.account_move_id.consulta_validez_observaciones = code_error
				else:
					self.account_move_id.consulta_validez_observaciones = f"Respuesta HTTP inesperada ({response.status_code})"
			except requests.exceptions.Timeout:
				self.account_move_id.consulta_validez_observaciones = "Tiempo de espera agotado al consultar PecanoFact."
			except requests.exceptions.ConnectionError:
				self.account_move_id.consulta_validez_observaciones = "No se pudo conectar con el servidor de PecanoFact."
			except UserError as e:
				self.account_move_id.consulta_validez_observaciones = str(e)
			except Exception as e:
				self.account_move_id.consulta_validez_observaciones = f"Error inesperado al consultar PecanoFact: {e}"
		else:
			return super(AccountLogStatus,self)._request_api_check_invoice_validity()