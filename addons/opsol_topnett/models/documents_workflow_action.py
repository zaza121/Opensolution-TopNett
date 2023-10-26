# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import logging

from odoo import api, fields, models
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class WorkflowTagAction(models.Model):
    _inherit = "documents.workflow.action"

    action = fields.Selection(selection_add=[('call_api', "Call Api")], ondelete={'call_api': 'set default'})

    def file_to_dict(url):
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

    def transform_employee(data_employee: list):
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


    def execute_tag_action(self, document):
        if self.action == "call_api":
            # load employee
            url = document.create_share_id.full_url
            datas = self.file_to_dict(url)
            transformed = self.transform_employee(datas)
            raise UserError(transformed)

        else:
            return super(WorkflowTagAction, self).execute_tag_action(document)
