# -*- coding: utf-8 -*-
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import ValidationError, UserError


ARRONDI_NOT_FOUND = "l'article arrondi inexistant, veuillez le recreer svp"
_logger = logging.getLogger(__name__)

class Situation(models.Model):
    _name = 'immo_bill.situation'
    _description = 'Situation Invoice'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute="compute_name",
        readonly=True
    )
    immo_bill_id = fields.Many2one(
        comodel_name='immo_bill.invoice',
        string='Immo invoice',
    )
    date_confirmation = fields.Date(
        string='Date confirmation'
    )
    situation_progress = fields.Float(
        string='Progress',
        compute="compute_amount_total",
        store=True,
    )
    situation_order = fields.Integer(
        string='Order situation',
    )
    invoices_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='situation_id',
        domain=[('state', '!=', 'cancel')],
        string='Invoices',
    )
    
    line_ids = fields.One2many(
        string='Lines',
        comodel_name='immo_bill.situation_line',
        inverse_name='situation_id',
    )
    pre_payments_ids = fields.One2many(
        string='Acomptes',
        comodel_name='immo_bill.pre_payment',
        inverse_name='situation_id',
    )
    
    state = fields.Selection(
        string='state',
        selection=[('registered', 'New'), ('invoiced', 'Invoiced')],
        default="registered"
    )
    untaxed_amount = fields.Monetary(
        string="Total ht",
        compute="compute_amount_total",
        readonly=True,
        store=True
    )
    amount_total = fields.Monetary(
        string="Total",
        compute="compute_amount_total",
        readonly=True,
        store=True
    )
    amount_down_payment = fields.Monetary(
        string="Acompte de situation",
        compute="compute_down_payment",
        inverse="set_amount_down_payment",
        store=True
    )
    amount_down_payment_novat = fields.Monetary(
        string="Acompte de situation HT",
        compute="compute_down_payment_other",
        store=True
    )
    amount_total_nodp = fields.Monetary(
        string="Total (avec acompte)",
        compute="compute_down_payment_other",
        store=True
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related="immo_bill_id.currency_id",
        store=True
    )
    retenue_percent = fields.Float(
        string='% Retenue de garantie',
        related="immo_bill_id.retenue_percent",
        store=True
    )
    rg_amount_untaxed_total = fields.Monetary(
        string="Montant Retenu HT",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )
    rg_amount_total = fields.Monetary(
        string="Montant Retenu",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )
    immo_has_down_payment = fields.Boolean(
        string="Immo has down payment",
        compute="compute_down_payment",
        store=True
    )
    avancement_montant = fields.Boolean(related="immo_bill_id.avancement_montant")
    force_rounding_method_id = fields.Many2one(
        string="Rounding method",
        comodel_name="account.cash.rounding",
        default=lambda self: self.get_default_rounding()
    )
    amount_invoice_untaxed = fields.Monetary(
        string='Montant Facture HT',
        compute="compute_amount_total",
        store=True
    )
    diff_situation_invoice = fields.Monetary(
        string='Difference entre Facture et situation',
        compute="compute_amount_total",
        store=True
    )
    diff_situation_invoice_fix = fields.Monetary(
        string='Difference a ajouter a la base',
        compute="compute_amount_total",
        store=True
    )
    enable_fix_difference_ = fields.Boolean(
        string='Corriger difference avec arrondi',
        default=False
    )


    @api.model
    def get_default_rounding(self):
        default_rounding = self.env["account.cash.rounding"].search([], limit=1)
        return default_rounding if default_rounding else None

    def compute_name(self):
        for rec in self:
            rec.name = f"Situation {rec.situation_order}"

    @api.depends('invoices_ids.amount_total', 'immo_bill_id.line_ids.total_ttc')
    def compute_amount_total(self):
        prod_id = self.env['ir.model.data'].sudo()._xmlid_lookup('immo_bill.article_arrondi')[2]
        prod_arrondi = self.env["product.product"].browse(prod_id)
        for rec in self:

            if not prod_arrondi:
                raise UserError(_(ARRONDI_NOT_FOUND))

            progress = 0
            amount_total = sum(rec.line_ids.mapped('amount_progress'))
            amount_total_ht = sum(rec.line_ids.mapped('untaxed_amount_progress'))
            amount_inv_untaxed = sum(rec.invoices_ids.mapped('invoice_line_ids').filtered(
                lambda x: x.product_id.id != prod_arrondi.id).mapped('price_subtotal'))
            diff_sit_inv_fix = sum(rec.invoices_ids.mapped('invoice_line_ids').filtered(
                lambda x: x.product_id.id != prod_arrondi.id and not x.tax_ids).mapped('price_subtotal'))
            diff_sit_inv = amount_total_ht - amount_inv_untaxed
            if rec.immo_bill_id:
                total = sum(rec.immo_bill_id.line_ids.mapped('total_ttc'))
                progress = amount_total / total if total else 0
            
            rec.update({
                'untaxed_amount': amount_total_ht, 'amount_total': amount_total,
                'situation_progress': progress, 'amount_invoice_untaxed': amount_inv_untaxed,
                'diff_situation_invoice': diff_sit_inv, 'diff_situation_invoice_fix': diff_sit_inv_fix
            })

    @api.depends('untaxed_amount', 'retenue_percent')
    def _compute_retenue_percent(self):
        for rec in self:
             rec.rg_amount_untaxed_total = rec.untaxed_amount * rec.retenue_percent
             rec.rg_amount_total = rec.amount_total * rec.retenue_percent


    @api.depends('immo_bill_id.pre_payment_ids.total_ttc', 'immo_bill_id.sale_order_id')
    def compute_down_payment(self):
        for rec in self:

            rec.immo_has_down_payment = False
            if rec.amount_down_payment == 0:
                result = self.search([
                    ('situation_order', '<', rec.situation_order),
                    ('immo_bill_id', '=', rec.immo_bill_id.id)])
                result = result.sorted(key=lambda r: r.situation_order, reverse=True)
                progress = 0
                amount_total = sum(rec.line_ids.mapped('amount_progress'))
                if rec.immo_bill_id:
                    total = sum(rec.immo_bill_id.line_ids.mapped('total_ttc'))
                    progress = amount_total * 1.0 / total if total else 0

                total_progress = sum(result.mapped('situation_progress'))
                down_payment = sum(rec.immo_bill_id.pre_payment_ids.mapped('total_ttc'))
                down_payment_previous = sum(result.mapped('amount_down_payment'))
                remaining_progress = 1 - total_progress
                remaining_down_payment = down_payment - down_payment_previous
                current_progress = progress
                dp_situation_progress = current_progress / remaining_progress
                rec.amount_down_payment = remaining_down_payment * dp_situation_progress
                rec.immo_has_down_payment = down_payment > 0

    @api.depends('immo_bill_id.pre_payment_ids.total_ttc', 'immo_bill_id.sale_order_id')
    def set_amount_down_payment(self):
        self.compute_down_payment_other()
        self.invoices_ids.filtered(lambda move: move.name == '/').unlink()
        self.invoices_ids.filtered(lambda move: move.name != '/').button_cancel()
        self.create_invoice()

    @api.depends('amount_down_payment')
    def compute_down_payment_other(self):
        for rec in self:

            total_dp_ht = total_dp = rec.amount_down_payment

            if rec.immo_bill_id and rec.immo_bill_id.sale_order_id:
                taxes = rec.immo_bill_id.sale_order_id.mapped('order_line.tax_id')
                currency = rec.immo_bill_id.currency_id
                tax = taxes[0] if taxes else None
                if tax:
                    total_dp_ht = rec.get_ht_tax(total_dp, tax, currency)

            rec.amount_down_payment_novat = total_dp_ht
            rec.amount_total_nodp = rec.untaxed_amount - total_dp_ht

    def action_confirm(self):
        for rec in self:
            pass

    def get_invoice_values(self):
        order = self.immo_bill_id.sale_order_id
        avenants = self.immo_bill_id.avenant_ids

        infos = {}
        for lin in self.line_ids:
            if lin.sale_order_line_id:
                s_o_line = lin.sale_order_line_id
                infos[s_o_line.id] = s_o_line.product_uom_qty * lin.progress_percent

        immo_context = {'infos': infos}
        invoice_vals_list = []
        invoice_vals = order.with_context(immo_context)._prepare_invoice()
        
        sale_orders = order + avenants
        invoiceable_lines = sale_orders._get_invoiceable_lines()
        situations_lines_ids = self.line_ids.mapped('invoice_line_id.sale_order_line_id.id')
        invoiceable_lines = invoiceable_lines.filtered(lambda x: x.id in situations_lines_ids)

        invoice_line_vals = []
        down_payment_section_added = False
        invoice_item_sequence = 0

        for line in invoiceable_lines:
            line_values = line.with_context(immo_context)._prepare_invoice_line(sequence=invoice_item_sequence)
            invoice_line_vals.append(Command.create(line_values))
            invoice_item_sequence += 1

        if self.amount_down_payment_novat:
            dp_product_id = int(self.env['ir.config_parameter'].sudo().get_param('sale.default_deposit_product_id'))
            product = self.env['product.product'].browse(dp_product_id)
            taxes = self.immo_bill_id.sale_order_id.mapped('order_line.tax_id')
            tax = taxes[0].ids if taxes else []
            if not product:
                raise UserError(_("Please set a product for down payment"))
            line_values = {
                'product_id': dp_product_id, 'quantity': 1, 'price_unit': -self.amount_down_payment_novat,
                'name': product.name, 'tax_ids': [Command.set(tax)], 'minus_down_payment': True
            }
            invoice_line_vals.append(Command.create(line_values))

        invoice_vals['invoice_line_ids'] += invoice_line_vals
        invoice_vals['immo_inv_id'] = self.immo_bill_id.id
        invoice_vals['situation_id'] = self.id
        invoice_vals['invoice_cash_rounding_id'] = self.force_rounding_method_id.id if self.force_rounding_method_id and self.avancement_montant else None
        invoice_vals_list.append(invoice_vals)

        values = {**order._prepare_invoice()}
        return invoice_vals_list

    def create_invoice(self):
        for rec in self:
            invoice = self.env['account.move'].sudo().create(
                rec.get_invoice_values()).with_user(self.env.uid)  # Unsudo the invoice after creation

    def open_invoice(self):
        self.ensure_one()
        invoices = self.mapped('invoices_ids')
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {'default_move_type': 'out_invoice',}
        if len(self) == 1:
            context.update({'default_invoice_origin': self.name})
        action['context'] = context
        return action

    @api.model
    def get_ht_tax(self, amount, tax, currency):
        is_tax_included = any(tax.mapped('price_include'))
        if is_tax_included:
            amount_ht = tax.compute_all(amount, currency=currency, quantity=1)['total_excluded']
        else:
            amount_ht = (amount / (1 + (tax.amount / 100)))
        return currency.round(amount_ht)

    @api.model
    def get_situation_to_current(self):
        result = self.search([
            ('situation_order', '<=', self.situation_order),
            ('immo_bill_id', '=', self.immo_bill_id.id)])
        result = result.sorted(key=lambda r: r.situation_order, reverse=True)
        total = sum(result.mapped('amount_total_nodp'))
        total_progress = sum(result.mapped('situation_progress'))
        pre_payments_ids = self.immo_bill_id.pre_payment_ids
        sale_order_id = self.immo_bill_id.sale_order_id

        data_payment = []
        for payment in pre_payments_ids:
            price_unit = payment.total_ttc
            if sale_order_id:
                taxes = sale_order_id.mapped('order_line.tax_id')
                currency = self.immo_bill_id.currency_id
                tax = taxes[0] if taxes else None
                if tax:
                    price_unit = self.get_ht_tax(price_unit, tax, currency)
                data_payment.append((sale_order_id.date_order, 0, price_unit, _("Acompte")))

        data = []
        for sit in result:
            data.append((sit.date_confirmation, round(total_progress * 100, 2), total, _("Avancement")))
            total_progress -= sit.situation_progress
            total -= sit.amount_total_nodp

        # add down payment
        data.extend(data_payment)
        return data

    @api.model
    def get_avancement_by_product(self, line_id):
        avancement = 0
        line_product = self.env['immo_bill.invoice_line'].browse(line_id)
        if not line_product:
            return 0
        sale_line = line_product and line_product.sale_order_line_id or None
        if sale_line:
            result = self.search([
                ('situation_order', '<=', self.situation_order),
                ('immo_bill_id', '=', self.immo_bill_id.id)])
            result = result.sorted(key=lambda r: r.situation_order, reverse=False)
            r_avan = sum(result.mapped('line_ids').filtered(
                lambda x: x.invoice_line_id.sale_order_line_id.id == sale_line.id).mapped('progress_percent'))
            avancement = round(r_avan * 100, 2)
        return avancement

    @api.model
    def get_avancement_amount_by_product(self, product_id):
        avancement = 0
        product = self.env['product.template'].browse(product_id)
        if product:
            result = self.search([
                ('situation_order', '<=', self.situation_order),
                ('immo_bill_id', '=', self.immo_bill_id.id)])
            r_avan = sum(result.mapped('line_ids').filtered(
                lambda x: x.product_id.id == product_id).mapped('amount_progress'))
            avancement = r_avan
        return avancement

    @api.model
    def get_info_avancement_amount_by_product(self, line_id):
        avancement = 0
        before_c_situation = current_situation = final_situation = 0
        line_product = self.env['immo_bill.invoice_line'].browse(line_id)
        sale_line = line_product and line_product.sale_order_line_id or None
        if sale_line:
            result = self.search([
                ('situation_order', '<', self.situation_order),
                ('immo_bill_id', '=', self.immo_bill_id.id)])
            before_c_situation = sum(result.mapped('line_ids').filtered(
                lambda x: x.invoice_line_id.sale_order_line_id.id == sale_line.id).mapped(
                'untaxed_amount_progress'))
            current_situation = sum(self.mapped('line_ids').filtered(
                lambda x: x.invoice_line_id.sale_order_line_id.id == sale_line.id).mapped(
                'untaxed_amount_progress'))
            final_situation = before_c_situation + current_situation

        return (before_c_situation, current_situation, final_situation)

    @api.constrains('amount_down_payment')
    def check_amount_down_payment(self):
        for rec in self:
            no_check_down_pay = rec._context.get("no_check_down_pay", False)
            if not no_check_down_pay:
                result = self.search([('immo_bill_id', '=', rec.immo_bill_id.id)])
                total_dp_used = sum(result.mapped('amount_down_payment'))
                down_payment = sum(rec.immo_bill_id.pre_payment_ids.mapped('total_ttc'))
                # if total_dp_used > down_payment:
                #     raise UserError(_("Le total des acomptes de situation (%.2f) est superieur a l'acompte du chantier %.2f", total_dp_used, down_payment) )

    @api.constrains('diff_situation_invoice', 'enable_fix_difference_')
    def fix_difference(self):
        prod_id = self.env['ir.model.data'].sudo()._xmlid_lookup('immo_bill.article_arrondi')[2]
        prod_arrondi = self.env["product.product"].browse(prod_id)
        self.env['account.move'].invalidate_recordset()
        for rec in self:
            update_values = []
            if not prod_arrondi:
                raise UserError(_("l'article arrondi inexistant, veuillez le recreer svp"))
            if len(rec.invoices_ids) == 0 or rec.amount_invoice_untaxed == 0 or not rec.enable_fix_difference_:
                continue

            # delete existing lines
            to_delete = rec.invoices_ids.mapped('invoice_line_ids').filtered(lambda x: x.product_id.id == prod_arrondi.id)
            for elt in to_delete:
                update_values.append(Command.delete(elt.id))

            if rec.diff_situation_invoice != 0:
                _taxes = rec.mapped('invoices_ids.invoice_line_ids.tax_ids')
                taxes = [_taxes[0].id] if _taxes else []
                values = {
                    'product_id': prod_arrondi.id, 'name': 'Arrondi',
                    'quantity': 1, 'price_unit': rec.diff_situation_invoice,
                    'move_type': 'entry', 'tax_ids': [Command.set(taxes)]
                }
                update_values.append(Command.create(values))
                
            # raise UserError(update_values)
            rec.invoices_ids.update({'invoice_line_ids': update_values})


