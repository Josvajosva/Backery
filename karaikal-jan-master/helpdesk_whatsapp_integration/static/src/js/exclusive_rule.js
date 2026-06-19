/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

/**
 * Calculate points for a single rule given the order amounts/quantities.
 * Handles floor_calculation logic for all reward_point_mode types.
 */
function calculateRulePoints(rule, orderedProductPaid, totalProductQty) {
    if (rule.floor_calculation) {
        const blockSize = 100;
        const completedBlocks = Math.floor(orderedProductPaid / blockSize);
        const flooredAmount = completedBlocks * blockSize;
        if (rule.reward_point_mode === "order") {
            return completedBlocks * rule.reward_point_amount;
        } else if (rule.reward_point_mode === "money") {
            return Math.round(flooredAmount * rule.reward_point_amount * 100) / 100;
        } else if (rule.reward_point_mode === "unit") {
            return completedBlocks * rule.reward_point_amount;
        }
    } else {
        if (rule.reward_point_mode === "order") {
            return rule.reward_point_amount;
        } else if (rule.reward_point_mode === "money") {
            return Math.round(rule.reward_point_amount * orderedProductPaid * 100) / 100;
        } else if (rule.reward_point_mode === "unit") {
            return rule.reward_point_amount * totalProductQty;
        }
    }
    return 0;
}

/**
 * Evaluate rules for a program against order lines.
 * Returns { matched, points } where matched is true if at least one rule matched.
 * If exclusiveMode is true, only the first matching rule's points are used.
 */
function evaluateRules(order, program, orderLines, exclusiveMode) {
    const sortedRules = [...program.rule_ids].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    let totalPoints = 0;
    let matched = false;

    for (const rule of sortedRules) {
        if (
            rule.mode === "with_code" &&
            !order.uiState.codeActivatedProgramRules.includes(rule.id)
        ) {
            continue;
        }

        // Get lines applicable to this rule
        const linesForRule = orderLines.filter(
            (line) =>
                !line.is_reward_line &&
                (rule.any_product || rule.validProductIds.has(line.product_id.id))
        );

        // Calculate amounts
        const amountWithTax = linesForRule.reduce(
            (sum, line) =>
                sum +
                (line.combo_line_ids.length > 0
                    ? line.getComboTotalPrice()
                    : line.get_price_with_tax()),
            0
        );
        const amountWithoutTax = linesForRule.reduce(
            (sum, line) =>
                sum +
                (line.combo_line_ids.length > 0
                    ? line.getComboTotalPriceWithoutTax()
                    : line.get_price_without_tax()),
            0
        );
        const amountCheck =
            (rule.minimum_amount_tax_mode === "incl" && amountWithTax) || amountWithoutTax;

        if (rule.minimum_amount > amountCheck) {
            continue;
        }

        // Calculate quantities and paid amount
        let totalProductQty = 0;
        let orderedProductPaid = 0;
        for (const line of orderLines) {
            if (
                ((!line.reward_product_id &&
                    (rule.any_product || rule.validProductIds.has(line.product_id.id))) ||
                    (line.reward_product_id &&
                        (rule.any_product ||
                            rule.validProductIds.has(line._reward_product_id?.id)))) &&
                !line.ignoreLoyaltyPoints({ program })
            ) {
                if (line.is_reward_line) {
                    const reward = line.reward_id;
                    if (
                        program.id === reward.program_id.id ||
                        ["gift_card", "ewallet"].includes(reward.program_id.program_type)
                    ) {
                        continue;
                    }
                }
                const lineQty = line._reward_product_id
                    ? -line.get_quantity()
                    : line.get_quantity();
                orderedProductPaid +=
                    line.combo_line_ids.length > 0
                        ? line.getComboTotalPrice()
                        : line.get_price_with_tax();
                if (!line.is_reward_line) {
                    totalProductQty += lineQty;
                }
            }
        }

        if (totalProductQty < rule.minimum_qty) {
            continue;
        }

        // Rule matches - calculate points
        const rulePoints = calculateRulePoints(rule, orderedProductPaid, totalProductQty);
        matched = true;

        if (exclusiveMode) {
            // Exclusive: only first matching rule
            totalPoints = rulePoints;
            break;
        } else {
            // Normal: sum all matching rules
            totalPoints += rulePoints;
        }
    }

    return { matched, points: totalPoints };
}

patch(PosOrder.prototype, {
    pointsForPrograms(programs) {
        // Let base handle everything first
        const result = super.pointsForPrograms(programs);

        // Check if partner qualifies for double points
        const partner = this.get_partner();
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const orderLines = this.get_orderlines().filter((line) => !line.combo_parent_id);

        for (const program of programs) {
            const isExclusive = program.exclusive_rule_evaluation;
            const hasFloorRule = program.rule_ids.some((r) => r.floor_calculation);

            // Skip programs that don't need custom handling
            if (!isExclusive && !hasFloorRule && !(program.double_points_days > 0)) {
                continue;
            }

            // Recalculate points with our custom logic
            const { matched, points } = evaluateRules(this, program, orderLines, isExclusive);

            let finalPoints = points;

            // Double points if partner purchased within double_points_days
            if (matched && program.double_points_days > 0 && partner && partner.last_pos_order_date) {
                const lastDate = new Date(partner.last_pos_order_date);
                lastDate.setHours(0, 0, 0, 0);
                const diffDays = Math.floor((today - lastDate) / (1000 * 60 * 60 * 24));
                if (diffDays <= program.double_points_days) {
                    finalPoints = finalPoints * 2;
                }
            }

            if (matched) {
                result[program.id] = [{ points: finalPoints }];
            } else if (isExclusive) {
                result[program.id] = program.program_type === "coupons" ? [{ points: 0 }] : [];
            }
        }

        return result;
    },
});