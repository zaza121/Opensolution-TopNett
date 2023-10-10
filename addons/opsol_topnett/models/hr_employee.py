# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    nom = fields.Char(string='Nom')
    prenom = fields.Char(string='Prenom')
    numero = fields.Integer(string='Numero')

    @api.constrains("nom", "prenom")
    def force_name(self):
        for rec in self:
            rec.name = f"{rec.nom} {rec.prenom}"
