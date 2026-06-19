import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useBarcodeReader } from "@point_of_sale/app/barcode/barcode_reader_hook";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
const { DateTime } = luxon;
import { ExpiryDatePopup } from "@bi_pos_lot_expiration/js/Popups/ExpiryDatePopup";
import { _t } from "@web/core/l10n/translation";

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
    },

    async _barcodeGS1Action(code) {
        const productBarcode = code.find((element) => element.type === "product");
        const lotBarcode = code.find((element) => element.type === "lot");
        const product = await this._getProductByBarcode(productBarcode);
        let current_date = DateTime.now().toFormat("yyyy-MM-dd hh:mm:ss")
        if(this.pos.config.allow_expiry_warning && this.pos.config.restrict_creating_lot){
            

            if (!product) {
                this.barcodeReader.showNotFoundNotification(
                    parsed_results.find((element) => element.type === "product")
                );
                return;
            }
            else{
                const lotbarcode_from_stock_lot = this.pos.stock_lot.find((element) => element.name === lotBarcode.value);
                if ( current_date >= lotbarcode_from_stock_lot.alert_date){
                    this.dialog.add(ExpiryDatePopup, {
                        title: _t('Expired Lot/Serial Number(s)'),
                        alert_date: lotbarcode_from_stock_lot.alert_date,
                    });
                }
            }
            
        }else if (this.pos.config.allow_expiry_warning && !this.pos.config.restrict_creating_lot){
            const lotbarcode_from_stock_lot = this.pos.stock_lot.find((element) => element.name === lotBarcode.value);
            if ( current_date >= lotbarcode_from_stock_lot.alert_date){
                this.dialog.add(ExpiryDatePopup, {
                    title: _t('Expired Lot/Serial Number(s)'),
                    alert_date: lotbarcode_from_stock_lot.alert_date,
                });
                await this.pos.addLineToCurrentOrder({ product_id: product }, { code: lotBarcode });
                this.numberBuffer.reset();
            }
        }else{
            await super._barcodeGS1Action(code);
        }
        
        
    },
});
