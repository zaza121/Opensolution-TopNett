# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    nom = fields.Char(string='Nom')
    prenom = fields.Char(string='Prenom')
    numero = fields.Integer(string='Numero')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'nom' in vals.keys() or 'prenom' in vals.keys():
                vals['name'] = f"{vals.get('nom', '')} {vals.get('prenom', '')}"

        return super().create(vals_list)

    @api.constrains("nom", "prenom")
    def force_name(self):
        for rec in self:
            rec.name = f"{rec.nom or ''} {rec.prenom or ''}"
