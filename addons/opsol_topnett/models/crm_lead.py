# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    num_affaire = fields.Char(string='Numero affaire')
    libelle_affaire = fields.Char(string='Libelle affaire')
    name = fields.Char(
        compute="_compute_custom_name",
        store=True,
        precompute=True
    )
    order_count = fields.Integer(
        string="Nombre de devis valides",
        compute='_compute_sale_data'
    )
    order_count_toshow = fields.Char(
        string="Nombre de devis valides affiches",
        compute='_compute_sale_data'
    )
    amount_mission = fields.Monetary(
        string="Montant Marche",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_untaxed_residual = fields.Monetary(
        string="Montant Restant dû",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_invoiced = fields.Monetary(
        string="Montant Facturé",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    mission_progress = fields.Monetary(
        string="Avanc. Marche",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_progress_percent = fields.Monetary(
        string="Avanc. Marche %",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_paid = fields.Monetary(
        string="Total payé",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_not_paid = fields.Monetary(
        string="Reste à payer",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )
    amount_not_invoiced = fields.Monetary(
        string="Reste à payer",
        compute="compute_amount_mission",
        currency_field='company_currency',
        readonly=True
    )

    def compute_amount_mission(self):
        for rec in self:
            confirmed_order = rec.order_ids.filtered(lambda x: x.state == 'sale')
            amount_untaxed = sum(confirmed_order.mapped('amount_untaxed'))
            amount_residual = sum(confirmed_order.mapped('invoice_ids.amount_residual'))
            amount_total_inv = sum(confirmed_order.mapped('invoice_ids.amount_total'))
            amount_invoiced = sum(confirmed_order.mapped('invoice_ids.amount_untaxed'))
            amount_percent = amount_total_inv and amount_residual / amount_total_inv or 0
            amount_paid = amount_invoiced * (1 - amount_percent)
            amount_not_paid = amount_invoiced - amount_paid
            amount_not_invoiced = amount_untaxed - amount_invoiced
            amount_untaxed_residual = amount_percent * amount_invoiced
            amount_progress = sum(confirmed_order.mapped(
                'order_line').mapped(
                lambda x: x.qty_invoiced / x.product_uom_qty * x.price_subtotal if x.product_uom_qty > 0 else 0))
            amount_progress_percent = amount_untaxed and amount_progress / amount_untaxed or 0
            rec.update({
                'amount_mission': amount_untaxed, 'mission_progress': amount_progress, 'amount_untaxed_residual': amount_untaxed_residual,
                'amount_progress_percent': amount_progress_percent, 'amount_invoiced': amount_invoiced, 'amount_not_paid': amount_not_paid,
                'amount_paid': amount_paid, 'amount_not_invoiced': amount_not_invoiced})

    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_sale_data(self):
        res = super(CrmLead, self)._compute_sale_data()
        for lead in self:
            order_count = len(lead.order_ids.filtered(lambda x: x.state == 'sale'))
            lead.order_count = order_count
            lead.order_count_toshow = _("%d devis valides", order_count)
        return res

    @api.depends("num_affaire", "libelle_affaire")
    def _compute_custom_name(self):
        for rec in self:
            value = ""
            if rec.num_affaire or rec.libelle_affaire:
                separator = "-" if rec.libelle_affaire else ""
                value = f"{rec.num_affaire} {separator} {rec.libelle_affaire}"
            rec.name = value
