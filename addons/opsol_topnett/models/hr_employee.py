# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    nom = fields.Char(string='Nom')
    prenom = fields.Char(string='Prenom')
    numero = fields.Integer(string='Numero')
    affiliation_ac = fields.Boolean(string='Affiliation AC', default=True)
    affiliation_rc = fields.Boolean(string='Affiliation RC', default=True)
    affiliation_car = fields.Boolean(string='Affiliation CAR', default=True)
    teletravail = fields.Boolean(string='Teletravail ?', default=False)
    administrateur_salarie = fields.Boolean(string='Administrateur Salarie ?', default=False)

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
