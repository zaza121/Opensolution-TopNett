# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    name = fields.Char(
        compute="_compute_name",
        inverse="inverse_compute_name"
    )
    nom = fields.Char(string='Nom')
    prenom = fields.Char(string='Prenom')
    numero = fields.Integer(string='Numero')

    @api.depends("nom", "prenom")
    def _compute_name(self):
        for res in self:
            rec.name = f"{rec.nom} {rec.prenom}"

    @api.onchange('name')
    def inverse_compute_name(self):
        for rec in self:
            values = rec.name and rec.name.split(" ") or []
            if len(values) > 1:
                rec.nom = values[0]
                rec.prenom = ' '.join(values[1:])
            else:
                rec.nom = rec.name
                rec.prenom = ""
