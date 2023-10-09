# -*- coding: utf-8 -*-

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.fields import Command


class UpdateSitutationWizard(models.TransientModel):

    _name = 'immo_bill.update_situtaion_wiz'
    _description = "Update situation wizard"

    situation_progress = fields.Float(
        string='Progress',
        default=0
    )
    final_progress = fields.Float(
        string='Final situation progress',
        compute="_compute_final_progress",
        readonly=True
    )
    situation_order = fields.Integer(string='Order situation')
    date_confirmation = fields.Date(
        string='Date confirmation',
        default=fields.Date.today
    )
    amount = fields.Float(
        string='Amount',
        compute="_compute_final_progress",
        readonly=True
    )
    initial_amount = fields.Float(
        string='Initial amount',
    )
    immo_bill_id = fields.Many2one(
        comodel_name='immo_bill.invoice',
        string='Immo bill',
    )

    @api.depends('immo_bill_id', 'situation_progress', 'initial_amount')
    def _compute_final_progress(self):
        self.ensure_one()
        value = self.immo_bill_id.current_progress + self.situation_progress
        list_order = self.immo_bill_id.situation_ids.mapped('situation_order')
        last_order = max(list_order) if list_order else 0
        current_amount = self.situation_progress * self.initial_amount
        self.final_progress = value
        self.amount = current_amount
        self.situation_order = last_order + 1

    def action_update(self):
        self.ensure_one()

        # create the invoice
        # invoice = self.env['account.move'].sudo().create(
        #     self.get_invoice_values()).with_user(self.env.uid)
        invoice = self.env['account.move'].sudo().create(
            self.get_invoice_values()).with_user(self.env.uid)  # Unsudo the invoice after creation
        # invoice = self.immo_bill_id.sale_order_id.sudo()_create_invoices().with_user(self.env.uid)  # Unsudo the invoice after creation
        situation_value = {
            'immo_bill_id': self.immo_bill_id.id,
            'situation_progress': self.situation_progress,
            'situation_order': self.situation_order,
            'date_confirmation': self.date_confirmation,
        }
        situation = self.env["immo_bill.situation"].create(situation_value)
        invoice.situation_id = situation
        return {'type': 'ir.actions.act_window_close'}

    def get_invoice_values(self):
        order = self.immo_bill_id.sale_order_id

        immo_context = {
            'immo_percent': self.situation_progress,
            'previous_advance': self.final_progress - self.situation_progress
        }

        invoice_vals_list = []
        invoice_vals = order.with_context(immo_context)._prepare_invoice()
        invoiceable_lines = order._get_invoiceable_lines()

        invoice_line_vals = []
        down_payment_section_added = False
        invoice_item_sequence = 0

        for line in invoiceable_lines:
            invoice_line_vals.append(
                Command.create(
                    line.with_context(
                        immo_context)._prepare_invoice_line(
                        sequence=invoice_item_sequence)
                ),
            )
            invoice_item_sequence += 1

        invoice_vals['invoice_line_ids'] += invoice_line_vals
        invoice_vals['immo_inv_id'] = self.immo_bill_id.id
        invoice_vals_list.append(invoice_vals)

        values = {**order._prepare_invoice()}
        return invoice_vals_list
