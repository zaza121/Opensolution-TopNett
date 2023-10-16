# -*- coding: utf-8 -*-

from datetime import date
from dateutil.relativedelta import relativedelta
from xml.etree import ElementTree as ET
import base64
import contextlib
import io

from odoo import models, fields, api, _
from odoo.fields import Command


class GenXMLCotWiz(models.TransientModel):

    _name = 'opsol_topnett.genxml_cot_wiz'
    _description = "Wizard XML cotisations"

    name = fields.Char('Nom fichier', readonly=False)
    lot_id = fields.Many2one(
        comodel_name='hr.payslip.run',
        string='Lot de bulletin',
    )
    description = fields.Text(string='Description')
    data = fields.Binary(
        string='Fichier',
        readonly=False,
        attachment=False
    )

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

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        # if self.lot_id:
        root = ET.Element("root")
        doc = ET.SubElement(root, "doc")
        # Adding subtags under the `Opening`
        # subtag 
        s_elem1 = ET.SubElement(doc, 'E4')
        s_elem2 = ET.SubElement(doc, 'D4')
         
        # Adding attributes to the tags under
        # `items`
        s_elem1.set('type', 'Accepted')
        s_elem2.set('type', 'Declined')
         
        # Adding text between the `E4` and `D5` 
        # subtag
        s_elem1.text = "King's Gambit Accepted"
        s_elem2.text = "Queen's Gambit Declined"

        # Converting the xml data to byte object,
        # for allowing flushing data to file 
        # stream
        b_xml = ET.tostring(root)
        # raise Warning(b_xml)
        b = base64.b64encode(b_xml) # bytes
        self.update({'data': b})
        # out = base64.encodebytes(buf.getvalue())

    def act_getfile(self):
        this = self[0]
        lang = this.lang if this.lang != NEW_LANG_KEY else False
        mods = sorted(this.mapped('modules.name')) or ['all']

        with contextlib.closing(io.BytesIO()) as buf:
            tools.trans_export(lang, mods, buf, this.format, self._cr)
            out = base64.encodebytes(buf.getvalue())

        filename = 'new'
        if lang:
            filename = tools.get_iso_codes(lang)
        elif len(mods) == 1:
            filename = mods[0]
        extension = this.format
        if not lang and extension == 'po':
            extension = 'pot'
        name = "%s.%s" % (filename, extension)
        this.write({'state': 'get', 'data': out, 'name': name})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'base.language.export',
            'view_mode': 'form',
            'res_id': this.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
