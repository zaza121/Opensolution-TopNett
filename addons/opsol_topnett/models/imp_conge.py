# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command

from dateutil.relativedelta import relativedelta


class ImpConge(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = "opsol_topnett.imp_conge"
    _description = "Importation Conge"
    _rec_name = 'code'

    code = fields.Char(string='Code')
    code_conge = fields.Char(string='Code conges', required=True)
    matricule = fields.Integer(string='Numero', required=True)
    date_start = fields.Date(string='Date de debut', required=True)
    date_end = fields.Date(string='Date de fin', required=True)
    nb_heures = fields.Float(string='Nombres d\'heures')
    nb_jours = fields.Float(string='Nombres de jours')
    employee_id = fields.Many2one(
        comodel_name='hr.employee', 
        string='Employe',
        compute="compute_employee"
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', required=True,
        store=True, readonly=False, default=lambda self: self.env.company,
    )
    active = fields.Boolean(string='Active', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['code'] = self.env['ir.sequence'].next_by_code(
                'opsol_topnett.imp_conge_seq') or _("New")

        return super().create(vals_list)

    def get_conge_data(self, date_format):
        return {
            'date_start' : self.date_start and self.date_start.strftime(date_format) or "",
            'date_end' : self.date_end and self.date_end.strftime(date_format) or "",
            'nb_heures': f"{self.nb_heures}"
        }

    @api.depends('matricule')
    def compute_employee(self):
        emp_obj = self.env["hr.employee"]
        for rec in self:
            rec.employee_id = emp_obj.search([('numero', '=', rec.matricule)], limit=1)
