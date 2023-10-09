from odoo import api, fields, models, _


class AccountInvoiceSend(models.TransientModel):
    _inherit = 'account.invoice.send'

    email_cc = fields.Char(
        related="template_id.email_cc",
        readonly=True
    )
