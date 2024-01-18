# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    imp_sal_ids = fields.One2many(
        comodel_name='opsol_topnett.imp_salaire_line',
        inverse_name='bulletin_id',
        string='Importation Salaire',
    )
    retraite_info_ids = fields.One2many(
        comodel_name='opsol_topnett.retraite_info',
        string='Info retraire',
        compute="_compute_retraite_info_ids"
    )

    @api.depends('employee_id', 'contract_id', 'struct_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):

        super(HrPayslip, self)._compute_input_line_ids()

        for slip in self:
            if not slip.employee_id or not slip.struct_id:
                continue

            structure = slip.struct_id
            other_inputs = structure.input_line_type_ids
            oi_codes = other_inputs.mapped('code')
            inputs_values = []
            to_delete = slip.input_line_ids.filtered(lambda x: x.name in oi_codes)
            inputs_values.extend([Command.unlink(to_del.id) for to_del in to_delete])

            # insert in input
            inputs_values.extend(
                [Command.create({'input_type_id': elt.id, 'name': elt.code, 'amount': elt.amount}) for elt in other_inputs])
            slip.update({'input_line_ids': inputs_values})

    def _compute_retraite_info_ids(self):
        retraite_obj = self.env["opsol_topnett.retraite_info"]
        for rec in self:
            numero = rec.employee_id and rec.employee_id.numero or ""
            rec.retraite_info_ids = retraite_obj.search([
                ('date_salaire', '>=', rec.date_from),
                ('date_salaire', '<=', rec.date_to),
                ('matricule', '=', numero),
            ])
