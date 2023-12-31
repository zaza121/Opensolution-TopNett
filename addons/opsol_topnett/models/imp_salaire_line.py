# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command

from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class ImpSalaireLine(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = "opsol_topnett.imp_salaire_line"
    _description = "Importation de salaire"
    _rec_name = 'code'

    code = fields.Char(string='Code')
    matricule_sex = fields.Char(string='Genre')
    matricule = fields.Char(string='Matricule')
    salaire_brut = fields.Float(string='Salaire Brut')
    h_travailles = fields.Float(string='Heures travailes')
    h_complementaires = fields.Float(string='Heures Complementaires')
    h_supplementaires = fields.Float(string='Heures supplementaires')
    c_maladie = fields.Float(string='Conge Maladie')
    c_at = fields.Float(string='Conge AT')
    c_maternite = fields.Float(string='Conge Maternite')
    c_payes = fields.Float(string='Conge Payes')
    c_autres = fields.Float(string='Autres Absences')
    date_entree1 = fields.Date(string='Date entree 1')
    date_entree2 = fields.Date(string='Date entree 2')
    maintien = fields.Float(string='Maintien')
    prime = fields.Float(string='Prime')
    date_salaire = fields.Date(string='Date du salaire')
    employee_id = fields.Many2one(
        comodel_name='hr.employee', 
        string='Employe',
        compute="compute_employee",
        tracking=True,
    )
    bulletin_id = fields.Many2one(
        comodel_name='hr.payslip',
        string='Bulletin de paie',
        tracking=True,
    )
    lot_id = fields.Many2one(
        comodel_name='hr.payslip.run',
        string='Lot de bulletin',
        related="bulletin_id.payslip_run_id",
        store=True
    )
    nombre_conges = fields.Integer(
        string='Nombre de conges',
        compute="_compute_nombres_conges"
    )
    conges_ids = fields.One2many(
        comodel_name='opsol_topnett.imp_conge',
        string='Conges lies',
        compute="_compute_nombres_conges"
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
                'opsol_topnett.imp_sal_seq') or _("New")

        return super().create(vals_list)

    @api.depends('matricule')
    def compute_employee(self):
        emp_obj = self.env["hr.employee"]
        for rec in self:
            rec.employee_id = emp_obj.search([('registration_number', '=', rec.matricule)], limit=1)

    def open_conges(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('opsol_topnett.action_opsol_topnett_imp_conge')
        if action:
            action['domain'] = [('id', 'in', self.conges_ids.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _compute_nombres_conges(self):
        imp_conge_obj = self.env["opsol_topnett.imp_conge"]
        for rec in self:
            if rec.date_salaire and rec.employee_id:
                first_day_month = rec.date_salaire.replace(day=1)
                last_day_month = first_day_month + relativedelta(months=1) - relativedelta(days=1)
                result = imp_conge_obj.search([
                    ('date_start', '>=', first_day_month),
                    ('date_end', '<=', last_day_month),
                    ('matricule', '=', rec.employee_id.numero)
                ])
                rec.update({'nombre_conges': len(result), 'conges_ids': [Command.set(result.ids)]})
            else:
                rec.update({'nombre_conges': 0, 'conges_ids': [Command.set([])]})

    def generate_payslip(self):
        payslip_obj = self.env["hr.payslip"]
        structure_id = self.env["hr.payroll.structure"].search([], limit=1)
        for rec in self:

            skip_error = self.env.context.get('skip_error', False)

            if rec.bulletin_id:
                continue

            if not rec.employee_id:
                if skip_error:
                    continue
                raise UserError(_("Pas d employe trouve avec le matricule %s", rec.matricule))

            if not rec.date_salaire:
                if skip_error:
                    continue
                raise UserError(_("veuillez renseigner la date de salaire pour le matricule %s", rec.matricule))

            if not structure_id:
                if skip_error:
                    continue
                raise UserError(_("Aucune structure salariale trouvee"))

            values = {'name': f"Bulletin {rec.matricule}: {rec.date_salaire}", 'employee_id': rec.employee_id.id}
            first_day_month = rec.date_salaire.replace(day=1)
            last_day_month = first_day_month + relativedelta(months=1) - relativedelta(days=1)
            contract = rec.get_current_contract(first_day_month, last_day_month)
            struct = contract.structure_type_id or structure_id
            lot_bulletin = rec.payslip_lot(first_day_month, last_day_month)
            values.update({
                'payslip_run_id': lot_bulletin.id,
                'date_from': first_day_month,
                'date_to': last_day_month,
                'contract_id': contract.id,
                'struct_id': struct.id
            })
            rec.bulletin_id = payslip_obj.create(values)

    @api.model
    def get_current_contract(self, date_from, date_to):
        contract = self.env['hr.contract'].search([
            ('company_id', '=', self.company_id.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', '!=', 'cancel'),
            ('date_start', '<=', date_to),
            '|',
            ('date_end', '>=', date_from),
            ('date_end', '=', False)], limit=1)
        if contract:
            contract.update({'date_start': self.date_entree2 or self.date_entree1 or date_from})
            return contract
        else:
            return self.env["hr.contract"].create({
                'name': f"Contrat pour {self.employee_id.name}",
                'employee_id': self.employee_id.id,
                'date_start': self.date_entree2 or self.date_entree1 or date_from,
                'resource_calendar_id': self.env.company.resource_calendar_id.id,
                'wage': 0
            })

    @api.model
    def payslip_lot(self, date_from, date_to):
        lot_id = self.env['hr.payslip.run'].search([
            ('date_start', '<=', date_to),
            ('date_end', '>=', date_from)], limit=1)
        if lot_id:
            return lot_id
        else:
            return self.env["hr.payslip.run"].create({
                'name': f"Lot salaire {date_from.month} / {date_to.year}",
                'date_start': date_from, 'date_end': date_to
            })

    @api.model
    def get_input_values(self, structure=None):
        R_INP_GROSS = self.env['hr.payslip.input.type'].search([('code', '=', 'INP_GROSS')], limit=1)
        inputs_values = []

        if not R_INP_GROSS:
            raise UserError("Veuillez creer un input type pour le salaire de base")
        v_command = Command.create({
            'input_type_id': R_INP_GROSS.id,
            'name': "Salaire de base",
            'amount': self.salaire_brut
        })
        inputs_values.append(v_command)

        if structure:
            other_inputs = structure.input_line_type_ids
            # insert in input
            inputs_values.extend(
                [Command.create({'input_type_id': elt.id, 'name': elt.code, 'amount': elt.amount}) for elt in other_inputs])
        return inputs_values
