# -*- coding: utf-8 -*-

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.fields import Command


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    invoice_status = fields.Selection(
        selection_add=[('situation', 'Facture en situation')]
    )

    is_immo_bill = fields.Boolean(
        string='Generer facture de situation ?',
        default=True
    )
    immo_bill_ids = fields.One2many(
        comodel_name='immo_bill.invoice',
        inverse_name='sale_order_id',
        string='Immo invoice',
    )
    count_immo_inv = fields.Integer(
        string='Number of immo',
        compute="compute_count_immo_inv"
    )
    is_avenant = fields.Boolean(
        string='Avenant',
    )
    immo_invoice_ids = fields.Many2many(
        comodel_name='immo_bill.invoice',
        string='Chantiers',
        relation="invoice_to_saleorder"
    )
    count_avenants = fields.Integer(
        string='Number of immo',
        compute="compute_count_avenants",
        store=True
    )
    retenue_percent = fields.Float(string='% Retenue de garantie')
    rg_date_expiration = fields.Date(
        string='Date expiration retenue',
        compute="_compute_rg_date_expiration_",
        readonly=False,
        store=True
    )
    use_rg = fields.Boolean(
        string='use rg feature ?',
        # default=lambda self: self.get_rg_ingfo(),
        compute="_compute_use_rg",
        store=False
    )
    rg_sale_mode = fields.Selection(
        string="Retenue de gestion Mode",
        selection=[('ht', 'Hors taxe'), ('ttc', 'TTC')],
        # default=lambda self: self.get_rg_ingfo(),
        compute="_compute_use_rg",
        store=False
    )

    def _compute_use_rg(self):
        self.update({
            'use_rg': self.env['ir.config_parameter'].sudo().get_param('immo_bill.param_rg_enable'),
            'rg_sale_mode': self.env['ir.config_parameter'].sudo().get_param('immo_bill.param_rg_sale_mode')
        })

    def compute_count_immo_inv(self):
        for rec in self:
            rec.count_immo_inv = len(rec.immo_bill_ids)

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        immo_percent = self._context.get("immo_percent", False)
        previous_advance = self._context.get("previous_advance", False)
        if immo_percent:
            invoice_vals['immo_percent'] = immo_percent
        if previous_advance:
            invoice_vals['previous_advance'] = previous_advance
        return invoice_vals

    def action_view_immo_invoice(self):
        action = self.env['ir.actions.actions']._for_xml_id(
            'immo_bill.action_immo_bill_invoice')
        if self.immo_bill_ids:
            action['res_id'] = self.immo_bill_ids[0].id
            form_view = [(self.env.ref('immo_bill.view_immo_bill_invoice_form').id, 'form')]
            action['views'] = form_view
        return action

    def action_view_avenants(self):
        action = self.env['ir.actions.actions']._for_xml_id(
            'immo_bill.action_immo_bill_invoice')
        if self.immo_invoice_ids:
            action['res_id'] = self.immo_invoice_ids[0].id
            form_view = [(self.env.ref('immo_bill.view_immo_bill_invoice_form').id, 'form')]
            action['views'] = form_view
        return action

    @api.depends('date_order')
    def _compute_rg_date_expiration_(self):
        for rec in self:
            date = rec.date_order if rec.date_order else fields.Date.today()
            rec.rg_date_expiration = fields.Date.add(date, years=1)

    @api.depends('state', 'order_line.invoice_status', 'immo_bill_ids')
    def _compute_invoice_status(self):
        situation_orders = self.filtered(lambda so: len(so.immo_bill_ids) > 1)
        situation_orders.invoice_status = 'situation'
        no_situation_orders = self - situation_orders
        return super(SaleOrder, no_situation_orders)._compute_invoice_status()

    @api.depends('immo_invoice_ids')
    def compute_count_avenants(self):
        for rec in self:
            rec.count_avenants = len(rec.immo_invoice_ids)

    @api.constrains('is_avenant', 'immo_invoice_ids')
    def check_avenant(self):
        for rec in self:
            if rec.is_avenant:
                if len(rec.immo_invoice_ids) > 1:
                    raise UserError(_("Please select only one Chantier"))
            else:
                if len(rec.immo_invoice_ids) > 0:
                    rec.write({'immo_invoice_ids': [Command.set([])]})
