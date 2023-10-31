# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    code_employeur = fields.Char(string='Code Employeur')
