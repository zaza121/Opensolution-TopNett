# -*- coding: utf-8 -*-
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class Invoice(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'immo_bill.invoice'
    _description = 'Chantier'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        required=True, copy=False,
        default=lambda self: _('New')
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        related="sale_order_id.partner_id",
        store=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale order',
        tracking=True,
    )
    invoices_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='immo_inv_id',
        domain=[('state', '!=', 'cancel')],
        string='Invoices',
        tracking=True,
    )
    
    count_invoice = fields.Integer(
        string='count_invoice',
        compute="_compute_count_invoice"
    )
    
    building_progress = fields.Float(
        string='Progress',
        default=0
    )
    current_progress = fields.Float(
        string='Actuel progress',
        compute="_compute_amount",
        readonly=True
    )
    situation_ids = fields.One2many(
        comodel_name='immo_bill.situation',
        inverse_name='immo_bill_id',
        string='Situations',
        tracking=True,
    )
    count_situation = fields.Integer(
       string="Number of situations",
       compute="_compute_count_situation" 
    )
    
    line_ids = fields.One2many(
        comodel_name='immo_bill.invoice_line',
        inverse_name='invoice_id',
        string='Lines',
        compute="_compute_line_ids",
        store=True,
        readonly=False,
        tracking=True,
    )
    pre_payment_ids = fields.One2many(
        comodel_name='immo_bill.pre_payment',
        inverse_name='invoice_id',
        string='Lines',
        compute="_compute_payment_line",
        store=True,
        readonly=False
    )
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount",
        readonly=True
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related="sale_order_id.currency_id",
        store=True
    )
    uninvoiced_amount = fields.Monetary(
        string="Uninvoiced amount",
        compute="_compute_amount",
        readonly=True
    )
    add_avenant = fields.Boolean(string='Avenant', tracking=True,)
    avenant_ids = fields.Many2many(
        comodel_name='sale.order',
        string='Avenants',
        relation="invoice_to_saleorder"
    )
    avancement_montant = fields.Boolean(string='Avancement en montant', tracking=True,)
    retenue_percent = fields.Float(
        string='% Retenue de garantie',
        compute="_compute_retenue_percent",
        readonly=False,
        store=True,
        tracking=True,
    )
    rg_sale_mode = fields.Selection(
        string="Retenue de gestion Mode",
        selection=[('ht', 'Hors taxe'), ('ttc', 'TTC')],
        default=lambda self: self.default_get_rg_sale_mode(),
        store=True
    )
    rg_amount_untaxed_total = fields.Monetary(
        string="Montant a retenir HT",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )
    rg_amount_total = fields.Monetary(
        string="Montant a retenir",
        compute="_compute_retenue_percent",
        readonly=True,
        store=True
    )
    rg_cumul_unt_amount = fields.Monetary(
        string="Cumul retenue HT",
        compute="_compute_amount",
        readonly=True
    )
    rg_cumul_amount = fields.Monetary(
        string="Cumul retenue",
        compute="_compute_amount",
        readonly=True
    )
    rg_date_expiration = fields.Date(
        string='Date expiration retenue',
        related="sale_order_id.rg_date_expiration"
    )
    rg_invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Rg Invoice',
    )

    def default_get_rg_sale_mode(self):
        use_rg = self.env['ir.config_parameter'].sudo().get_param('immo_bill.param_rg_enable'),
        rg_sale_mode = self.env['ir.config_parameter'].sudo().get_param('immo_bill.param_rg_sale_mode')
        return rg_sale_mode if use_rg else False

    def _compute_amount(self):
        for rec in self:
            amount_total = sum(rec.line_ids.filtered(lambda x: not x.is_acompte).mapped('total_ttc'))
            acompte = sum(rec.line_ids.filtered(lambda x: x.is_acompte).mapped('total_ttc'))
            total_situation = sum(rec.situation_ids.mapped("amount_total"))
            rg_cumul_unt_amount = sum(rec.situation_ids.mapped("rg_amount_untaxed_total"))
            rg_cumul_amount = sum(rec.situation_ids.mapped("rg_amount_total"))
            current_progress = amount_total and total_situation / amount_total or 0
            uninvoiced_amount = amount_total * (1 - current_progress)
            rec.update({
                'amount_total': amount_total,
                'uninvoiced_amount': uninvoiced_amount,
                'current_progress': current_progress,
                'rg_cumul_unt_amount': rg_cumul_unt_amount,
                'rg_cumul_amount': rg_cumul_amount,
            })

    def _compute_count_situation(self):
        for rec in self:
            rec.count_situation = len(rec.situation_ids)

    def _compute_count_invoice(self):
        for rec in self:
            rec.count_invoice = len(rec.invoices_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'immo_bill.invoice') or _("New")

        return super().create(vals_list)

    @api.depends('sale_order_id', 'avenant_ids')
    def _compute_line_ids(self):
        sale_obj = self.env['sale.order']
        for rec in self:

            no_del_lines = rec.line_ids.filtered(lambda x: x.progress > 0).mapped('sale_order_line_id')
            sales_orders = rec.sale_order_id
            sales_orders |= sale_obj.search([('name', 'in', rec.avenant_ids.mapped('name'))])

            if sales_orders:
                values = [Command.delete(_line.id) for _line in rec.line_ids if _line.progress == 0]
                lines = sales_orders.mapped('order_line').filtered(
                    lambda x: not x.display_type and x.product_uom_qty > 0 or x.display_type).sorted(
                    key=lambda x: x.order_id.id if x.order_id.id == rec.sale_order_id else x.order_id.id * 1000)
                i = 0
                for o_line in lines:
                    i += 1
                    if o_line.id not in no_del_lines.ids:
                        from_avenant = o_line.order_id.id not in rec.sale_order_id.mapped('id')
                        line = {'invoice_id': rec.id, 'sale_order_line_id': o_line.id, 'sequence': i, 'from_avenant': from_avenant}
                        values.append(Command.create(line))
                    else:
                        values.append(Command.update(o_line.id, {'sequence': i}))
                rec.update({'line_ids': values})
            else:
                rec.line_ids.unlink()

    @api.depends('sale_order_id.order_line.price_unit')
    def _compute_payment_line(self):
        for rec in self:
            if rec.sale_order_id:
                values = [Command.delete(_line.id) for _line in rec.pre_payment_ids]
                lines = rec.sale_order_id.order_line.filtered(
                    lambda x: not x.display_type and x.product_uom_qty == 0)
                for o_line in lines:
                    line = {'invoice_id': rec.id, 'sale_order_line_id': o_line.id}
                    values.append(Command.create(line))
                rec.update({'pre_payment_ids': values})
            else:
                rec.pre_payment_ids.unlink()

    @api.depends('sale_order_id.retenue_percent')
    def _compute_retenue_percent(self):
        for rec in self:
            retenue_percent = 0
            rg_amount_untaxed_total = 0
            rg_sale_mode = rg_amount_total = None
            if rec.sale_order_id:
                untaxed_total = sum(rec.line_ids.mapped('total_ht'))
                total = sum(rec.line_ids.mapped('total_ttc'))
                retenue_percent = rec.sale_order_id.retenue_percent
                rg_sale_mode = rec.sale_order_id.rg_sale_mode
                rg_amount_untaxed_total = untaxed_total * (1.0 - retenue_percent)
                rg_amount_total = total * (1.0 - retenue_percent)
            rec.update({
                'retenue_percent': retenue_percent,
                'rg_sale_mode': rg_sale_mode,
                'rg_amount_untaxed_total': rg_amount_untaxed_total,
                'rg_amount_total': rg_amount_total
            })

    def action_view_invoice(self):
        invoices = self.ids
        action = self.env['ir.actions.actions']._for_xml_id('immo_bill.action_immo_bill_invoice')
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('immo_bill.view_immo_bill_invoice_form').id, 'form')]
            action['views'] = form_view
            action['res_id'] = invoices[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.model
    def prepare_situation_values(self, changes):
        n_order = self.situation_ids.mapped('situation_order')
        values = {
            'immo_bill_id': self.id,
            'date_confirmation': fields.Date.today(),
            'situation_order': max(n_order) + 1 if len(n_order) > 0 else 1,
            'enable_fix_difference_': True
        }

        lines = []
        for _change in changes:
            line = {'name': "", 'invoice_line_id': _change[0].id, 'progress_percent': _change[1] }
            lines.append(Command.create(line))
        values['line_ids'] = lines
        return values

    @api.constrains('line_ids', 'amount_total')
    def check_percentage(self):

        no_create_situation = self._context.get("no_create_situation", False)
        if not no_create_situation:
            for rec in self:
                lines = rec.line_ids.filtered(lambda x: not x.is_acompte)
                situations_lines = rec.situation_ids.mapped('line_ids')
                to_update = []

                # get the changements
                for line in lines:

                    if line.display_type:
                        to_update.append((line, 0))
                        continue

                    sit_lines = situations_lines.filtered(lambda x: x.invoice_line_id.id == line.id)
                    current_progress = sum(sit_lines.mapped('progress_percent'))
                    diff = line.progress - current_progress

                    if diff < 0:
                        raise UserError(_(
                            "the product %s has already a progress percentage of %.2f %s", line.product_id.name, current_progress * 100, '%'))
                    elif diff > 0:
                        to_update.append((line, diff))

                # create the situation
                total_percent = sum([x[1] for x in to_update]) if to_update else 0
                if to_update and total_percent > 0:
                    situation = self.env['immo_bill.situation'].create(
                        rec.prepare_situation_values(to_update))
                    situation.create_invoice()
                    message = _(
                        "Nouvelle situation cree. \t  Avanacement de %.2f %% pour un total de %.2f .",
                        situation.situation_progress * 100, situation.amount_total)
                    rec.message_post(body=message)

                    # get pre payments
                    rec.pre_payment_ids.filtered(lambda x: not x.situation_id).update({'situation_id': situation.id})

    def action_update_status(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "immo_bill.action_view_sale_advance_payment_inv")
        action['context'] = {
            'default_immo_bill_id': self.id,
            'default_situation_order': 2,
            'default_situation_progress': 1.0 - self.current_progress,
            'default_initial_amount': self.amount_total
        }
        return action

    def open_situation(self):
        for rec in self:
 
            action = self.env["ir.actions.actions"]._for_xml_id(
                "immo_bill.action_immo_bill_situation")
            action['domain'] = [('id', 'in', rec.situation_ids.ids)]
            return action
    
    def open_invoice(self):
        for rec in self:
 
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice_type")
            action['domain'] = [('id', 'in', rec.invoices_ids.ids)]
            return action

    @api.model
    def get_invoice_report_data(self, situation=None):
        total_ht = sum(self.line_ids.mapped('total_ht'))
        total_vat = sum(self.line_ids.mapped('vat'))
        total_ttc = total_ht + total_vat
        residual = total_ttc
        if situation:
            situation = self.env['immo_bill.situation'].browse(situation)
            residual -= situation.get_situation_to_current()[0][2]
        return (total_ht, total_vat, total_ttc, residual)

    def rg_generate_invoice(self):
        self.ensure_one()

        # check the condition
        today = fields.Date.today()
        
        if self.current_progress < 1:
            raise UserError(_(
                "La progression actuelle du chantier est de %d (%) et non de 100%, condition necessaire pour generer la facture de retenue",
                self.current_progress))

        if today < self.rg_date_expiration:
            raise UserError(_("La facture de retenue ne peut pas etre genere avant le %s", self.rg_date_expiration))

        invoice = self.env['account.move'].sudo().create(
            self.rg_get_invoice_values()).with_user(self.env.uid)  # Unsudo the invoice after creation
        self.rg_invoice_id = invoice

    def rg_get_invoice_values(self):
        self.ensure_one()
        order = self.sale_order_id
        avenants = self.avenant_ids
        retenue_percent = self.retenue_percent

        infos = {}
        for lin in self.line_ids:
            if lin.sale_order_line_id:
                s_o_line = lin.sale_order_line_id
                infos[s_o_line.id] = s_o_line.product_uom_qty * retenue_percent

        immo_context = {'infos': infos, 'no_retenue': True}
        invoice_vals_list = []
        invoice_vals = order.with_context(immo_context)._prepare_invoice()
        
        sale_orders = order + avenants
        invoiceable_lines = sale_orders._get_invoiceable_lines()
        immo_invoice_lines_ids = self.line_ids.mapped('sale_order_line_id.id')
        invoiceable_lines = invoiceable_lines.filtered(lambda x: x.id in immo_invoice_lines_ids)

        invoice_line_vals = []
        down_payment_section_added = False
        invoice_item_sequence = 0

        for line in invoiceable_lines:
            line_values = line.with_context(immo_context)._prepare_invoice_line(sequence=invoice_item_sequence)
            invoice_line_vals.append(Command.create(line_values))
            invoice_item_sequence += 1

        invoice_vals['invoice_line_ids'] += invoice_line_vals
        invoice_vals['immo_inv_id'] = self.id
        invoice_vals_list.append(invoice_vals)

        return invoice_vals_list

    def synchro_data_saleorder(self):
        self = self.with_context({'no_create_situation': True, 'no_check_down_pay': True})
        for rec in self:
            sales_orders = rec.sale_order_id
            sales_orders |= rec.avenant_ids
            if sales_orders:
                values = []
                lines = sales_orders.mapped('order_line').filtered(
                    lambda x: not x.display_type and x.product_uom_qty > 0 or x.display_type)
                situations_lines = rec.situation_ids.mapped('line_ids')
                current_lines = self.line_ids
                current_sales_lines = self.line_ids.mapped('sale_order_line_id')

                i = 0
                for o_line in lines:
                    i += 1
                    progress = sum(situations_lines.filtered(
                            lambda x: x.sale_order_line_id.id == o_line.id).mapped('progress_percent'))
                    if o_line.id in current_sales_lines.ids:
                        immo_line = current_lines.filtered(lambda x: x.sale_order_line_id.id == o_line.id)
                        if immo_line:
                            values.append(Command.update(immo_line.id, {'progress': progress, 'sequence': i}))
                    else:
                        line = {'invoice_id': rec.id, 'sale_order_line_id': o_line.id, 'progress': progress, 'sequence': i}
                        values.append(Command.create(line))
                rec.with_context({'no_create_situation': True, 'no_check_down_pay': True})._compute_payment_line()
                rec.with_context({'no_create_situation': True, 'no_check_down_pay': True}).update({'line_ids': values})


class ImmoInvoiceLine(models.Model):
    _name = 'immo_bill.invoice_line'
    _description = 'Immo Invoice Line'
    _rec_name = 'name'
    _order = 'invoice_id, sequence'

    sequence = fields.Integer(
        string='Sequence'
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Order line'
    )
    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        related="sale_order_line_id.product_template_id",
    )
    name = fields.Text(
        string='Designation',
        related="sale_order_line_id.name",
        copy=False,
    )
    display_type = fields.Selection(
        string='Display type',
        related="sale_order_line_id.display_type",
        copy=False,
    )
    quantity = fields.Float(
        string='Quantity',
        # related="sale_order_line_id.product_uom_qty",
        compute="_compute_data",
        store=True
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related="sale_order_line_id.product_uom",
        string='Unit'
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related="sale_order_line_id.product_uom",
        string='Unit'
    )
    price_unit = fields.Float(
        string='Price Unit HT',
        # related="sale_order_line_id.price_unit",
        compute="_compute_data",
        store=True,
        digits='Product Price',
    )
    total_ht = fields.Monetary(
        string='Total HT',
        # related="sale_order_line_id.price_subtotal",
        compute="_compute_data",
        store=True,
    )
    price_subtotal = fields.Monetary(
        string='Total HT',
        related="sale_order_line_id.price_subtotal"
    )
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        related="sale_order_line_id.tax_id"
    )
    total_ttc = fields.Monetary(
        string='Total TTC',
        compute="_compute_data",
        store=True
    )
    progress = fields.Float(
        string='Progress',
    )
    untaxed_total_progress = fields.Monetary(
        string='Avancement Total HT',
        compute="compute_total_progress",
        inverse="inverse_total_progress",
        store=True
    )
    ro_progress = fields.Float(
        string='Progress',
        compute="compute_static_value",
    )
    ro_untaxed_total_progress = fields.Monetary(
        string='Avancement Total HT',
        compute="compute_static_value",
    )
    total_progress = fields.Monetary(
        string='Total Progress',
        compute="compute_total_progress",
        store=True
    )
    vat = fields.Float(
        string='VAT',
        # related="sale_order_line_id.price_tax",
        compute="_compute_data",
        store=True
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related="sale_order_line_id.currency_id"
    )
    invoice_id = fields.Many2one(
        comodel_name='immo_bill.invoice',
        string='Immo Invoice',
    )
    is_acompte = fields.Boolean(
        string='Is acompte',
        default=False,
        compute="_compute_data",
        store=True
    )
    from_avenant = fields.Boolean(string='Is avenant', default=False)

    def unlink(self):
        for line in self:
            if line.progress > 0:
                raise UserError(_(
                    "You cannot delete a line with a progress greater than 0: %s - %.2f",
                    line.name, line.progress * 100))
        return super(ImmoInvoiceLine, self).unlink()

    @api.depends('progress', 'total_ttc')
    def compute_total_progress(self):
        for rec in self:
            rec.update({
                'untaxed_total_progress': rec.progress * rec.total_ht,
                'total_progress': rec.progress * rec.total_ttc,
            })

    @api.onchange('untaxed_total_progress')
    def inverse_total_progress(self):
        for rec in self:
            val = rec.untaxed_total_progress / rec.total_ht if rec.total_ht > 0 else 0
            rec.update({'progress': val})

    @api.depends('progress', 'untaxed_total_progress')
    def compute_static_value(self):
        for rec in self:
            rec.ro_progress = rec.progress
            rec.ro_untaxed_total_progress = rec.untaxed_total_progress

    @api.depends('sale_order_line_id', 'total_ht', 'vat')
    def _compute_data(self):
        for rec in self:
            quantity = price_unit = total_ht = vat = total_ttc = progress = 0
            _is_acompte = False
            if rec.sale_order_line_id:
                quantity = rec.sale_order_line_id.product_uom_qty
                price_unit = rec.sale_order_line_id.price_unit
                total_ht = rec.sale_order_line_id.price_subtotal
                vat = rec.sale_order_line_id.price_tax
                total_ttc = total_ht + vat
                if quantity == 0 and rec.sale_order_line_id.product_type == 'service':
                    quantity = -1
                    total_ht = price_unit * quantity
                    total_ttc = total_ht - vat
                    _is_acompte = True
                    progress = 1

            rec.update({
                'quantity': quantity, 'price_unit':  price_unit,
                'total_ht':  total_ht, 'total_ttc':  total_ttc,
                'vat': vat, 'is_acompte':  _is_acompte, 'progress': progress
            })


