# -*- coding: utf-8 -*-
from odoo import fields,models,api,_
from odoo.exceptions import UserError,ValidationError
from ..parameters.catalogs import tdc
import re
import logging
_logger = logging.getLogger(__name__)

class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _selection_invoice_type(self):
        return tdc

    submission_type = fields.Selection(selection=[("0","0 - Pruebas"), ("1","1 - Producción")], default="0")
    send_async = fields.Boolean(string="Envío asíncrono", default=False)
    electronic_invoice = fields.Boolean(string="Documento de emisión electrónica", default=False)
    #jnq_move_ids = fields.One2many("account.move", "journal_id")
    jnq_sequence_number = fields.Integer(string="Siguiente número", default=1)
    #jnq_edit_sequence = fields.Boolean(compute="_compute_edit_sequence_number")
    invoice_type_code = fields.Selection(string="Tipo de Documento", selection=_selection_invoice_type)
    tipo_comprobante_a_rectificar = fields.Selection(selection=[("00","Otros"), ("01","Factura"), ("03","Boleta")])
    # [ Detracciones ]
    detraction = fields.Boolean(string="Detraccion", default=False)
    
    #Sobreescritura para crear diario con campo usa documentos en False
    @api.onchange('company_id', 'type')
    def _onchange_company(self):
        self.l10n_latam_use_documents = self.type in ['sale'] and self.l10n_latam_company_use_documents

    # @api.depends('jnq_move_ids')
    # def _compute_edit_sequence_number(self):
    #     for record in self:
    #         record.jnq_edit_sequence = bool(record.jnq_move_ids)

    @api.onchange("invoice_type_code", "submission_type", "code")
    def onchange_name(self):
        d = {
            "01":"Factura de venta",
            "03":"Boleta de venta",
            "07":"Nota de crédito",
            "08":"Nota de débito",
            "09":"Guía de Remisión - Remitente",
            "31":"Guía de Remisión - Transportista",
            "20":"Retención","40":"Percepción"
        }
        if self.invoice_type_code in ["01","03","07","08","09","31","20","40"] and self.electronic_invoice:
            self.name = "{} {}{}".format(d[self.invoice_type_code],self.code or "*"," [test]" if self.submission_type == "0" else "")
        
    @api.constrains("jnq_sequence_number")
    def _check_jnq_sequence_number(self):
        for record in self:
            if record.jnq_sequence_number <= 0:
                raise ValidationError("Valor de secuencia inválido, debe ser mayor a 0.")
    
    @api.constrains("code")
    def _check_journal_code(self):
        for record in self:
            if record.electronic_invoice and record.type == "sale":

                prefix_codes = self.env['account.journal'].search([
                    ('electronic_invoice','=',True),
                    ('type', '=', 'sale'),
                    ('active', '=', True),
                    ('id', '!=', record.id),
                    ('invoice_type_code', '=', record.invoice_type_code)
                ])
                if record.code in prefix_codes.mapped('code'):
                    raise ValidationError("Error: La serie debe ser único por tipo de documento.")
                
                code = record.code or ""
                type_code = record.invoice_type_code

                if code and type_code in ["07","08"]:
                    if re.match(r"^B\w{3}$", code) and record.tipo_comprobante_a_rectificar == "03":
                        return 
                    if re.match(r"^F\w{3}$", code) and record.tipo_comprobante_a_rectificar == "01":
                        return 
                    raise ValidationError("Error: El campo 'Serie' o 'Comprobante a rectificar' son incorrectos.")
                if re.match(r"^B\w{3}$", code) and type_code == "03":
                    return
                if re.match(r"^F\w{3}$", code) and type_code == "01":
                    return
                if re.match(r"^T[A-Z0-9]{3}$", code) and type_code == "09":
                    return
                if re.match(r"^V[A-Z0-9]{3}$", code) and type_code == "31":
                    return
                if re.match(r"^R\w{3}$", code) and type_code == "20":
                    return
                if re.match(r"^P\w{3}$", code) and type_code == "40":
                    return
                raise ValidationError("Error: El campo 'Serie' o el 'Tipo de comprobante' son incorrectos.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", False):
                vals["code"] = vals.get("code").upper()
        result = super(AccountJournal, self).create(vals_list)
        return result

    @api.depends('type', 'l10n_latam_use_documents', 'electronic_invoice')
    def _compute_refund_sequence(self):
        super()._compute_refund_sequence()
        for journal in self:
            if journal.l10n_latam_use_documents or journal.electronic_invoice:
                journal.refund_sequence = False
    
    @api.depends('type', 'l10n_latam_use_documents', 'electronic_invoice')
    def _compute_debit_sequence(self):
        super()._compute_debit_sequence()
        for journal in self:
            if journal.l10n_latam_use_documents or journal.electronic_invoice:
                journal.debit_sequence = False

    def action_create_new(self):
        res = super(AccountJournal,self).action_create_new()
        context = res.get("context",{})
        if self.type in ["sale","purchase"]:
            context.update({"default_journal_type":self.type,"default_invoice_type_code":self.invoice_type_code})
        
        res.update({"context":context})

        return res