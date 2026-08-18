from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from ..utils import get_request_baja_document_body, update_low, get_log_status_anulacion, get_invoice_status
import requests,re
import json

class AccountComunicacionBaja(models.Model):
	_inherit = "account.comunicacion_baja"
	
	submitted_pecanofact = fields.Boolean(string='Enviado por PecanoFact', default=False, copy=False)

	def get_token_pecanofact(self):
		return self.env.company.get_token_pecanofact()
	
	# [ FORM: ANULAR COMPROBANTES ELECTRÓNICOS (FACTURAS Y NOTAS ASOCIADAS) ]
	def action_generate_and_signed_xml(self):
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			bodies = get_request_baja_document_body(self) # [ OBTENER: LISTA DE CUERPOS DE LAS FACTURAS A ANULAR ]
			token = self.get_token_pecanofact()
			pecano_base_url = self.company_id.pecano_base_url_prod if self.company_id.electronic_invoicing_type_environment == '1' else self.company_id.pecano_base_url_test
			url = f"{pecano_base_url.rstrip('/')}/api/v2/cpe/anulacion"
			headers = {
				"Content-Type": "application/json",
				"TOKEN-PSE-PECANOFACT": token,
			}
			for body in bodies:
				response = requests.post(url, headers=headers, json=body, timeout=60) # [ REALIZAR EL ENVIO ]
				if response.status_code == 200:
					result = update_low(json.loads(response.text), self, body) # [ OBTENER: INOFRMACIÓN DEL LOG ]
					log_status_obj = self.env["account.log.status"].create(result) # [ CREAR: LOG]
					log_status_obj.action_set_last_log() # [ "SETEAR": LOG ]
					#self.submitted_pecanofact = True	
		else:
			return super(AccountComunicacionBaja,self).action_generate_and_signed_xml()

	# [ FORM: ANULAR COMPROBANTES ELECTRÓNICOS (FACTURAS Y NOTAS ASOCIADAS) || CRON: ENVÍO DE COMUNICACIONES DE BAJA PENDIENTES ]
	def action_send_voided(self):
		if self.env.company.sunat_provider == 'pecanofact' and self.company_id.sunat_provider == 'pecanofact': # [ EVALUAR: PROVEEDOR DE FACTURACIÓN ]
			if not self.account_log_status_ids or len(self.invoice_ids) != len(self.account_log_status_ids): # [ EVALUAR: LISTA DE LOG DE FACTURAS A ANULAR ]
				self.action_generate_and_signed_xml()
			result = {}
			if all(self.invoice_ids.mapped(lambda r:r.status_pecanofact == "1")): # [ EVALUAR: ESTADO DE LAS FACTURAS A ANULAR ]
				for account_log in self.account_log_status_ids: # [ RECORRER: LOGS DE FACTURAS A ANULAR ]
					try:
						# [ ACTUALIZAR ESTADO DEL CPE ]
						# result = get_invoice_status(self)
						# account_log.invoice_id.current_log_status_id.write(result)
						result = get_log_status_anulacion(account_log) # [ OBTENER: INFORMACIÓN ACTUAL DEL LOG ]
						account_log.write(result) # [ ACTUALIZAR: INFORMACIÓN DEL LOG ]
					except Exception as e:
						raise e
		else:
			return super(AccountComunicacionBaja,self).action_send_voided()