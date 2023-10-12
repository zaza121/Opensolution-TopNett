# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    amount = fields.Float(string='Montant', default=0)
