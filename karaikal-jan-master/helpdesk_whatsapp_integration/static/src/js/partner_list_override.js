/** @odoo-module **/

import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { makeActionAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { useService } from "@web/core/utils/hooks";

patch(PartnerList.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    async quickCreateCustomer() {
        const viewResult = await this.orm.searchRead(
            "ir.ui.view",
            [["name", "=", "res.partner.pos.quick.create"]],
            ["id"],
            { limit: 1 }
        );

        const view_id = viewResult && viewResult.length > 0 ? viewResult[0].id : false;

        if (!view_id) {
            this.notification.add("Custom view not found", { type: "danger" });
            return;
        }

        const record = await makeActionAwaitable(
            this.pos.action,
            {
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: undefined,
                views: [[view_id, "form"]],
                target: "new",
                context: {
                    default_customer_rank: 1,
                },
            },
            {
                props: { resId: undefined },
                additionalContext: {},
            }
        );
        
        if (record && record.config && record.config.resIds && record.config.resIds.length > 0) {
            const partners = await this.pos.data.read("res.partner", record.config.resIds);
            if (partners && partners.length > 0) {
                this.clickPartner(partners[0]);
            }
        }
    },
});