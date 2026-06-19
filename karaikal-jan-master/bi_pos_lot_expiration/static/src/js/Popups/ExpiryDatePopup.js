import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";


export class ExpiryDatePopup extends Component {
    static template = "bi_pos_lot_expiration.ExpiryDatePopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        close: Function,
        alert_date: { type: String, optional: true }  
    };

    static defaultProps = {
        confirmText: _t("Ok"),
        title: '',
        body: '',
        cancelText: _t("Cancel"),

    };

    setup() {
        super.setup();
    };

    close() {
        this.props.close();
    };

}