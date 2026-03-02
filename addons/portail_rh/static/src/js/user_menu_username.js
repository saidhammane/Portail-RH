/** @odoo-module **/

import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { escape } from "@web/core/utils/strings";

function currentUserItem(env) {
    const userName = env.services.user.name || "";
    return {
        type: "item",
        id: "current_user_name",
        description: markup(
            `<span class="fw-semibold text-body">${escape(_t("Utilisateur"))}: ${escape(userName)}</span>`
        ),
        callback: () => {},
        sequence: 5,
    };
}

registry.category("user_menuitems").add("current_user_name", currentUserItem);
