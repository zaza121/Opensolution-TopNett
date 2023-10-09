# -*- coding: utf-8 -*-

import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_compare, float_round


_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def get_rg(self):
        order = self.order_id
        immo_or_avenant = order.immo_bill_ids or order.immo_invoice_ids
        return order.retenue_percent or sum(immo_or_avenant.mapped('retenue_percent'))

    def _prepare_invoice_line(self, **optional_values):

        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        infos = self._context.get("infos", False)
        if infos:
            if self.id in infos.keys():
                new_qty = infos[self.id]
                _qty = self.product_uom_qty
                res['initial_quantity'] = _qty
                res['quantity'] = float_round(new_qty, precision_digits=precision)

        retenue_rg = self.get_rg()
        no_retenue = self._context.get("no_retenue", False)


        if retenue_rg > 0 and not no_retenue:

            # if quantity product is zero it is sometimes a down payment
            if self.product_uom_qty == 0:
                if res['quantity'] > 0: # quantity is greater than 0 on the down payment invoice
                    res['quantity'] = res['quantity'] * (1 - retenue_rg)
            else:
                # check the condition
                remain_progress = 1 - (self.qty_invoiced + res['quantity']) / self.product_uom_qty
                today = fields.Date.today()

                if infos:
                    res['quantity'] = res['quantity'] * (1 - retenue_rg)
                else:
                    if self.qty_invoiced == 0 or self.qty_invoiced > 0 and remain_progress > retenue_rg:
                        res['quantity'] = res['quantity'] * (1 - retenue_rg)
                    elif self.order_id.rg_date_expiration and today < self.order_id.rg_date_expiration:
                        raise UserError(_("La facture de retenue ne peut pas etre genere avant le %s", self.order_id.rg_date_expiration))

        return res
