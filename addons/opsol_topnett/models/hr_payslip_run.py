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
    importation_count = fields.Integer(
        string='Nombres d\'importations',
        compute="compute_contracts_ids"
    )
    importation_sal_ids = fields.One2many(
        comodel_name='opsol_topnett.imp_salaire_line',
        inverse_name='lot_id',
        string='Importations de salaire',
    )
    imp_conge_count = fields.Integer(
        string='Nombres de conges',
        compute="compute_contracts_ids"
    )
    importation_con_ids = fields.One2many(
        comodel_name='opsol_topnett.imp_conge',
        compute="compute_contracts_ids",
        string='Importations de conges',
    )
    pay_struct_count = fields.Integer(
        string='Structures du lot',
        compute="compute_contracts_ids"
    )
    structure_ids = fields.One2many(
        comodel_name='hr.payroll.structure',
        compute="compute_contracts_ids",
        string='Importations de conges',
    )

    def compute_contracts_ids(self):
        for rec in self:
            contracts = rec.slip_ids.mapped('contract_id')
            employes = rec.slip_ids.mapped('employee_id')
            importation_conges = rec.mapped('importation_sal_ids.conges_ids')

            rec.contracts_ids = contracts
            rec.contracts_count = len(contracts)
            rec.employee_ids = employes
            rec.employee_count = len(employes)
            rec.importation_count = len(rec.importation_sal_ids)
            rec.imp_conge_count = len(importation_conges)
            rec.importation_con_ids = importation_conges

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

    def action_open_importation(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("opsol_topnett.action_opsol_topnett_imp_salaire_line")
        action['domain'] = [('id', 'in', self.importation_sal_ids.ids)]
        action['context'] = {}
        return action

    def action_open_imp_conges(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("opsol_topnett.action_opsol_topnett_imp_conge")
        action['domain'] = [('id', 'in', self.importation_con_ids.ids)]
        action['context'] = {}
        return action

    def get_tag_from_code(self, code_conge):
        TAG_CONGE = {'CP': 'congesPayes', 'AT': 'Accident du travail', 'MAL': 'Maladie', 'CSS': 'Congés sans solde'}
        return TAG_CONGE.get(code_conge, "")

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
            contract = slip.contract_id
            _lines = slip.line_ids
            salarie = ET.SubElement(effectif, 'salarie')
            period = imp_sal.date_salaire and imp_sal.date_salaire.strftime("%Y-%m")
            
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
            
            # ==> Conge payes
            for conge in imp_sal.conges_ids:
                tag_code = self.get_tag_from_code(conge.code_conge)
                if not tag_code:
                    continue
                congesPayes = ET.SubElement(evenements, tag_code)
                DateDebut = ET.SubElement(congesPayes, "dateDebut")
                DateFin = ET.SubElement(congesPayes, "dateFin")
                slip = slip[0] if len(slip) > 1 else slip
                data_conge = conge.get_conge_data(slip.date_from, slip.date_to, DATE_FORMAT)
                DateDebut.text = data_conge['date_start']
                DateFin.text = data_conge['date_end']
                if data_conge['nb_heures']:
                    heures = ET.SubElement(congesPayes, "heures")
                    heures.text = data_conge['nb_heures']

            # ==> Entree du salarie
            if contract and contract.date_start and contract.date_start.strftime("%Y-%m") == period:
                entree_salarie = ET.SubElement(evenements, "Entree du salarié")
                es_dateDebut = ET.SubElement(entree_salarie, "dateDebut")
                es_dateDebut.text = contract.date_start.strftime(DATE_FORMAT)

            # ==> Entree du salarie
            if contract and contract.date_start_2 and contract.date_start_2.strftime("%Y-%m") == period:
                entree_salarie = ET.SubElement(evenements, "Entree du salarié")
                es_dateDebut = ET.SubElement(entree_salarie, "dateDebut")
                es_dateDebut.text = contract.date_start_2.strftime(DATE_FORMAT)

            # ==> Sortie du salarie
            date_depart_adm = contract and contract.date_depart_administratif or None
            date_depart_phy = contract and contract.date_depart_physique or None
            if date_depart_phy or date_depart_adm:
                sortie_salarie = ET.SubElement(evenements, "Sortie du salarie")
                es_dateADM = ET.SubElement(sortie_salarie, "dateSortieAdministrative")
                es_dateADM.text = contract.date_start.strftime(DATE_FORMAT)
                es_datePHY = ET.SubElement(sortie_salarie, "dateSortiePhysique")
                es_datePHY.text = contract.date_depart_physique.strftime(DATE_FORMAT)

            # ==> Préavis
            if contract.date_depart_preavis or contract.date_fin_preavis:
                preavis = ET.SubElement(evenements, "Preavis")
                pr_dateDebut = ET.SubElement(preavis, "dateDebut")
                pr_dateDebut.text = contract.date_depart_preavis.strftime(DATE_FORMAT)
                es_dateFin = ET.SubElement(preavis, "dateFin")
                es_dateFin.text = contract.date_fin_preavis.strftime(DATE_FORMAT)
            
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
