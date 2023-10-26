# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


class HrContract(models.Model):
    _inherit = "hr.contract"

    date_start_2 = fields.Date(string='Date entree 2')
    date_sortie = fields.Date(string='Date de sortie')
    date_depart_administratif = fields.Date(string='Date de depart administratif')
    date_depart_physique = fields.Date(string='Date de depart physique')
    date_depart_preavis = fields.Date(string='Date de debut preavis')
    date_fin_preavis = fields.Date(string='Date de fin preavis')
    hr_responsible_id = fields.Many2one(default=lambda self: self._get_hr_responsible_domain_default())

    def _get_hr_responsible_domain_default(self):
        group = self.env.ref('hr.group_hr_user')
        return self.env["res.users"].search([
            ('share', '=', False), ('groups_id', 'in', [group and group.id or None])], limit=1)
