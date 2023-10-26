# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


class WorkflowTagAction(models.Model):
    _inherit = "documents.workflow.action"

    action = fields.Selection(selection_add=[('call_api', "Call Api")], ondelete={'call_api': 'set default'})

    def execute_tag_action(self, document):
        if self.action == "call_api":
            raise Warning("Hello")
        else:
            return super(WorkflowTagAction, self).execute_tag_action(document)
