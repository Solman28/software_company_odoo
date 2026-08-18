from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    names = fields.Char(string='Nombres')
    fathers_last_name = fields.Char(string='Apellido Paterno')
    mothers_last_name = fields.Char(string='Apellido Materno')
    
    @api.onchange('company_type')
    def onchange_company_type(self):
        for record in self:
            record.is_company = (record.company_type == 'company')
            if record.company_type == 'company':
                record.names = False
                record.fathers_last_name = False
                record.mothers_last_name = False
                record.l10n_latam_identification_type_id = False
                record.vat = False
        
    def _get_full_name(self, vals=None):
        self.ensure_one()
        vals = vals or {}

        return " ".join(filter(None, [
            vals.get('names', self.names),
            vals.get('fathers_last_name', self.fathers_last_name),
            vals.get('mothers_last_name', self.mothers_last_name),
        ]))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('company_type') == 'person':
                full_name = " ".join(filter(None, [
                    vals.get('names'),
                    vals.get('fathers_last_name'),
                    vals.get('mothers_last_name'),
                ]))
                if full_name and not vals.get('name'):
                    vals['name'] = full_name

        partner = super().create(vals_list)
        return partner
    
    def write(self, vals):
        if self.env.context.get('skip_user_sync'):
            return super().write(vals)
        
        recompute = any(k in vals for k in (
			'names',
			'fathers_last_name',
			'mothers_last_name',
		))

        if not recompute: 
            return super().write(vals)
        
        vals = dict(vals)

        for partner in self:
            partner_vals = dict(vals)
            # Solo personas
            if partner.company_type == 'person':
                full_name = partner._get_full_name(partner_vals)
                if full_name:
                    partner_vals['name'] = full_name
            
            super(ResPartner, partner).write(partner_vals)

            # Sincronizar hacia res.users
            for user in partner.user_ids:
                update_vals = {}
                for field in ('names', 'fathers_last_name', 'mothers_last_name'):
                    if field in partner_vals:
                        update_vals[field] = partner_vals[field]

                if update_vals:
                    user.with_context(skip_partner_sync=True).write(update_vals)

        return True