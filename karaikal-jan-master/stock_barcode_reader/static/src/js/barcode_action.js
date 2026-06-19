/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class BarcodeInventoryAction extends Component {
    static template = "stock_barcode_reader.BarcodeAction";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.barcodeRef = useRef("barcodeInput");
        this._lineCounter = 0;

        this.state = useState({
            selectedLocationId: false,
            locationName: "",
            lines: [],
            barcodeValue: "",
            productSuggestions: [],
            isApplying: false,
            isEditingQuantity: false,
        });

        onMounted(async () => {
            await this._loadLocations();
            this._focusBarcode();
        });
    }

    // -------------------------------------------------------------------------
    // Locations — loaded from Python method
    // -------------------------------------------------------------------------

    async _loadLocations() {
        const loc = await this.orm.call(
            "stock.quant",
            "get_barcode_locations",
            [],
        );
        if (loc && loc.id) {
            this.state.selectedLocationId = loc.id;
            this.state.locationName = loc.name;
        }
    }

    // -------------------------------------------------------------------------
    // Barcode scanning
    // -------------------------------------------------------------------------

    onBarcodeInput(ev) {
        this.state.barcodeValue = ev.target.value;
        this._searchProductsByBarcodeOrName(this.state.barcodeValue);
    }

    async _searchProductsByBarcodeOrName(term) {
        const value = (term || "").trim();
        if (value.length < 2) {
            this.state.productSuggestions = [];
            return;
        }
        const products = await this.orm.searchRead(
            "product.product",
            [
                "|",
                "|",
                ["barcode", "ilike", value],
                ["display_name", "ilike", value],
                ["default_code", "ilike", value],
            ],
            ["id", "display_name", "uom_id", "barcode", "default_code"],
            { limit: 10 },
        );
        this.state.productSuggestions = products;
    }

    async onBarcodeKeydown(ev) {
        if (ev.key !== "Enter") return;
        ev.preventDefault();
        const value = this.state.barcodeValue.trim();
        if (!value) return;

        const products = await this.orm.searchRead(
            "product.product",
            [["barcode", "=", value]],
            ["id", "display_name", "uom_id", "barcode", "default_code"],
            { limit: 1 },
        );

        if (products.length) {
            await this._addLine(products[0]);
        } else if (this.state.productSuggestions.length === 1) {
            await this._addLine(this.state.productSuggestions[0]);
        } else if (this.state.productSuggestions.length > 1) {
            await this._addLine(this.state.productSuggestions[0]);
            this.notification.add(
                `Added: "${this.state.productSuggestions[0].display_name}". Select from list for other matches.`,
                { type: "info" },
            );
        } else {
            this.notification.add(
                `Product with barcode or name "${value}" not found.`,
                { type: "danger", title: "Product Not Found" },
            );
        }
        this.state.barcodeValue = "";
        this.state.productSuggestions = [];
        this._focusBarcode();
    }

    async onSuggestionClick(product) {
        await this._addLine(product);
        this.state.barcodeValue = "";
        this.state.productSuggestions = [];
        this._focusBarcode();
    }

    // -------------------------------------------------------------------------
    // Lines management
    // -------------------------------------------------------------------------

    async _addLine(product) {
        const existingIdx = this.state.lines.findIndex((l) => l.product_id === product.id);
        if (existingIdx >= 0) {
            const existing = this.state.lines[existingIdx];
            existing.quantity += 1;
            existing.animKey = Date.now();
            // Move to top of list
            this.state.lines.splice(existingIdx, 1);
            this.state.lines.unshift(existing);
            this.notification.add(
                `"${product.display_name}" — quantity increased to ${existing.quantity}`,
                { type: "info" },
            );
            return;
        }
        // Fetch on-hand quantity at selected location
        let onHand = 0;
        if (this.state.selectedLocationId) {
            const quants = await this.orm.searchRead(
                "stock.quant",
                [
                    ["product_id", "=", product.id],
                    ["location_id", "=", this.state.selectedLocationId],
                    ["lot_id", "=", false],
                ],
                ["quantity"],
                { limit: 1 },
            );
            if (quants.length) {
                onHand = quants[0].quantity;
            }
        }
        this._lineCounter++;
        this.state.lines.unshift({
            key: this._lineCounter,
            product_id: product.id,
            name: product.display_name,
            uom: product.uom_id[1],
            barcode: product.barcode || "",
            default_code: product.default_code || "",
            quantity: 1,
            animKey: Date.now(),
        });
    }

    onQuantityKeydown(ev) {
        if (ev.key === "Tab" || ev.key === "Enter") {
            ev.preventDefault();
            ev.target.dispatchEvent(new Event("change"));
            this._focusBarcode();
        }
    }

    onQuantityFocus() {
        this.state.isEditingQuantity = true;
    }

    onQuantityBlur(productId, ev) {
        this.state.isEditingQuantity = false;
        this.onQuantityChange(productId, ev);
    }

    onQuantityChange(productId, ev) {
        const val = parseFloat(ev.target.value);
        const line = this.state.lines.find((l) => l.product_id === productId);
        if (!line) return;
        if (isNaN(val) || val < 0) {
            this.notification.add("Quantity must be a positive number.", {
                type: "warning",
            });
            ev.target.value = line.quantity;
            return;
        }
        if (val > 10000) {
            this.notification.add(`Quantity for "${line.name}" exceeds 10000.`, {
                type: "warning",
            });
        }
        line.quantity = val;
    }

    removeLine(productId) {
        const idx = this.state.lines.findIndex((l) => l.product_id === productId);
        if (idx >= 0) {
            this.state.lines.splice(idx, 1);
        }
    }

    // -------------------------------------------------------------------------
    // Apply inventory
    // -------------------------------------------------------------------------

    async onApply() {
        if (!this.state.selectedLocationId) {
            this.notification.add("Please select a warehouse location first.", {
                type: "warning",
                title: "Missing Location",
            });
            return;
        }
        if (!this.state.lines.length) {
            this.notification.add("No products to apply.", { type: "warning" });
            return;
        }

        this.state.isApplying = true;
        try {
            const lines = this.state.lines.map((l) => ({
                product_id: l.product_id,
                quantity: l.quantity,
            }));
            await this.orm.call(
                "stock.quant",
                "barcode_apply_inventory",
                [this.state.selectedLocationId, lines],
            );
            this.notification.add("Inventory updated successfully!", {
                type: "success",
                title: "Inventory Applied",
            });
            this.state.lines = [];
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || "Unknown error";
            this.notification.add(msg, { type: "danger", title: "Error" });
        }
        this.state.isApplying = false;
        this._focusBarcode()
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    _focusBarcode() {
        if (this.barcodeRef.el) {
            this.barcodeRef.el.focus();
        }
    }
}

registry.category("actions").add("stock_barcode_action", BarcodeInventoryAction);
