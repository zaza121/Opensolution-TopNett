from odoo import models, fields, api

from functools import lru_cache


class ReportInvoiceWithPayment(models.AbstractModel):
    _inherit = 'report.account.report_invoice'
    _description = 'Account report with payment lines'
    _name = 'report.immo_bill.report_invoice_situation'

    @api.model
    def _get_report_values(self, docids, data=None):
        rslt = super()._get_report_values(docids, data)
        rslt['report_type'] = data.get('report_type') if data else ''
        return rslt
