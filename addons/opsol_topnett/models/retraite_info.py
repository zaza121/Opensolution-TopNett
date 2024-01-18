# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command

from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class RetraiteInfo(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = "opsol_topnett.retraite_info"
    _description = "Information Retraite"
    _rec_name = 'code'

    code = fields.Char(string='Code')
    matricule = fields.Char(string='Matricule')
    retra_comp_a = fields.Float(string='Retraite complementaire A')
    retra_comp_b = fields.Float(string='Retraite complementaire B')
    date_salaire = fields.Date(string='Date du salaire')
    employee_id = fields.Many2one(
        comodel_name='hr.employee', 
        string='Employe',
        compute="compute_employee",
        tracking=True,
    )
    active = fields.Boolean(string='Active', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['code'] = self.env['ir.sequence'].next_by_code(
                'opsol_topnett.retrai_inf_seq') or _("New")

        return super().create(vals_list)

    @api.depends('matricule')
    def compute_employee(self):
        emp_obj = self.env["hr.employee"]
        for rec in self:
            rec.employee_id = emp_obj.search([('numero', '=', rec.matricule)], limit=1)
