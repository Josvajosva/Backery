/** @odoo-module */
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";



patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
    },
    export_for_printing() {
        const result = super.export_for_printing(...arguments);

        result.count = this.lines.length;
        this.receipt = result.count;

        console.log(this , "this")

        let sum = 0;
        result.orderlines = this.lines.map((line) => {
            sum += line.qty;
            return {
                productName: line.full_product_name || '',
                qty: line.qty || 0,
                unitPrice: line.price_unit || 0,
                price: line.price_subtotal_incl || 0,
            };
        });

        result.sum = sum;

        const getValueOrNil = (value) => value ? value : '';


        result.available_points = this.partner_id?.available_points || 0;
        result.has_membership = this.partner_id?.has_membership || false;
        result.displayName = getValueOrNil(this.display_name);
        result.partner_street = getValueOrNil(this.partner_id?.street);
        result.partner_name = getValueOrNil(this.partner_id?.name);
        result.partner_city = getValueOrNil(this.partner_id?.city);
        result.partner_state = getValueOrNil(this.partner_id?.state_id?.name);
        result.partner_address = getValueOrNil(this.partner_id?.street);

        const stateTinCodes = {
            'AP': '28', 'AR': '12', 'AS': '18', 'BR': '10', 'CG': '22',
            'DL': '07', 'GA': '30', 'GJ': '24', 'HR': '06', 'HP': '02',
            'JK': '01', 'JH': '20', 'KA': '29', 'KL': '32', 'MP': '23',
            'MH': '27', 'MN': '14', 'ML': '17', 'MZ': '15', 'NL': '13',
            'OD': '21', 'PB': '03', 'RJ': '08', 'SK': '11', 'TN': '33',
            'TS': '36', 'UP': '09', 'UK': '05', 'WB': '19', 'PY': '34',
        };

        const stateCode = this.company_id?.state_id?.code;
        this.company.state_tin_code = stateTinCodes[stateCode] || '';

        result.TotalQuantity = this.lines.reduce((acc, line) => acc + (parseFloat(line.qty) || 0), 0);
        result.ItemCount = this.lines.length;
        
        
        result.company = {
            name: this.company?.name || '',
            phone: this.company?.phone || '',
            hide_franchise_span: this.company?.hide_franchise_span || false,
        };

        return result;
    }
});


