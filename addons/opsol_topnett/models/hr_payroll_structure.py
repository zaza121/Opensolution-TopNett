# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    rate_ccss = fields.Float(string='Taux Employe CCSS')
    rate_ccss_comp = fields.Float(string='Taux Employeur CCSS')
    rate_car = fields.Float(string='Taux Employe CAR')
    rate_car_comp = fields.Float(string='Taux Employeur CAR')
    rate_uned = fields.Float(string='Taux Employe UNEDIC')
    rate_uned_comp = fields.Float(string='Taux Employeur UNEDIC')
