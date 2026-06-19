/** @odoo-module **/

import { Component, useRef, useState, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class ScanInputDialog extends Component {
    static template = "po_order_creator.ScanInputDialog";
    static components = { Dialog };
    static props = {
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.inputRef = useRef("input");
        this.state = useState({ value: "", busy: false });
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }

    async processScan(value) {
        value = (value || "").trim();
        if (!value) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await this.orm.call("account.move", "action_confirm", [value]);
            const message = result?.message || "Done";
            const level = result?.level || "success";
            this.notification.add(message, { type: level });
            this.state.value = "";

            const action = result?.action;
            if (action && typeof action === "object" && typeof action.type === "string") {
                await this.action.doAction(action);
            }
        } catch (e) {
            const message = e?.data?.message || e?.message || "Scan failed";
            this.notification.add(message, { type: "danger" });
        } finally {
            this.state.busy = false;
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        }
    }

    async onKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        if (this.state.busy) {
            return;
        }
        await this.processScan(this.state.value);
    }

    async onConfirm() {
        if (this.state.busy) {
            return;
        }
        await this.processScan(this.state.value);
    }
}

