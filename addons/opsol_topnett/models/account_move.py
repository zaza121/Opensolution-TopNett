# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = 'account.move'

    num_affaire = fields.Char(
        string='Num Affaire',
        related="sale_order_id.num_affaire",
        store=True
    )

    libelle_affaire = fields.Char(
        string='Libellé Affaire',
        related="sale_order_id.libelle_affaire",
        store=True
    )

    date_move_sent = fields.Datetime(
        string="Date d'envoi"
    )

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        domain = args
        template_folder_id = self.env.context.get('project_documents_template_folder')
        domain = expression.OR([domain,[('num_affaire', 'ilike', self)]])
        domain = expression.OR([domain,[('libelle_affaire', 'ilike', self)]])
        return super()._name_search(name, domain, operator, limit, name_get_uid)

    @api.constrains('is_move_sent')
    def get_date_sent_invoice(self):
        for rec in self:
            date = None
            if rec.is_move_sent:
                date = fields.Datetime.now()
            rec.date_move_sent = date
