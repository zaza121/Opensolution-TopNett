# -*- coding: utf-8 -*-

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    advance_payment_method = fields.Selection(
        selection_add=[('situation', 'Facture de situation')],
        ondelete={'situation': 'set default'}
    )

    #=== ACTION METHODS ===#

    def create_invoices(self):

        if self.advance_payment_method == 'situation':
            self._create_invoices(self.sale_order_ids)
            if self.env.context.get('open_invoices'):
                immo_bills = self.sale_order_ids.mapped("immo_bill_ids")
                if immo_bills:
                    return immo_bills[0].action_view_invoice()

            return {'type': 'ir.actions.act_window_close'}
        else:
            return super(SaleAdvancePaymentInv, self).create_invoices()

    def _create_invoices(self, sale_orders):

        if self.advance_payment_method == 'situation':
            self.sale_order_ids.ensure_one()
            self = self.with_company(self.company_id)
            order = self.sale_order_ids

            self.env['immo_bill.invoice'].create({
                'partner_id': order.partner_id.id,
                'sale_order_id': order.id
            })
            order._compute_invoice_status

            return order.action_view_immo_invoice()
        else:
            return super(SaleAdvancePaymentInv, self)._create_invoices(sale_orders)
