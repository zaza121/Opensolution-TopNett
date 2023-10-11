# -*- coding: utf-8 -*-
from xml.etree import ElementTree as ET
import base64
import contextlib
import io

from odoo import api, fields, models
HEADER = b"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE declaration PUBLIC "-//CSM//DSM 2.0//FR" "http://www.caisses-sociales.mc/DSM/2.0/dsm.dtd">
"""


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def launch_genxml_wiz(self):
        self.ensure_one()
        lines = self.slip_ids.line_ids

        declaration = ET.Element("declaration")
        declaration.set('xmlns', "http://www.caisses-sociales.mc/DSM/2.0")
        declaration.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        declaration.set('xsi:schemaLocation', "http://www.caisses-sociales.mc/DSM/2.0 http://www.caisses-sociales.mc/DSM/2.0/dsm.xsd")
        assiettes = ET.SubElement(declaration, "assiettes")
        
        # Ajout des assiettes
        ass_assur = ET.SubElement(assiettes, 'AssuranceChomage')
        ass_car = ET.SubElement(assiettes, 'CAR')
        ass_ccss = ET.SubElement(assiettes, 'CCSS')

        ass_assur.text = f"{sum(lines.filtered(lambda x: x.code == 'ASSUR').mapped('total'))}"
        ass_car.text = ass_assur.text = f"{sum(lines.filtered(lambda x: x.code == 'CAR').mapped('total'))}"
        ass_ccss.text = ass_assur.text = f"{sum(lines.filtered(lambda x: x.code == 'CCSS').mapped('total'))}"

        # ajoute les effectifs a declarer
        effectif = ET.SubElement(declaration, "effectif")

        for emp in self.slip_ids.mapped("employee_id"):
            slip = self.slip_ids.filtered(lambda x: x.employee_id.id == emp.id)
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
            dateNaissance.text = emp.birthday.strftime("%Y-%m-%d")
            administrateurSalarie = ET.SubElement(salarie, 'administrateurSalarie')
            administrateurSalarie.text = "Oui" if emp.administrateur_salarie else "Non"

            # renumeration
            remuneration = ET.SubElement(salarie, "remuneration")
            salaireBrut = ET.SubElement(remuneration, "salaireBrut")
            salaireBrut.text = 0

            # evenements
            evenements = ET.SubElement(salarie, "evenements")
            congesPayes = ET.SubElement(evenements, "congesPayes")
            
            prime = ET.SubElement(evenements, "prime")
            montant = ET.SubElement(prime, "montant")
            montant.text = "512.9"


        # ajoute employeur et periode
        employeur = ET.SubElement(declaration, "employeur")
        periode = ET.SubElement(declaration, "periode")
        employeur.text = f"{len(self.slip_ids.mapped('employee_id'))}"
        periode.text = self.date_start.strftime("%Y-%m") or ""

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
            'name': "cotisation.xml"
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'opsol_topnett.genxml_cot_wiz',
            'view_mode': 'form',
            'res_id': wiz.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
