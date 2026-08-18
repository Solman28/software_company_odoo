from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import re

patron_dni = re.compile(r"\d{8}$")
patron_ruc = re.compile(r"[12]\d{10}$")


class SaleAdvancePaymentInv(models.TransientModel):
	_inherit = 'sale.advance.payment.inv'
	

	def create_invoices(self):
		for sale_order in self.sale_order_ids:
			# [ Validar almacen y diario/serie ]
			warehouse = sale_order.warehouse_id
			journal = sale_order.journal_id
			if not warehouse:
				raise UserError("Debe seleccionar un almacén en la orden de venta para continuar.")
			if not journal:
				raise UserError("Debe seleccionar una serie en la orden de venta para continuar.")
			# [ Validar cliente ]
			partner = sale_order.partner_invoice_id
			document_type = partner.l10n_latam_identification_type_id.l10n_pe_vat_code
			identification_number = (partner.vat or "").strip()
			if not document_type:
				raise UserError("El tipo de documento del cliente es obligatorio.")
			if not identification_number:
				raise UserError("El numero de identificación del cliente es obligatorio.")
			if document_type == "6":
				# [ SERIE FACTURA ]
				if journal.invoice_type_code != "01":
					raise UserError(f"La serie {journal.name} no es una serie válida para el tipo de comprobante Factura.")
				# [ RUC ]
				if not patron_ruc.match(identification_number):
					raise UserError("Para emitir una Factura, la dirección de Facturación debe tener el tipo de documento RUC y su valor debe ser válido")

				sale_order.tipo_documento = "01"
			elif document_type in ["-", "0", "1", "4", "7"]:
				# [ SERIE BOLETA ]
				if journal.invoice_type_code != "03":
					raise UserError(f"La serie {journal.name} no es una serie válida para el tipo de comprobante Boleta.")
				# [ DNI ]
				if document_type == "1":
					if not patron_dni.match(sale_order.partner_invoice_id.vat or ""):
						raise UserError("El número de DNI del cliente no tiene un formato válido.")
				# [ CE, PASAPORTE ]
				elif document_type in ["4", "7"]:
					if not identification_number:
						raise UserError("Debe ingresar el número de documento del cliente (CE o Pasaporte).")
				
				sale_order.tipo_documento = "03"
			else:
				raise UserError("El tipo de documento del cliente no está soportado para emisión de comprobantes.")
			
		
		return super(SaleAdvancePaymentInv,self).create_invoices()