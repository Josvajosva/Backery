/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

console.log("🟣 pos_hide_outofstock module loaded");


patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        console.log(`validateOrder`);
        const order = this.currentOrder;

        // 🔥 Update local stock BEFORE validation
        for (const line of order.get_orderlines()) {
            console.log(`get_orderlines`);
            const product = line.product_id;
            console.log(product.type + ` get_orderlines`);
            if (!product || product.type !== "consu") continue;
            console.log(`get_quantity`);
            const qty = line.get_quantity();
            console.log(`Products changed qty: ${qty}`);
            console.log(`Hide out of stock: ${this.pos.config.hide_outofstock_products}`);
            console.log(`Product Category: ${product.categ_id.name}`);
            console.log(`Product Category status: ${product.categ_id.always_visible_in_pos}`);
            if (this.pos.config.hide_outofstock_products && !product.categ_id.always_visible_in_pos) {
                if (qty > product.raw.qty_available) {
                    this.dialog.add(AlertDialog, {
                        title: "Insufficient Stock",
                        body: `You tried to order ${qty} quantity of ${product.display_name}, but only ${product.raw.qty_available} is available in stock.`,
                    });
                    //⛔ Block validation
                    return;
                }
            }
            if (this.pos.config.hide_outofstock_products && !product.categ_id.always_visible_in_pos) {
                if (product.raw?.qty_available !== undefined) { // ) 
                    product.raw.qty_available -= qty;
                    console.log(`Products changed qty_available: ${product.raw.qty_available}`);

                    if (product.raw.qty_available <= 0) {
                        product.raw.qty_available = 0;
                        product.available_in_pos = false;
                        console.log(`Products changed available_in_pos`);
                    }
                }
            }
        }

        return await super.validateOrder(isForceValidate);
    },
});


patch(ProductScreen.prototype, {
    __debugLogged: false,  

    get productsToDisplay() {
        console.log("recomputed productsToDisplay");
        let list = [];

        if (this.searchWord) {
            list = this.addMainProductsToDisplay(
                this.getProductsBySearchWord(this.searchWord)
            );
        } else if (this.pos.selectedCategory?.id) {
            list = this.getProductsByCategory(this.pos.selectedCategory);
        } else {
            list = this.products;
        }

        const totalBeforeFilter = list.length;

        let hiddenCount = 0;

        if (this.pos.config.hide_outofstock_products) {
            const beforeFilterCount = list.length;

            list = list.filter(p => {
                const category = p.categ_id
                    ? this.pos.models["product.category"].get(p.categ_id.id)
                    : null;
                const alwaysVisible = category?.always_visible_in_pos || false;

                return (
                    Number(p.raw.qty_available || 0) > 0 ||
                    alwaysVisible
                );
            });

            hiddenCount = beforeFilterCount - list.length;
        }
        const totalAfterFilter = list.length;

        const excludedIds = [
            this.pos.config.tip_product_id?.id,
            ...(this.pos.hiddenProductIds || []),
            ...(this.pos.session._pos_special_products_ids || []),
        ];

        const finalList = list.filter(p => !excludedIds.includes(p.id) && p.available_in_pos);

        // Log debug only once
        if (!this.__debugLogged) {
            console.log(`🧮 Products before out-of-stock filter: ${totalBeforeFilter}`);
            console.log(`🚫 Products hidden (out of stock): ${hiddenCount}`);
            console.log(`✅ Products after filtering: ${totalAfterFilter}`);
            console.log(`🎯 Final products to display (after exclusions): ${finalList.length}`);
            this.__debugLogged = true;
        }

        return finalList;
    },
});
