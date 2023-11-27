/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { localization as l10n } from "@web/core/l10n/localization";
import { registry } from "@web/core/registry";
import * as documentsHooks from "@documents/views/hooks";

import { useBus, useService } from "@web/core/utils/hooks";
import { escape, sprintf } from "@web/core/utils/strings";
import { memoize } from "@web/core/utils/functions";
import { useSetupView } from "@web/views/view_hook";
import { insert } from "@mail/model/model_field_command";
import { PdfManager } from "@documents/owl/components/pdf_manager/pdf_manager";
import { x2ManyCommands } from "@web/core/orm_service";
import { ShareFormViewDialog } from "@documents/views/helper/share_form_view_dialog";

const { EventBus, onWillStart, markup, reactive, useComponent, useEnv, useRef, useSubEnv } = owl;


patch(documentsHooks, 'opsol_topnett.newdocumentsHooks', {

	useTriggerRule() {
	    const env = useEnv();
	    const orm = useService("orm");
	    const notification = useService("notification");
	    const action = useService("action");
	    return {
	        triggerRule: async (documentIds, ruleId, preventReload = false) => {
	            const result = await orm.call("documents.workflow.rule", "apply_actions", [[ruleId], documentIds]);

	            if (result && typeof result === "object") {
	                if (result.hasOwnProperty("message")) {
	                    
	                	notification.add(result['message'], {title: "Infos Importation", type: "info"});

	                }else if (result.hasOwnProperty("warning")) {
	                    notification.add(
	                        markup(`<ul>${result["warning"]["documents"].map((d) => `<li>${escape(d)}</li>`).join("")}</ul>`),
	                        {
	                            title: result["warning"]["title"],
	                            type: "danger",
	                        }
	                    );
	                    if (!preventReload) {
	                        await env.model.load();
	                    }
	                } else if (!preventReload) {
	                    await action.doAction(result, {
	                        onClose: async () => await env.model.load(),
	                    });
	                    return;
	                }
	            } else if (!preventReload) {
	                await env.model.load();
	            }
	        },
	    };
	}
});