class InvoiceLinePrePayment(models.Model):
    _name = 'immo_bill.pre_payment'
    _description = 'Immo Invoice pre payment'
    _rec_name = 'name'

    sequence = fields.Integer(
        string='Sequence',
        related="sale_order_line_id.sequence",
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Order line'
    )
    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        related="sale_order_line_id.product_template_id",
    )
    name = fields.Text(
        string='Designation',
        related="sale_order_line_id.name",
        copy=False,
    )
    display_type = fields.Selection(
        string='Display type',
        related="sale_order_line_id.display_type",
        copy=False,
    )
    quantity = fields.Float(
        string='Quantity',
        # related="sale_order_line_id.product_uom_qty",
        compute="_compute_data",
        store=True
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related="sale_order_line_id.product_uom",
        string='Unit'
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related="sale_order_line_id.product_uom",
        string='Unit'
    )
    price_unit = fields.Float(
        string='Price Unit HT',
        # related="sale_order_line_id.price_unit",
        compute="_compute_data",
        store=True,
        digits='Product Price',
    )
    total_ht = fields.Monetary(
        string='Total HT',
        # related="sale_order_line_id.price_subtotal",
        compute="_compute_data",
        store=True,
    )
    price_subtotal = fields.Monetary(
        string='Total HT',
        related="sale_order_line_id.price_subtotal"
    )
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        related="sale_order_line_id.tax_id"
    )
    total_ttc = fields.Monetary(
        string='Total TTC',
        compute="_compute_data",
        store=True
    )
    progress = fields.Float(
        string='Progress',
    )
    total_progress = fields.Monetary(
        string='Total Progress',
        compute="compute_total_progress",
        store=True
    )
    vat = fields.Float(
        string='VAT',
        compute="_compute_data",
        store=True
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related="sale_order_line_id.currency_id"
    )
    invoice_id = fields.Many2one(
        comodel_name='immo_bill.invoice',
        string='Immo Invoice',
    )
    is_acompte = fields.Boolean(
        string='Is acompte',
        default=False,
        compute="_compute_data",
        store=True
    )
    situation_id = fields.Many2one(
        comodel_name='immo_bill.situation',
        string='Situation',
        tracking=True,
    )
            

    @api.depends('progress', 'total_ttc')
    def compute_total_progress(self):
        for rec in self:
            rec.total_progress = rec.progress * rec.total_ttc

    @api.depends('sale_order_line_id', 'total_ht', 'vat')
    def _compute_data(self):
        for rec in self:
            quantity = price_unit = total_ht = vat = total_ttc = progress = 0
            _is_acompte = False
            if rec.sale_order_line_id:
                quantity = rec.sale_order_line_id.product_uom_qty
                price_unit = rec.sale_order_line_id.price_unit
                total_ht = rec.sale_order_line_id.price_subtotal

                vat = 0
                if rec.sale_order_line_id.tax_id:
                    _tax = rec.sale_order_line_id.tax_id
                    taxes_result = _tax.compute_all(
                        price_unit, currency=rec.sale_order_line_id.currency_id, quantity=-1,
                        product=rec.sale_order_line_id.product_id)
                    vat = taxes_result['total_included'] - taxes_result['total_excluded']
                total_ttc = total_ht + vat
                if quantity == 0 and rec.sale_order_line_id.product_type == 'service':
                    quantity = 1
                    total_ht = price_unit * quantity
                    total_ttc = total_ht - vat
                    _is_acompte = True
                    progress = 1

            rec.update({
                'quantity': quantity, 'price_unit':  price_unit,
                'total_ht':  total_ht, 'total_ttc':  total_ttc,
                'vat': vat, 'is_acompte':  _is_acompte, 'progress': progress
            })
