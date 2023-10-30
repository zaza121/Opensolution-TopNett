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
   if date and type(date) in [str, datetime, date]:
        _date = datetime.strptime(date, "%d/%m/%Y") if type(date) != datetime else date
        return _date.strftime("%Y-%m-%d")
   else:
        return "" 


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
                    self.execute_load_salaire(document)

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

    def get_salaire_data(self, url):
        """Get les donnees de salaire from URL."""
        _logger.info("Start get excel file ..............................")

        excel_file = pd.read_excel(url) # get excel file for salary
        excel_file.columns = excel_file.iloc[3]
        _datas = excel_file.iloc[4:].dropna(axis=1, how='all')
        _datas = _datas.replace({np.nan:None})
        datas = _datas.to_dict('records')
        datas = ['nan' in dt.keys() and dt.pop('nan') and dt or dt for dt in datas]

        #for values in datas:
        #    val = values['date_salaire'] and type(values['date_salaire']) == 'Timestamp' and values['date_salaire'].to_pydatetime().strftime("%Y-%m-%d") or values['date_salaire']
        #    values['date_salaire'] = val

        _logger.info(f" template line: {datas}")
        _logger.info("end extract..............................")
        return datas

    def transform(self, datas):
        """Change les nom des colonnes de salaire."""
        def v_get_value(value, key):
            if key in ['standard_price', 'supplier_stock']:
                return float(value.replace(',', '.')) if value else 0
            elif key in ['image_1920']:
                if 'http://' not in value:
                    value = value and 'http://' + value or value
                return value
            else:
                return value

        _logger.info("Start transform..............................")
        map_croisement = {
            'Matricule': 'matricule', 'Salaire brut': 'salaire_brut', 'Travaillées': 'h_travailles', 'Complémentaires': 'h_complementaires',
            'Supplémentaires': 'h_supplementaires', 'Maladie': 'c_maladie', 'A.T.': 'c_at', 'Maternité': 'c_maternite', 'Congés.P': 'c_payes', 'Autres Abs.': 'c_autres',
            'DateEntree1': 'date_entree1', 'DateEntree2': 'date_entree2', 'Maintien': 'maintien', 'Prime': 'prime', 'date_salaire': 'date_salaire'
        }
        transformed = []
        for line in datas:
            transformed.append({ map_croisement.get(key): v_get_value(line[key], map_croisement.get(key)) for key in line.keys() if key in map_croisement.keys()})

        _logger.info(f"{str(transformed[:5])}")
        _logger.info("end transform..............................")
        return transformed

    def transform2(self, lines):
        """Adapte les valeurs des salaires."""

        _logger.info("Start transform2..............................")
        transformed = []
        for line in lines:
            vals = line['matricule'].split("/")
            line['matricule'] = len(vals) > 1 and vals[-1].strip() or line['matricule']
            line['salaire_brut'] = float(line['salaire_brut'].replace(";", "")) if type(line['salaire_brut']) == 'str' else line['salaire_brut']
            line['date_entree1'] = get_date_formated(line['date_entree1'])
            line['date_entree2'] = get_date_formated(line['date_entree2'])
            line['date_salaire'] = get_date_formated(line['date_salaire'])
            transformed.append(line)

            if not line["date_entree1"]:
                line.pop('date_entree1')
            if not line["date_entree2"]:
                line.pop('date_entree2')

        _logger.info(f"{str(transformed[:5])}")
        _logger.info("end transform2..............................")
        return transformed

    def split_nouveau_existant(self, transformed):
        """Separe creation et mise a jour."""
        _logger.info(f"data : {transformed[:5]}")
        _logger.info("Start Separation nouveau et anciens ..............................")

        imp_lines = self.env["opsol_topnett.imp_salaire_line"].search_read([('date_salaire', '!=', False)], ['id', 'date_salaire', 'matricule'])
        existing_products = []
        new_products = []
        for lp_ in transformed:
            if 'date_salaire' not in lp_.keys() or type(lp_['date_salaire']) == float:
                continue

            exist = list(filter(lambda x: x['date_salaire'] and lp_['date_salaire'] and x['matricule'] == lp_['matricule'] and (type(x['date_salaire']) == str and  x['date_salaire'][:7] or x['date_salaire'].strftime('%Y-%m')) == lp_['date_salaire'][:7], imp_lines))
            if exist:
                existing_products.append((exist[0]['id'], lp_))
            else:
                new_products.append(lp_)
        _logger.info(f" existing: {existing_products} et news: {new_products}")
        return {'exist': existing_products, 'news': new_products}

    def creer_line(self, imp_create):
        """Creation des nouvelles lignes de salaire."""

        _logger.info(f"data : {imp_create}")
        _logger.info("Start Creer nouvelles lignes ..............................")
        elts = []
        for line in imp_create:
            elts.append(self.env["opsol_topnett.imp_salaire_line"].create(line))
        for elt in elts:
            elt.generate_payslip()
        _logger.info("end of pipeline!")

    def mettre_a_jour_line(self, update_salaire):
        """Mise a jour des importation salaire."""
        _logger.info(f"data : {update_salaire}")
        _logger.info("Start update existing products..............................")
        ids = []
        for _id, vals in update_salaire:
            self.env["opsol_topnett.imp_salaire_line"].browse(_id).update(vals)
            ids.append(_id)
        records = self.env["opsol_topnett.imp_salaire_line"].browse(ids)
        records.mapped('bulletin_id').action_payslip_cancel()
        records.mapped('bulletin_id').unlink()
        records.generate_payslip()
        _logger.info("end of pipeline!")

    def execute_load_employee(self, document):
        # load employee
        url = document.raw
        datas = self.file_to_dict(url)
        transformed = self.transform_employee(datas)
        transformed = self.update_employee(transformed)

    def execute_load_salaire(self, document):
        # load salaire
        url = document.raw
        datas = self.file_to_dict(url)
        transformed = self.transform(datas)
        transformed = self.transform2(transformed)
        result = self.split_nouveau_existant(transformed)
        result1 = self.creer_line(result['news'])
        result2 =  self.mettre_a_jour_line(result['exist'])
