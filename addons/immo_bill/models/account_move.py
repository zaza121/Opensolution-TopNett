# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools import formatLang


class AccountMove(models.Model):
    _inherit = 'account.move'

    immo_inv_id = fields.Many2one(
        comodel_name='immo_bill.invoice',
        string='Immo Invoice',
    )
    immo_percent = fields.Float(string='Immo percent')
    previous_advance = fields.Float(string='previous advance')
    situation_id = fields.Many2one(
        comodel_name='immo_bill.situation',
        string='Situation',
    )

    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Order',
        compute="_compute_sale_order_id",
    )
    amount_down_payment_novat = fields.Monetary(
        string="Acompte HT",
        compute='_compute_situation_amount_total',
        store=False, readonly=True,
    )
    invoice_line_ids_wo_downpay = fields.One2many(  # /!\ invoice_line_ids is just a subset of line_ids.
        'account.move.line',
        'move_id',
        string='Invoice lines',
        copy=False,
        readonly=True,
        domain=[('display_type', 'in', ('product', 'line_section', 'line_note')),('minus_down_payment', '=', False)],
        states={'draft': [('readonly', False)]},
    )
    simple_avancement = fields.Boolean(
        string='Avancement simplifie',
    )

    def _compute_sale_order_id(self):
        for rec in self:
            result = rec.invoice_line_ids.mapped('sale_line_ids.order_id')
            rec.sale_order_id = result[0] if result else None

    def _get_mail_template(self):
        """
        :return: the correct mail template based on the current move type
        """
        not_refund_model = "account.email_template_edi_invoice"
        if self.situation_id:
            not_refund_model = "immo_bill.email_template_immo_invoice"
        # raise Warning(not_refund_model)
        return (
            'account.email_template_edi_credit_note'
            if all(move.move_type == 'out_refund' for move in self)
            else not_refund_model
        )

    def action_invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        if any(not move.is_invoice(include_receipts=True) for move in self):
            raise UserError(_("Only invoices could be printed."))
        self.filtered(lambda inv: not inv.is_move_sent).write({'is_move_sent': True})

        if self.situation_id:
            return self.env.ref('immo_bill.situation_invoice_report_action').report_action(self)
        else:
            return super(AccountMove, self).action_invoice_print()

    def _compute_situation_amount_total(self):
        for rec in self:
            rec.amount_down_payment_novat = 0
            if rec.situation_id and rec.situation_id.amount_down_payment:
                rec.amount_down_payment_novat = -rec.situation_id.amount_down_payment_novat


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    situation_id = fields.Many2one(
        related="move_id.situation_id",
        comodel_name='immo_bill.situation',
        string='Situation'
    )

    immo_inv_id = fields.Many2one(
        related="move_id.immo_inv_id",
        comodel_name='immo_bill.invoice',
        string='Immo Invoice',
    )

    initial_quantity = fields.Float(
        string='Initial quantity',
        store=True,
        readonly=False,
        default=1
    )
    immo_percent = fields.Float(
        string='Immo percent',
        related="move_id.immo_percent",
        default=1
    )
    previous_advance = fields.Float(
        string='previous advance',
        related="move_id.previous_advance"
    )
    cumul_advance = fields.Float(
        string='cumul advance',
        compute="_compute_cumul_advance",
        store=True,
    )
    minus_down_payment = fields.Boolean(
        string='Recuperation acompte',
        default=False
    )

    @api.depends('product_id', 'price_unit', 'immo_percent')
    def _compute_cumul_advance(self):
        for rec in self:
            rec.cumul_advance = rec.previous_advance + rec.immo_percent
            new_qty = rec.initial_quantity * rec.immo_percent
            rec.quantity = new_qty if rec.immo_percent else rec.quantity
