(function () {
    'use strict';

    // Blocks checkout "Next" navigation if "Scheduled" pickup is selected
    // but the user has not chosen a date and time.
    // Works alongside checkout_pickup.js (which handles showing/hiding the date-time picker).
    //
    // Odoo 18 checkout "Next" button is an <a name="website_sale_main_button"> link,
    // NOT a form submit — so we intercept its click event.

    function getPickupType() {
        var checked = document.querySelector('input[name="pickup_type_radio"]:checked');
        return checked ? checked.value : null;
    }

    function isScheduleComplete() {
        var date = document.getElementById('scheduled_pickup_date');
        var time = document.getElementById('scheduled_pickup_time');
        return date && time && date.value && time.value;
    }

    function showPickupError(message) {
        var existing = document.getElementById('j_pickup_error');
        if (existing) {
            existing.textContent = message;
            return;
        }
        var section = document.getElementById('pickup_schedule_section');
        if (!section) {
            return;
        }
        var alert = document.createElement('div');
        alert.id = 'j_pickup_error';
        alert.className = 'alert alert-danger mt-2';
        alert.textContent = message;
        section.appendChild(alert);
        section.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function clearPickupError() {
        var existing = document.getElementById('j_pickup_error');
        if (existing) {
            existing.remove();
        }
    }

    function validatePickupSchedule(event) {
        // Skip if the pickup schedule section is not on this page
        if (!document.getElementById('pickup_schedule_section')) {
            return;
        }
        if (getPickupType() === 'scheduled' && !isScheduleComplete()) {
            event.preventDefault();
            event.stopImmediatePropagation();
            showPickupError('Please select both a pickup date and time before continuing.');
        } else {
            clearPickupError();
        }
    }

    function attachGuards() {
        // Odoo 18: the "Next" step button is <a name="website_sale_main_button">
        var nextBtn = document.querySelector('a[name="website_sale_main_button"]');
        if (nextBtn) {
            nextBtn.addEventListener('click', validatePickupSchedule);
        }

        // Fallback: also guard any form submit and .a-submit buttons on the page
        document.querySelectorAll('form').forEach(function (form) {
            form.addEventListener('submit', validatePickupSchedule);
        });
        document.querySelectorAll('.a-submit').forEach(function (btn) {
            btn.addEventListener('click', validatePickupSchedule);
        });

        // Clear error when ASAP is selected
        document.querySelectorAll('input[name="pickup_type_radio"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                if (this.value === 'asap') {
                    clearPickupError();
                }
            });
        });

        // Clear error once the user picks a time slot
        var timeSelect = document.getElementById('scheduled_pickup_time');
        if (timeSelect) {
            timeSelect.addEventListener('change', function () {
                if (this.value) {
                    clearPickupError();
                }
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachGuards);
    } else {
        attachGuards();
    }
})();
