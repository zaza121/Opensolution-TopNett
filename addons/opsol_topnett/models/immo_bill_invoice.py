# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression


class ImmoBillInvoice(models.Model):
    _inherit = 'immo_bill.invoice'

    nom_chantier = fields.Char(
        string='Nom Chantier',
        compute="compute_nom_chantier",
        store=True
    )

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('nom_chantier', 'ilike', name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    @api.depends('sale_order_id.nom_devis')
    def compute_nom_chantier(self):
        for rec in self:
            num_affaire = rec.sale_order_id.nom_devis.split("-") if rec.sale_order_id else ""
            _name = num_affaire[0] if len(num_affaire) > 1 else ""
            rec.nom_chantier = _name

    def name_get(self):
        result = []
        for inv in self:
            name = inv.nom_chantier if inv.nom_chantier else inv.name
            result.append((inv.id, name))
        return result
