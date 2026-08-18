from odoo import api, fields, models


class Users(models.Model):
	_inherit = 'res.users'

	names = fields.Char(string='Nombres')
	fathers_last_name = fields.Char(string='Apellido Paterno')
	mothers_last_name = fields.Char(string='Apellido Materno')

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('partner_id'):
				partner = self.env['res.partner'].browse(vals['partner_id'])
				if partner:
					if partner.company_type == 'person':
						if not vals.get('names'):
							vals['names'] = partner.names
						if not vals.get('fathers_last_name'):
							vals['fathers_last_name'] = partner.fathers_last_name
						if not vals.get('mothers_last_name'):
							vals['mothers_last_name'] = partner.mothers_last_name
					elif partner.company_type == 'company':
						if not vals.get('names'):
							vals['names'] = partner.name

			full_name = None
			if any(k in vals for k in (
				'names',
				'fathers_last_name',
				'mothers_last_name',
			)):
				full_name = " ".join(filter(None, [
					vals.get('names'),
					vals.get('fathers_last_name'),
					vals.get('mothers_last_name'),
				]))
				if full_name:
					vals['name'] = full_name

			if not vals.get('partner_id'):
				partner_vals = {
					'company_type': 'person',
					'name': full_name or vals.get('name') or "",
					'names': vals.get('names'),
					'fathers_last_name': vals.get('fathers_last_name'),
					'mothers_last_name': vals.get('mothers_last_name'),
				}
				partner = self.env['res.partner'].create(partner_vals)
				vals['partner_id'] = partner.id

		return super().create(vals_list)

	def write(self, vals):
		if self.env.context.get('skip_partner_sync'):
			return super().write(vals)

		recompute = any(k in vals for k in (
			'names',
			'fathers_last_name',
			'mothers_last_name',
		))

		if not recompute: 
			return super().write(vals)

		for user in self:
			user_vals = dict(vals)

			full_name = " ".join(filter(None, [
				user_vals.get('names', user.names),
				user_vals.get('fathers_last_name', user.fathers_last_name),
				user_vals.get('mothers_last_name', user.mothers_last_name),
			]))

			if user.partner_id:
				partner_vals = {}
				if user.partner_id.company_type == 'person':
					partner_vals = {
						'names': vals.get('names', user.names),
						'fathers_last_name': vals.get('fathers_last_name', user.fathers_last_name),
						'mothers_last_name': vals.get('mothers_last_name', user.mothers_last_name),
					}
					if full_name:
						partner_vals['name'] = full_name
				elif user.partner_id.company_type == 'company':
					if full_name:
						partner_vals['name'] = full_name
							
				if partner_vals:
					user.partner_id.sudo().with_context(skip_user_sync=True).write(partner_vals)

			if full_name and 'name' not in user_vals:
				user_vals['name'] = full_name

			super(Users, user).write(user_vals)
		return True
