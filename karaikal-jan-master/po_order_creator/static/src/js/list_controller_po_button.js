/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { ScanInputDialog } from "./scan_input_dialog";

patch(ListController.prototype, {
    get isPurchaseOrderList() {
        const resModel = this.props?.resModel || this.model?.root?.resModel;
        return resModel === "purchase.order";
    },

    onPoCustomListButtonClick() {
        this.dialogService.add(ScanInputDialog);
    },
});
