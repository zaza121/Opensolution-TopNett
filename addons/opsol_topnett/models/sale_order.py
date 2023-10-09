# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    num_affaire = fields.Char(
        string='Numero affaire',
        related="opportunity_id.num_affaire",
        store=True
    )

    libelle_affaire = fields.Char(
        string='Libelle affaire',
        related="opportunity_id.libelle_affaire",
        store=True
    )

    num_devis = fields.Integer(
        string='Numero devis',
        compute="_compute_num_devis",
        store=True
    )

    nom_devis = fields.Char(
        string='Nom devis',
        compute="_compute_num_devis",
        store=True
    )

    state = fields.Selection(
        selection=[
            ('draft', "Devis"),
            ('sent', "Devis envoyé"),
            ('sale', "Devis validé"),
            ('done', "Bloqué"),
            ('cancel', "Annulé"),
        ],
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='draft')

    # localisation = fields.Selection(
    #     selection=[('france', "France"),('monaco', "Monaco")],
    #     string="Localisation",
    #     default='france'
    # )

    def name_get(self):
        result = []
        for order in self:
            name = order.nom_devis if order.nom_devis else order.name
            result.append((order.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|', ('nom_devis', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name), ('num_affaire', 'ilike', name), ('libelle_affaire', 'ilike', name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    @api.depends('opportunity_id', 'state')
    def _compute_num_devis(self):
        for rec in self:

            if rec.state not in ['sent', 'sale', 'done', 'cancel'] :
                _num_devis = 0
                _nom_devis = f"{rec.num_affaire or ''}-PH"
                if rec.num_affaire and rec.opportunity_id:
                    nums_devis = self.search([
                        ('opportunity_id', '=', self.opportunity_id.id),]).mapped('num_devis')
                    next_num_devis =max(nums_devis) + 1 if len(nums_devis) > 0 else 1
                    _num_devis = next_num_devis
                    _nom_devis = f"{rec.num_affaire}-PH-{_num_devis}"
                
                rec.num_devis = _num_devis
                rec.nom_devis = _nom_devis