class SituationLine(models.Model):
    _name = 'immo_bill.situation_line'
    _description = 'Situation Invoice Line'
    _rec_name = 'name'

    invoice_id = fields.Many2one(
        string='Invoice immo',
        comodel_name='immo_bill.invoice',
        related='invoice_line_id.invoice_id',
        store=True
    )
    invoice_line_id = fields.Many2one(
        string='Invoice Line',
        comodel_name='immo_bill.invoice_line'
    )
    name = fields.Text(
        string='Name',
        related="invoice_line_id.sale_order_line_id.name"
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Order line',
        related="invoice_line_id.sale_order_line_id"
    )
    display_type = fields.Selection(
        string='Display type',
        related="invoice_line_id.display_type",
        copy=False,
    )
    product_id = fields.Many2one(
        string='Product',
        comodel_name='product.template',
        related='invoice_line_id.product_id',
        readonly=True,
        store=True
    )
    progress_percent = fields.Float(
        string='Progress Percent',
        default=0
    )
    situation_id = fields.Many2one(
        comodel_name='immo_bill.situation',
        string='Situation'
    )
    untaxed_amount_progress = fields.Float(
        string='Untaxed amount',
        compute="_compute_amount_progress",
        store=True
    )
    amount_progress = fields.Float(
        string='Amount',
        compute="_compute_amount_progress",
        store=True
    )
    retenue_percent = fields.Float(
        string='% Retenue de garantie',
        related="situation_id.retenue_percent",
        store=True
    )
    rg_amount_untaxed_total = fields.Float(
        string="Montant Retenu",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )
    rg_total = fields.Float(
        string="Total amount",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )

    @api.depends('invoice_line_id', 'progress_percent')
    def _compute_amount_progress(self):
        for rec in self:
            total = rec.invoice_line_id.total_ttc
            rg_remain_percent = 1 - rec.invoice_id.retenue_percent
            total_ht = rec.invoice_line_id.total_ht
            rec.update({
                'untaxed_amount_progress': total_ht * rec.progress_percent,
                'amount_progress': total * rec.progress_percent * rg_remain_percent,
            })

    @api.depends('untaxed_amount_progress', 'retenue_percent')
    def _compute_retenue_percent(self):
        for rec in self:
             rec.rg_amount_untaxed_total = rec.untaxed_amount_progress * rec.retenue_percent
             rec.rg_total = rec.untaxed_amount_progress - rec.rg_amount_untaxed_total
