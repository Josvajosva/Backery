odoo.define('loyalty_pos.RedeemButton', function(require) {
    'use strict';

    const { Gui } = require('point_of_sale.Gui');
    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');

    // Extend the PaymentScreen to add redeem functionality
    const LoyaltyPaymentScreen = (PaymentScreen) => 
        class LoyaltyPaymentScreen extends PaymentScreen {
            setup() {
                super.setup();
            }

            get partner() {
                const order = this.env.pos.get_order();
                return order ? order.get_partner() : null;
            }

            get availablePoints() {
                return this.partner ? this.partner.available_points || 0 : 0;
            }

            get canRedeem() {
                return this.partner && 
                       this.partner.has_membership && 
                       this.availablePoints > 0;
            }

            async onClickRedeem() {
                if (!this.partner) {
                    Gui.showPopup('ErrorPopup', {
                        title: 'Error',
                        body: 'Please select a customer first.',
                    });
                    return;
                }

                if (!this.partner.has_membership) {
                    Gui.showPopup('ErrorPopup', {
                        title: 'Error',
                        body: 'Customer does not have active membership.',
                    });
                    return;
                }

                if (this.availablePoints <= 0) {
                    Gui.showPopup('ErrorPopup', {
                        title: 'Error',
                        body: 'No points available to redeem.',
                    });
                    return;
                }

                // Show redeem popup
                const { confirmed, payload } = await Gui.showPopup('NumberPopup', {
                    title: 'Redeem Points',
                    body: `Available Points: ${this.availablePoints}`,
                    startingValue: Math.min(100, this.availablePoints),
                    isInputSelected: true,
                });

                if (confirmed) {
                    const pointsToRedeem = Math.floor(payload);
                    if (pointsToRedeem <= 0 || pointsToRedeem > this.availablePoints) {
                        Gui.showPopup('ErrorPopup', {
                            title: 'Error',
                            body: 'Invalid points amount.',
                        });
                        return;
                    }

                    // Call server to redeem points
                    try {
                        const result = await this.rpc({
                            model: 'pos.order',
                            method: 'action_redeem_points',
                            args: [this.partner.id, pointsToRedeem],
                        }, { timeout: 5000 });

                        if (result.success) {
                            // Apply discount to order (1 point = 1 currency unit)
                            const discountAmount = pointsToRedeem;
                            const order = this.env.pos.get_order();
                            
                            // Check if discount product exists
                            let discountProduct = this.env.pos.db.get_product_by_id(
                                this.env.pos.config.discount_product_id && this.env.pos.config.discount_product_id[0]
                            );
                            
                            if (!discountProduct) {
                                // Create a temporary discount product
                                discountProduct = {
                                    id: -1,
                                    name: 'Loyalty Discount',
                                    lst_price: 0,
                                    taxes_id: [],
                                };
                            }

                            // Add discount line
                            order.addProduct(discountProduct, {
                                price: -discountAmount,
                                extras: {
                                    price_manually_set: true,
                                },
                            });

                            Gui.showPopup('ConfirmPopup', {
                                title: 'Success',
                                body: `Redeemed ${pointsToRedeem} points. 
                                      Discount: ${this.env.pos.currency.symbol}${discountAmount}
                                      Remaining points: ${result.remaining_points}`,
                            });

                            // Refresh partner data
                            await this.env.pos.load_new_partners();
                        } else {
                            Gui.showPopup('ErrorPopup', {
                                title: 'Error',
                                body: result.error || 'Failed to redeem points.',
                            });
                        }
                    } catch (error) {
                        Gui.showPopup('ErrorPopup', {
                            title: 'Error',
                            body: 'Server error: ' + error.message,
                        });
                    }
                }
            }
        };

    Registries.Component.extend(PaymentScreen, LoyaltyPaymentScreen);

    return PaymentScreen;
});