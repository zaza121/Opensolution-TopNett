# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    rib_image = fields.Image(
        string="Rib Image",
        max_width=256,
        max_height=256
    )
    signature = fields.Image(
        string="Signature email",
        max_width=256,
        max_height=256,
        store=True, attachment=False
    )
    signature_text = fields.Text(
        string="Signature text",
    )
