# -*- coding: utf-8 -*-
from xml.etree import ElementTree as ET
import base64
import contextlib
import io

from odoo import api, fields, models
HEADER = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE declaration PUBLIC "-//CSM//DSM 2.0//FR" "http://www.caisses-sociales.mc/DSM/2.0/dsm.dtd">
"""
DATE_FORMAT = "%Y-%m-%d"


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    ass_chomage = fields.Float(
        string='Assiette Assurance Chomage',
        compute="compute_info_cotisation"
    )
    ass_car = fields.Float(
        string='Assiette CAR',
        compute="compute_info_cotisation"
    )
    ass_ccss = fields.Float(
        string='Assiette CCSS',
        compute="compute_info_cotisation"
    )
    effectif = fields.Integer(
        string='Effectif',
        compute="compute_info_cotisation"
    )

    contracts_count = fields.Integer(
        string='Nombre de contrats',
        compute="compute_contracts_ids"
    )
    contracts_ids = fields.One2many(
        comodel_name='hr.contract',
        string='Contrats du lot',
        compute="compute_contracts_ids"
    )
    employee_count = fields.Integer(
        string='Nombres d\'employes',
        compute="compute_contracts_ids"
    )
    employee_ids = fields.One2many(
        comodel_name='hr.employee',
        string='Employes du lot',
        compute="compute_contracts_ids"
    )

    def compute_contracts_ids(self):
        for rec in self:
            contracts = rec.slip_ids.mapped('contract_id')
            employes = rec.slip_ids.mapped('employee_id')
            rec.contracts_ids = contracts
            rec.contracts_count = len(contracts)
            rec.employee_ids = employes
            rec.employee_count = len(employes)

    def compute_info_cotisation(self):
        for rec in self:
            lines = rec.slip_ids.line_ids
            effectif = len(rec.slip_ids.mapped('employee_id'))
            ass_assur = sum(lines.filtered(lambda x: x.code == 'ASSUR').mapped('total'))
            ass_car = sum(lines.filtered(lambda x: x.code == 'CAR').mapped('total'))
            ass_ccss = sum(lines.filtered(lambda x: x.code == 'CCSS').mapped('total'))
            rec.update({'ass_chomage': ass_assur, 'ass_car': ass_car, 'ass_ccss': ass_ccss, 'effectif': effectif})

    def action_open_contracts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_contract.action_hr_contract")
        action['domain'] = [('id', 'in', self.contracts_ids.ids)]
        return action

    def action_open_employees(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr.open_view_employee_list_my")
        action['domain'] = [('id', 'in', self.employee_ids.ids)]
        return action

    def launch_genxml_wiz(self):
        self.ensure_one()
        lines = self.slip_ids.line_ids
        imp_sals = self.env["opsol_topnett.imp_salaire_line"].search([('lot_id', '=', self.id)])

        declaration = ET.Element("declaration")
        declaration.set('xmlns', "http://www.caisses-sociales.mc/DSM/2.0")
        declaration.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        declaration.set('xsi:schemaLocation', "http://www.caisses-sociales.mc/DSM/2.0 http://www.caisses-sociales.mc/DSM/2.0/dsm.xsd")

        # ajoute employeur et periode
        employeur = ET.SubElement(declaration, "employeur")
        periode = ET.SubElement(declaration, "periode")
        employeur.text = f"9999"
        periode.text = self.date_start.strftime("%Y-%m") or ""

        # Ajout des assiettes
        assiettes = ET.SubElement(declaration, "assiettes")
        ass_assur = ET.SubElement(assiettes, 'AssuranceChomage')
        ass_car = ET.SubElement(assiettes, 'CAR')
        ass_ccss = ET.SubElement(assiettes, 'CCSS')

        ass_assur.text = f"{round(self.ass_chomage)}"
        ass_car.text = ass_assur.text = f"{round(self.ass_car)}"
        ass_ccss.text = ass_assur.text = f"{round(self.ass_ccss)}"

        # ajoute les effectifs a declarer
        effectif = ET.SubElement(declaration, "effectif")

        for emp in self.slip_ids.mapped("employee_id").sorted(lambda x: x.name):
            slip = self.slip_ids.filtered(lambda x: x.employee_id.id == emp.id)
            imp_sal = imp_sals.filtered(lambda x: x.employee_id.id == emp.id)
            _lines = slip.line_ids
            salarie = ET.SubElement(effectif, 'salarie')
            
            matricule = ET.SubElement(salarie, 'matricule')
            matricule.text = emp.registration_number
            nom = ET.SubElement(salarie, 'nom')
            nom.text = emp.nom
            prenom = ET.SubElement(salarie, 'prenom')
            prenom.text = emp.prenom
            affiliationAC = ET.SubElement(salarie, 'affiliationAC')
            affiliationAC.text = "Oui" if emp.affiliation_ac else "Non"
            affiliationRC = ET.SubElement(salarie, 'affiliationRC')
            affiliationRC.text = "Oui" if emp.affiliation_rc else "Non"
            affiliationCAR = ET.SubElement(salarie, 'affiliationCAR')
            affiliationCAR.text = "Oui" if emp.affiliation_car else "Non"
            teletravail = ET.SubElement(salarie, 'teletravail')
            teletravail.text = "Oui" if emp.teletravail else "Non"
            dateNaissance = ET.SubElement(salarie, 'dateNaissance')
            dateNaissance.text = emp.birthday.strftime(DATE_FORMAT)
            administrateurSalarie = ET.SubElement(salarie, 'administrateurSalarie')
            administrateurSalarie.text = "Oui" if emp.administrateur_salarie else "Non"

            # renumeration
            remuneration = ET.SubElement(salarie, "remuneration")
            salaireBrut = ET.SubElement(remuneration, "salaireBrut")
            heuresTotales = ET.SubElement(remuneration, "heuresTotales")
            baseCCSS = ET.SubElement(remuneration, "baseCCSS")
            baseCAR = ET.SubElement(remuneration, "baseCAR")
            baseCMRCTA = ET.SubElement(remuneration, "baseCMRCTA")
            baseCMRCTB = ET.SubElement(remuneration, "baseCMRCTB")
            
            v_salaire_brut = sum(_lines.filtered(lambda x: x.code == 'GROSS').mapped(lambda x: x.amount))
            salaireBrut.text = f"{round(v_salaire_brut)}"
            heuresTotales.text = f"{round(imp_sal.h_travailles + imp_sal.h_complementaires)}"
            baseCCSS.text = f"{round(v_salaire_brut)}"
            baseCAR.text = f"{round(5504)}"
            baseCMRCTA.text = f"{round(5504)}"
            baseCMRCTB.text = f"{round(5504)}"

            # evenements
            prime_montant = imp_sal and imp_sal.prime or 0
            evenements = ET.SubElement(salarie, "evenements")
            for conge in imp_sal.conges_ids:
                congesPayes = ET.SubElement(evenements, "congesPayes")
                DateDebut = ET.SubElement(congesPayes, "dateDebut")
                DateFin = ET.SubElement(congesPayes, "dateFin")
                heures = ET.SubElement(congesPayes, "heures")
                data_conge = conge.get_conge_data(DATE_FORMAT)
                DateDebut.text = data_conge['date_start']
                DateFin.text = data_conge['date_end']
                heures.text = data_conge['nb_heures']
            
            if prime_montant != 0:
                prime = ET.SubElement(evenements, "prime")
                montant = ET.SubElement(prime, "montant")
                montant.text = f"{prime_montant}"

        # Converting the xml data to byte object,
        # for allowing flushing data to file 
        # stream

        # Indentation
        tree = ET.ElementTree(declaration)
        ET.indent(tree, '  ')

        b_xml = ET.tostring(declaration)
        b_xml = HEADER + b_xml
        b = base64.b64encode(b_xml) # bytes

        wiz = self.env["opsol_topnett.genxml_cot_wiz"].create({
            'lot_id': self.id,
            'data': b,
            'name': f"{self.name.lower().replace(' ', '_').replace('/', '')}_cotisation.xml",
            'description': """
                Trouvez ci dessous le fichier de declaration des caisses sociales pour le lot %s""" % self.name
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'opsol_topnett.genxml_cot_wiz',
            'view_mode': 'form',
            'res_id': wiz.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
