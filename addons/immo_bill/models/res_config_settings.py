# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rg_enable = fields.Boolean(
        string="Activer Retenue de gestion",
        config_parameter='immo_bill.param_rg_enable',
    )
    rg_sale_mode = fields.Selection(
        string="Retenue de gestion Mode",
        selection=[('ht', 'Hors taxe'), ('ttc', 'TTC')],
        config_parameter='immo_bill.param_rg_sale_mode',
    )
