# -*- coding: utf-8 -*-
from xml.etree import ElementTree as ET
import base64
import contextlib
import io
from datetime import datetime

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
    summary_pay = fields.Html(
        string='Resume du Lot',
        compute="compute_info_cotisation"
    )

    @api.depends()

    def compute_contracts_ids(self):
        for rec in self:
            contracts = rec.slip_ids.mapped('contract_id')
            employes = rec.slip_ids.mapped('employee_id')
            importation_conges = rec.mapped('importation_sal_ids.conges_ids')
            structures = rec.mapped('slip_ids.struct_id')

            rec.contracts_ids = contracts
            rec.contracts_count = len(contracts)
            rec.employee_ids = employes
            rec.employee_count = len(employes)
            rec.importation_count = len(rec.importation_sal_ids)
            rec.imp_conge_count = len(importation_conges)
            rec.importation_con_ids = importation_conges
            rec.pay_struct_count = len(structures)
            rec.structure_ids = structures

    def compute_info_cotisation(self):
        for rec in self:
            first_day_of_year = datetime.strptime(f"{rec.date_start.year}-01-01", "%Y-%m-%d")
            cumul_domain = [('date_start', '<=', rec.date_start), ('date_start', '>=', first_day_of_year)]
            cumul_lot = self.env["hr.payslip.run"].search(cumul_domain)

            lines = rec.slip_ids.line_ids
            lines_cumul = cumul_lot.mapped('slip_ids.line_ids')

            effectif = len(rec.slip_ids.mapped('employee_id'))
            assur = round(sum(lines.filtered(lambda x: x.code == 'ASSUR_EMP').mapped('total')), 2)
            car = round(sum(lines.filtered(lambda x: x.code == 'CAR_EMP').mapped('total')), 2)
            ccss = round(sum(lines.filtered(lambda x: x.code == 'CCSS_EMP').mapped('total')), 2)

            cumul_assur = round(sum(lines_cumul.filtered(lambda x: x.code == 'ASSUR_EMP').mapped('total')), 2) if lines_cumul else 0
            cumul_car = round(sum(lines_cumul.filtered(lambda x: x.code == 'CAR_EMP').mapped('total')), 2) if lines_cumul else 0
            cumul_ccss = round(sum(lines_cumul.filtered(lambda x: x.code == 'CCSS_EMP').mapped('total')), 2) if lines_cumul else 0
            
            ccss_total = round(sum(lines.filtered(lambda x: x.code == 'CCSS').mapped('total')), 2)
            car_total = round(sum(lines.filtered(lambda x: x.code == 'CAR').mapped('total')), 2)
            
            gross = round(sum(lines.filtered(lambda x: x.code == 'GROSS').mapped('total')), 2)
            base_ccss = round(sum(lines.filtered(lambda x: x.code == 'BASE_CCSS').mapped('total')), 2)
            base_car = round(sum(lines.filtered(lambda x: x.code == 'BASE_CAR').mapped('total')), 2)
            base_assur = round(sum(lines.filtered(lambda x: x.code == 'BASE_CRMCTA').mapped('total')), 2)

            rate_ccss = round(ccss / base_ccss * 100 if base_ccss else 0, 2)
            rate_car = round(car / base_car * 100 if base_car else 0, 2)
            rate_assur = round(assur / base_assur * 100 if base_assur else 0, 2)
            summary_pay = f"""
                <div>
                    <table class="table table-bordered table-dark" style="width: 100%;">
                        <colgroup>
                            <col style="width: 40%;" />
                            <col style="width: 20%;" />
                            <col style="width: 20%;" />
                            <col style="width: 20%;" />
                        </colgroup>
                        <thead>
                            <th>CALCUL DES COTISATIONS</th>
                            <th>C.C.S.S</th>
                            <th>C.A.R</th>
                            <th>Assurance chomage</th>
                        </thead>
                        <tbody>
                            <tr>
                                <td colspan="4">DECLARATION DES SALAIRES DU MOIS DE : {self.name}</td>
                            </tr>
                            <tr>
                                <td></td>
                                <td></td>
                                <td></td>
                                <td></td>
                            </tr>
                            <tr>
                                <td>REMUNERATION BRUTES</td>
                                <td class="text-end">{gross}</td>
                                <td class="text-end">{gross}</td>
                                <td class="text-end">{gross}</td>
                            </tr>
                            <tr>
                                <td>DEPASSEMENTS</td>
                                <td class="text-end">0.0</td>
                                <td class="text-end">0.0</td>
                                <td class="text-end">0.0</td>
                            </tr>
                            <tr>
                                <td>SALAIRES SOUMIS A COTISATIONS</td>
                                <td class="text-end">{base_ccss}</td>
                                <td class="text-end">{base_car}</td>
                                <td class="text-end">{base_assur}</td>
                            </tr>
                            <tr>
                                <td>TAUX APPLIQUES</td>
                                <td class="text-end">{rate_ccss}</td>
                                <td class="text-end">{rate_car}</td>
                                <td class="text-end">{rate_assur}</td>
                            </tr>
                            <tr>
                                <td><br/></td>
                                <td></td>
                                <td></td>
                                <td></td>
                            </tr>
                            <tr>
                                <td><br/></td>
                                <td></td>
                                <td></td>
                                <td></td>
                            </tr>
                            <tr>
                                <td>COTISATION DU MOIS</td>
                                <td class="text-end">{ccss}</td>
                                <td class="text-end">{car}</td>
                                <td class="text-end">{assur}</td>
                            </tr>
                             <tr>
                                <td>TOTAUX CUMULES</td>
                                <td class="text-end">{cumul_ccss}</td>
                                <td class="text-end">{cumul_car}</td>
                                <td class="text-end">{cumul_assur}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            """
            rec.update({
                'ass_chomage': assur, 'ass_car': car, 'ass_ccss': ccss,
                'effectif': effectif, 'summary_pay': summary_pay
            })

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

    def action_open_structures(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("hr_payroll.action_view_hr_payroll_structure_list_form")
        action['domain'] = [('id', 'in', self.structure_ids.ids)]
        if self.pay_struct_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.structure_ids[0].id
            if 'views' in action:
                action['views'] = [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form']
        return action

    def get_tag_from_code(self, code_conge):
        TAG_CONGE = {'CP': 'congesPayes', 'AT': 'accidentTravail', 'MAL': 'maladie', 'CSS': 'congesSansSolde'}
        return TAG_CONGE.get(code_conge, "")

    def action_recompute_payslip(self):
        for rec in self:
            rec.slip_ids.compute_sheet()

    def action_reload_and_recompute_payslip(self):
        for rec in self:
            rec.slip_ids._compute_input_line_ids()
            rec.slip_ids.compute_sheet()

    def launch_genxml_wiz(self):
        self.ensure_one()
        company = self.env.company
        lines = self.slip_ids.line_ids
        imp_sals = self.env["opsol_topnett.imp_salaire_line"].search([('lot_id', '=', self.id)])

        declaration = ET.Element("declaration")
        declaration.set('xmlns', "http://www.caisses-sociales.mc/DSM/2.0")
        declaration.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        declaration.set('xsi:schemaLocation', "http://www.caisses-sociales.mc/DSM/2.0 http://www.caisses-sociales.mc/DSM/2.0/dsm.xsd")

        # Ajout des assiettes
        assiettes = ET.SubElement(declaration, "assiettes")
        ass_assur = ET.SubElement(assiettes, 'AssuranceChomage')
        ass_car = ET.SubElement(assiettes, 'CAR')
        ass_ccss = ET.SubElement(assiettes, 'CCSS')

        lines = self.slip_ids.line_ids
        base_ccss = round(sum(lines.filtered(lambda x: x.code == 'BASE_CCSS').mapped('total')), 2)
        base_car = round(sum(lines.filtered(lambda x: x.code == 'BASE_CAR').mapped('total')), 2)
        base_assur = round(sum(lines.filtered(lambda x: x.code == 'BASE_CRMCTA').mapped('total')), 2)
        ass_assur.text = f"{base_assur}"
        ass_car.text = ass_assur.text = f"{base_car}"
        ass_ccss.text = ass_assur.text = f"{base_ccss}"

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
            affiliationAC.text = "Oui" if contract.affiliation_ac else "Non"
            affiliationRC = ET.SubElement(salarie, 'affiliationRC')
            affiliationRC.text = "Oui" if contract.affiliation_rc else "Non"
            affiliationCAR = ET.SubElement(salarie, 'affiliationCAR')
            affiliationCAR.text = "Oui" if contract.affiliation_car else "Non"
            dateNaissance = ET.SubElement(salarie, 'dateNaissance')
            dateNaissance.text = emp.birthday.strftime(DATE_FORMAT)
            administrateurSalarie = ET.SubElement(salarie, 'administrateurSalarie')
            administrateurSalarie.text = "Oui" if contract.administrateur_salarie else "Non"
            teletravail = ET.SubElement(salarie, 'teletravail')
            teletravail.text = "Oui" if contract.teletravail else "Non"
            tempsPartiel = ET.SubElement(salarie, 'tempsPartiel')
            tempsPartiel.text = "Oui" if contract.temps_partiel else "Non"
            if contract.teletravail:
                paysTeletravail = ET.SubElement(salarie, 'paysTeletravail')
                paysTeletravail.text = f"{contract.teletravail_country_id and contract.teletravail_country_id.name or ''}"

            # renumeration
            remuneration = ET.SubElement(salarie, "remuneration")
            salaireBrut = ET.SubElement(remuneration, "salaireBrut")
            heuresTotales = ET.SubElement(remuneration, "heuresTotales")
            baseCCSS = ET.SubElement(remuneration, "baseCCSS")
            baseCAR = ET.SubElement(remuneration, "baseCAR")
            baseCMRCTA = ET.SubElement(remuneration, "baseCMRCTA")
            baseCMRCTB = ET.SubElement(remuneration, "baseCMRCTB")
            
            v_salaire_brut = sum(_lines.filtered(lambda x: x.code == 'GROSS').mapped(lambda x: x.amount))
            v_base_ccss = sum(_lines.filtered(lambda x: x.code == 'BASE_CCSS').mapped(lambda x: x.amount))
            v_base_car = sum(_lines.filtered(lambda x: x.code == 'BASE_CAR').mapped(lambda x: x.amount))
            v_base_assur = sum(_lines.filtered(lambda x: x.code == 'BASE_CRMCTA').mapped(lambda x: x.amount))

            salaireBrut.text = f"{v_salaire_brut}"
            heuresTotales.text = f"{imp_sal.h_travailles}"
            baseCCSS.text = f"{v_base_ccss}"
            baseCAR.text = f"{v_base_car}"
            baseCMRCTA.text = f"{v_base_assur}"
            baseCMRCTB.text = f"{5504}"

            # evenements
            prime_montant = imp_sal and imp_sal.prime or 0
            evenements = ET.SubElement(salarie, "evenements")
            delEvent = True
            
            # ==> Conge payes
            for conge in imp_sal.conges_ids:
                delEvent = False
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
                delEvent = False
                entree_salarie = ET.SubElement(evenements, "entreeDuSalarie")
                es_dateDebut = ET.SubElement(entree_salarie, "dateDebut")
                es_dateDebut.text = contract.date_start.strftime(DATE_FORMAT)

            # ==> Entree du salarie
            if contract and contract.date_start_2 and contract.date_start_2.strftime("%Y-%m") == period:
                delEvent = False
                entree_salarie = ET.SubElement(evenements, "entreeDuSalarie")
                es_dateDebut = ET.SubElement(entree_salarie, "dateDebut")
                es_dateDebut.text = contract.date_start_2.strftime(DATE_FORMAT)

            # ==> Sortie du salarie
            date_depart_adm = contract and contract.date_depart_administratif or None
            date_depart_phy = contract and contract.date_depart_physique or None
            if date_depart_phy or date_depart_adm:
                delEvent = False
                sortie_salarie = ET.SubElement(evenements, "sortieDuSalarie")
                es_dateADM = ET.SubElement(sortie_salarie, "dateSortieAdministrative")
                es_dateADM.text = contract.date_depart_administratif.strftime(DATE_FORMAT)
                es_datePHY = ET.SubElement(sortie_salarie, "dateSortiePhysique")
                es_datePHY.text = contract.date_depart_physique.strftime(DATE_FORMAT)

            # ==> Préavis
            if contract.date_depart_preavis or contract.date_fin_preavis:
                delEvent = False
                preavis = ET.SubElement(evenements, "preavis")
                pr_dateDebut = ET.SubElement(preavis, "dateDebut")
                pr_dateDebut.text = contract.date_depart_preavis.strftime(DATE_FORMAT)
                es_dateFin = ET.SubElement(preavis, "dateFin")
                es_dateFin.text = contract.date_fin_preavis.strftime(DATE_FORMAT)
            
            if prime_montant != 0:
                delEvent = False
                prime = ET.SubElement(evenements, "prime")
                montant = ET.SubElement(prime, "montant")
                montant.text = f"{prime_montant}"

            if delEvent:
                salarie.remove(evenements)

        
        # ajoute employeur et periode
        employeur = ET.SubElement(declaration, "employeur")
        periode = ET.SubElement(declaration, "periode")
        employeur.text = f"{company and company.code_employeur or 9999}"
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
