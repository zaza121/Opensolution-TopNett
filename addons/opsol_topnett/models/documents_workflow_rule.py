# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.fields import Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

def get_date_formated(date):
   if date:
        _date = datetime.strptime(date, "%d/%m/%Y")
        return _date.strftime("%Y-%m-%d")
   else:
        return date


class WorkflowRules(models.Model):
    _inherit = "documents.workflow.rule"

    topnet_action = fields.Selection(
        selection=[('load_emp', "Charger Employe"), ('load_sal', 'Charger Salaire')],
        string="Action Speciales Topnett",
        default="",
        required=False
    )

    def apply_actions(self, document_ids):
        """
        called by the front-end Document Inspector to apply the actions to the selection of ID's.

        :param document_ids: the list of documents to apply the action.
        :return: if the action was to create a new business object, returns an action to open the view of the
                newly created object, else returns True.
        """
        topnett_rules = self.filtered(lambda x: x.topnet_action)
        others = self - topnett_rules
        if self.topnet_action:

            documents = self.env['documents.document'].browse(document_ids)

            # partner/owner/share_link/folder changes
            document_dict = {}
            if self.user_id:
                document_dict['owner_id'] = self.user_id.id
            if self.partner_id:
                document_dict['partner_id'] = self.partner_id.id
            if self.folder_id:
                document_dict['folder_id'] = self.folder_id.id

            # Use sudo if user has write access on document else allow to do the
            # other workflow actions(like: schedule activity, send mail etc...)
            try:
                documents.check_access_rights('write')
                documents.check_access_rule('write')
                documents = documents.sudo()
            except AccessError:
                pass

            documents.write(document_dict)

            for document in documents:
                if self.remove_activities:
                    document.activity_ids.action_feedback(
                        feedback="completed by rule: %s. %s" % (self.name, self.note or '')
                    )

                if self.topnet_action == "load_emp":
                    self.execute_load_employee(document)
                if self.topnet_action == "load_sal":
                    pass

            return True
        else:
            return super(WorkflowRules, others).apply_actions(document_ids)

    def file_to_dict(self, url):
        """Get the data from URL."""
        _logger.info("Start get excel file ..............................")

        excel_file = pd.read_excel(url) # get excel file for salary
        excel_file.columns = excel_file.iloc[3]
        _datas = excel_file.iloc[4:].dropna(axis=1, how='all')
        datas = _datas.to_dict('records')
        datas = ['nan' in dt.keys() and dt.pop('nan') and dt or dt for dt in datas]

        _logger.info(f" template line: {str(datas[:0])}")
        _logger.info("end extract..............................")
        return datas

    def transform_employee(self, data_employee):
        """Changement du nom des colonnes employes et adaptation des valeurs"""
        _logger.info("Start transform employee data ..............................")

        def v_get_value(value, key):
            if not value:                
                return value
            elif key == 'numero':
                return value and int(value) or 0
            elif key == 'birthday':                
                return get_date_formated(value)
            elif key == 'registration_number':
                vals = value.split("/")
                return len(vals) > 1 and vals[-1].strip() or value
            else:
                return value

        _logger.info("Start transform..............................")
        map_croisement = {'Matricule': 'registration_number', 'Nom': 'nom', 'Prenom': 'prenom', 'Date naissance': 'birthday', 'Numero': 'numero'}
        transformed = []
        for line in data_employee:
            transformed.append({ map_croisement.get(key): v_get_value(line[key], map_croisement.get(key)) for key in line.keys() if key in map_croisement.keys()})

        _logger.info(f"{str(transformed[:5])}")
        _logger.info("end transform..............................")
        return transformed

    def update_employee(self, transformed):
        """Recupere les employee existants et les met a jour."""
        _logger.info("Start update employee ..............................")
        emp_lines = self.sudo().env["hr.employee"].search_read([], ['id', 'numero'])
        _logger.info(f" request {emp_lines}")

        existing_products = []
        new_products = []
        for lp_ in transformed:
            if 'numero' not in lp_.keys() or not lp_['numero']:
                continue

            exist = list(filter(lambda x: x['numero'] and x['numero'] == lp_['numero'], emp_lines))
            if exist:
                existing_products.append((exist[0]['id'], lp_))
            else:
                new_products.append(lp_)

        # write ou update
        for _id, vals in existing_products:
            self.env["hr.employee"].browse(_id).update(vals)
        # odoorpc_write("hr.employee", existing_products)

        # create new employee
        for elt in new_products:
            self.env["hr.employee"].create(elt)
        # ids = odoorpc_create("hr.employee", new_products)

        _logger.info("end updating employee..............................")
        return True


    def execute_load_employee(self, document):
        # load employee
        url = document.raw
        datas = self.file_to_dict(url)
        transformed = self.transform_employee(datas)
        transformed = self.update_employee(datas)
        # raise UserError(transformed)

