import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { EditListPopup } from "@point_of_sale/app/store/select_lot_popup/select_lot_popup";
import { WarningMessagePopup } from "@bi_pos_lot_expiration/js/Popups/WarningMessagePopup";
import { NoLotAvailable } from "@bi_pos_lot_expiration/js/Popups/NoLotAvailable";
import { ExpiryDatePopup } from "@bi_pos_lot_expiration/js/Popups/ExpiryDatePopup";
const { DateTime } = luxon;
import {
    makeAwaitable,
    ask,
    makeActionAwaitable,
} from "@point_of_sale/app/store/make_awaitable_dialog";


patch(PosStore.prototype, {

    async processServerData() {
        await super.processServerData();
        let self = this;
        self.stock_lot = this.models["stock.lot"].getAll();
    },

    async editLots(product, packLotLinesToEdit) {
        if(!this.config.allow_expiry_warning && !this.config.restrict_creating_lot){
            const isAllowOnlyOneLot = product.isAllowOnlyOneLot();
            let canCreateLots = this.pickingType.use_create_lots || !this.pickingType.use_existing_lots;

            let existingLots = [];
            try {
                existingLots = await this.data.call(
                    "pos.order.line",
                    "get_existing_lots",
                    [this.company.id, product.id],
                    {
                        context: {
                            config_id: this.config.id,
                        },
                    }
                );
                if (!canCreateLots && (!existingLots || existingLots.length === 0)) {
                    this.dialog.add(AlertDialog, {
                        title: _t("No existing serial/lot number"),
                        body: _t(
                            "There is no serial/lot number for the selected product, and their creation is not allowed from the Point of Sale app."
                        ),
                    });
                    return null;
                }
            } catch (ex) {
                console.error("Collecting existing lots failed: ", ex);
                const confirmed = await ask(this.dialog, {
                    title: _t("Server communication problem"),
                    body: _t(
                        "The existing serial/lot numbers could not be retrieved. \nContinue without checking the validity of serial/lot numbers ?"
                    ),
                    confirmLabel: _t("Yes"),
                    cancelLabel: _t("No"),
                });
                if (!confirmed) {
                    return null;
                }
                canCreateLots = true;
            }

            const existingLotsName = existingLots.map((l) => l.name);
            const payload = await makeAwaitable(this.dialog, EditListPopup, {
                title: _t("Lot/Serial Number(s) Required"),
                name: product.display_name,
                isSingleItem: isAllowOnlyOneLot,
                array: packLotLinesToEdit,
                options: existingLotsName,
                customInput: canCreateLots,
                uniqueValues: product.tracking === "serial",
            });
            if (payload) {
                const modifiedPackLotLines = Object.fromEntries(
                    payload.filter((item) => item.id).map((item) => [item.id, item.text])
                );
                const newPackLotLines = payload
                    .filter((item) => !item.id)
                    .map((item) => ({ lot_name: item.text }));

                return { modifiedPackLotLines, newPackLotLines };
            } else {
                return null;
            }
        }
        else{
            var self = this;
            var lots = this.stock_lot;
            let is_exist = [];
            let not_exist = [];
            let lots1 = [];

            const isAllowOnlyOneLot = product.isAllowOnlyOneLot();
            let canCreateLots = this.pickingType.use_create_lots || !this.pickingType.use_existing_lots;

            let existingLots = [];
            try {
                existingLots = await this.data.call(
                    "pos.order.line",
                    "get_existing_lots",
                    [this.company.id, product.id],
                    {
                        context: {
                            config_id: this.config.id,
                        },
                    }
                );
                if (!canCreateLots && (!existingLots || existingLots.length === 0)) {
                    this.dialog.add(AlertDialog, {
                        title: _t("No existing serial/lot number"),
                        body: _t(
                            "There is no serial/lot number for the selected product, and their creation is not allowed from the Point of Sale app."
                        ),
                    });
                    return null;
                }
            } catch (ex) {

                console.error("Collecting existing lots failed: ", ex);
                const confirmed = await ask(this.dialog, {
                    title: _t("Server communication problem"),
                    body: _t(
                        "The existing serial/lot numbers could not be retrieved. \nContinue without checking the validity of serial/lot numbers ?"
                    ),
                    confirmLabel: _t("Yes"),
                    cancelLabel: _t("No"),
                });
                if (!confirmed) {
                    return null;
                }
                canCreateLots = true;
            }

            const existingLotsName = existingLots.map((l) => l.name);
            var payload = await makeAwaitable(this.dialog, EditListPopup, {
                title: _t("Lot/Serial Number(s) Required"),
                name: product.display_name,
                isSingleItem: isAllowOnlyOneLot,
                array: packLotLinesToEdit,
                options: existingLotsName,
                customInput: canCreateLots,
                uniqueValues: product.tracking === "serial",
            });

            if(this.config.allow_expiry_warning && this.config.restrict_creating_lot){
                if(product.tracking == 'serial'){
                    
                    const modifiedPackLotLines = Object.fromEntries(
                        payload.filter((item) => item.id).map((item) => [item.id, item.text])
                    );

                    const newPackLotLines = payload
                        .filter((item) => !item.id)
                        .map((item) => ({ lot_name: item.text }));
                    
                    var is_exist_1 = lots.filter(function(v) {
                        if (v.product_id){
                            if (v.product_id.id == product.id){
                                payload.forEach(function (array) {
                                    let today = new Date();
                                    let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                    let alert_date = v.alert_date
                                    if(v.name == array.text && current_date >= alert_date){
                                        is_exist.push(v)
                                     }
                                });
                                return is_exist;
                            }
                        }
                    });

                    lots.forEach(function (line){
                        if (line.product_id){
                            if (line.product_id.id == product.id){
                                lots1.push(line.name)
                            }
                        }
                    });

                    payload.forEach(function (array) {
                        if(!lots1.includes(array.text)){
                            not_exist.push(array)
                        }
                    });
                    
                    if (not_exist)
                        if(is_exist.length != 0 || not_exist.length != 0){
                            this.dialog.add(WarningMessagePopup, {
                                title: _t('Invalid Serial Number(s) or Expired'),
                                expiry_lot: is_exist,
                                message: not_exist
                            });
                        }
                    else{
                        return { modifiedPackLotLines, newPackLotLines };
                    }
                }

                if(product.tracking == 'lot'){
                    if (payload){
                        if(payload[0]){
                            var is_exist_val = lots.filter(function(v) {
                                if (v.product_id){
                                    if (v.product_id.id == product.id){
                                        return v.name == payload[0].text;
                                    }
                                }
                            });
                            if(is_exist_val.length != 0){
                                let today = new Date();
                                let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                let alert_date = is_exist_val[0].alert_date
                                if (!alert_date){
                                    alert_date = ""
                                }
                                if(alert_date){
                                    if ( current_date >= alert_date){
                                        this.dialog.add(ExpiryDatePopup, {
                                            title: _t('Expired Lot/Serial Number(s)'),
                                            alert_date: alert_date,
                                        });
                                    }else{
                                        if (payload) {
                                            const modifiedPackLotLines = Object.fromEntries(
                                                payload.filter((item) => item.id).map((item) => [item.id, item.text])
                                            );
                                            const newPackLotLines = payload
                                                .filter((item) => !item.id)
                                                .map((item) => ({ lot_name: item.text }));
                                            return { modifiedPackLotLines, newPackLotLines };
                                        } else {
                                            return null;
                                        }
                                    }
                                }else{
                                    if (payload) {
                                        const valid = lots.find((v) => v.name === payload[0].text && v.product_id && v.product_id.id === product.id);
                                        if (valid) {
                                            payload = payload.filter(function(item) {
                                                return item.text == valid.name;
                                            });
                                        }
                                        const modifiedPackLotLines = Object.fromEntries(
                                            payload.filter((item) => item.id).map((item) => [item.id, item.text])
                                        );
                                        const newPackLotLines = payload
                                            .filter((item) => !item.id)
                                            .map((item) => ({ lot_name: item.text }));
                                        return { modifiedPackLotLines, newPackLotLines };
                                    } else {
                                        return null;
                                    }
                                    
                                }
                            }else{
                                this.dialog.add(NoLotAvailable, {
                                    title: _t('Unmatched Lot/Serial Number(s)'),
                                });
                            }
                        }
                    }
                }
            }
            else if(this.config.allow_expiry_warning && !this.config.restrict_creating_lot){
                if(product.tracking == 'serial'){
                    const modifiedPackLotLines = Object.fromEntries(
                        payload.filter((item) => item.id).map((item) => [item.id, item.text])
                    );

                    const newPackLotLines = payload
                        .filter((item) => !item.id)
                        .map((item) => ({ lot_name: item.text }));
                    
                    var is_exist_1 = lots.filter(function(v) {
                        if (v.product_id){
                            if (v.product_id.id == product.id){
                                payload.forEach(function (array) {
                                    let today = new Date();
                                    let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                    let alert_date = v.alert_date
                                    if(v.name == array.text && current_date >= alert_date){
                                        is_exist.push(v)
                                     }
                                });
                                return is_exist;
                            }
                        }
                    });

                    lots.forEach(function (line){
                        if (line.product_id){
                            if (line.product_id.id == product.id){
                                lots1.push(line.name)
                            }
                        }
                    });

                    payload.forEach(function (array) {
                        if(!lots1.includes(array.text)){
                            not_exist.push(array)
                        }
                    });

                    if(is_exist.length != 0 || not_exist.length != 0){
                        this.dialog.add(WarningMessagePopup, {
                            title: _t('Invalid Serial Number(s) or Expired'),
                            expiry_lot: is_exist,
                            message: not_exist
                        });
                    }

                    return { modifiedPackLotLines, newPackLotLines };
                }
                if(product.tracking == 'lot'){
                    if(payload){
                        if(payload[0]){
                            const modifiedPackLotLines = Object.fromEntries(
                                payload.filter((item) => item.id).map((item) => [item.id, item.text])
                            );
                            const newPackLotLines = payload
                                .filter((item) => !item.id)
                                .map((item) => ({ lot_name: item.text }));

                            var is_exist_data = lots.filter(function(v) {
                                if (v.product_id){
                                    if (v.product_id.id == product.id){
                                        return v.name == payload[0].text;
                                    }
                                }
                            });
                            if(is_exist_data.length != 0){
                                let today = new Date();
                                let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                let alert_date = is_exist_data[0].alert_date
                                if(alert_date){
                                    if ( current_date >= alert_date){
                                        this.dialog.add(ExpiryDatePopup, {
                                            title: _t('Expired Lot/Serial Number(s)'),
                                            alert_date: alert_date,
                                        });
                                    }
                                }
                                return { modifiedPackLotLines, newPackLotLines };
                            }else{
                                this.dialog.add(NoLotAvailable, {
                                    title: _t('Unmatched Lot/Serial Number(s)'),
                                });
                                return { modifiedPackLotLines, newPackLotLines };
                            }
                        }
                    }
                }
            }
            else if(!this.config.allow_expiry_warning && this.config.restrict_creating_lot){
                if(product.tracking == 'serial'){
                    const modifiedPackLotLines = Object.fromEntries(
                        payload.filter((item) => item.id).map((item) => [item.id, item.text])
                    );

                    const newPackLotLines = payload
                        .filter((item) => !item.id)
                        .map((item) => ({ lot_name: item.text }));
                    
                    var is_exist_1 = lots.filter(function(v) {
                        if (v.product_id){
                            if (v.product_id.id == product.id){
                                payload.forEach(function (array) {
                                    let today = new Date();
                                    let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                    let alert_date = v.alert_date
                                    if(v.name == array.text && current_date >= alert_date){
                                        is_exist.push(v)
                                     }
                                });
                                return is_exist;
                            }
                        }
                    });

                    lots.forEach(function (line){
                        if (line.product_id){
                            if (line.product_id.id == product.id){
                                lots1.push(line.name)
                            }
                        }
                    });

                    payload.forEach(function (array) {
                        if(!lots1.includes(array.text)){
                            not_exist.push(array)
                        }
                    });

                    if (not_exist.length <= 0 && is_exist.length <= 0){
                        return { modifiedPackLotLines, newPackLotLines };
                    }
                }
                if(product.tracking == 'lot'){
                    if (payload){
                        if(payload[0]){
                            var is_exist_data = lots.filter(function(v) {
                                if (v.product_id){
                                    if (v.product_id.id == product.id){
                                        let today = new Date();
                                        let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
                                        let alert_date = v.alert_date
                                        return v.name == payload[0].text && alert_date >= current_date;
                                    }
                                }
                            });
                            if(is_exist_data.length != 0){
                                const modifiedPackLotLines = Object.fromEntries(
                                    payload.filter((item) => item.id).map((item) => [item.id, item.text])
                                );
                                const newPackLotLines = payload
                                    .filter((item) => !item.id)
                                    .map((item) => ({ lot_name: item.text }));
                                return { modifiedPackLotLines, newPackLotLines };
                            }else{}
                        }
                    }
                }
            }
        }
    },
});