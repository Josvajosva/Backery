(function () {
    'use strict';

    var PICKUP_DAYS_AHEAD = 2;
    var SLOT_MINUTES = 30;
    var OPEN_HOUR = 9;
    var CLOSE_HOUR = 21;

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function formatDateLocal(date) {
        return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
    }

    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function getToday() {
        return startOfDay(new Date());
    }

    function getMaxDate() {
        var max = getToday();
        max.setDate(max.getDate() + PICKUP_DAYS_AHEAD);
        return max;
    }

    function parseTimeValue(value) {
        var parts = value.split(':');
        return { hours: parseInt(parts[0], 10), minutes: parseInt(parts[1], 10) };
    }

    function formatTimeLabel(hours, minutes) {
        var period = hours >= 12 ? 'PM' : 'AM';
        var h = hours % 12;
        if (h === 0) {
            h = 12;
        }
        return h + ':' + pad(minutes) + ' ' + period;
    }

    function buildTimeSlots(dateStr) {
        var slots = [];
        var selectedDay = startOfDay(new Date(dateStr + 'T00:00:00'));
        var today = getToday();
        var now = new Date();
        var isToday = selectedDay.getTime() === today.getTime();

        for (var hour = OPEN_HOUR; hour < CLOSE_HOUR; hour++) {
            for (var minute = 0; minute < 60; minute += SLOT_MINUTES) {
                var slotDate = new Date(
                    selectedDay.getFullYear(),
                    selectedDay.getMonth(),
                    selectedDay.getDate(),
                    hour,
                    minute,
                    0
                );
                if (isToday && slotDate <= now) {
                    continue;
                }
                slots.push({
                    value: pad(hour) + ':' + pad(minute),
                    label: formatTimeLabel(hour, minute),
                });
            }
        }
        return slots;
    }

    function setDateLimits(dateInput) {
        if (!dateInput) {
            return;
        }
        dateInput.setAttribute('min', formatDateLocal(getToday()));
        dateInput.setAttribute('max', formatDateLocal(getMaxDate()));
    }

    function populateTimeSlots(timeSelect, dateStr, selectedTime) {
        if (!timeSelect) {
            return;
        }
        timeSelect.innerHTML = '';
        var placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select a time';
        timeSelect.appendChild(placeholder);

        if (!dateStr) {
            timeSelect.disabled = true;
            return;
        }

        var slots = buildTimeSlots(dateStr);
        timeSelect.disabled = slots.length === 0;
        slots.forEach(function (slot) {
            var option = document.createElement('option');
            option.value = slot.value;
            option.textContent = slot.label;
            if (selectedTime === slot.value) {
                option.selected = true;
            }
            timeSelect.appendChild(option);
        });

        if (selectedTime && !slots.some(function (s) { return s.value === selectedTime; })) {
            timeSelect.value = '';
        }
    }

    function getScheduledValue() {
        var dateInput = document.getElementById('scheduled_pickup_date');
        var timeSelect = document.getElementById('scheduled_pickup_time');
        if (!dateInput || !timeSelect || !dateInput.value || !timeSelect.value) {
            return '';
        }
        return dateInput.value + 'T' + timeSelect.value;
    }

    function savePickupSchedule(pickupType, datetimeValue) {
        var params = { pickup_type: pickupType };
        if (datetimeValue) {
            params.scheduled_datetime = datetimeValue;
        }
        fetch('/shop/save_pickup_schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1, params: params }),
        });
    }

    function onScheduleChange() {
        var value = getScheduledValue();
        if (value) {
            savePickupSchedule('scheduled', value);
        }
    }

    function restoreScheduledFields() {
        var wrapper = document.getElementById('scheduled_datetime_wrapper');
        if (!wrapper) {
            return;
        }
        var saved = wrapper.getAttribute('data-scheduled-value') || '';
        if (!saved) {
            return;
        }
        var dateInput = document.getElementById('scheduled_pickup_date');
        var timeSelect = document.getElementById('scheduled_pickup_time');
        if (!dateInput || !timeSelect) {
            return;
        }
        var parts = saved.split('T');
        if (parts.length !== 2) {
            return;
        }
        dateInput.value = parts[0];
        populateTimeSlots(timeSelect, parts[0], parts[1].slice(0, 5));
    }

    function applyPickupType(value) {
        var wrapper = document.getElementById('scheduled_datetime_wrapper');
        if (!wrapper) {
            return;
        }
        if (value === 'scheduled') {
            var dateInput = document.getElementById('scheduled_pickup_date');
            var timeSelect = document.getElementById('scheduled_pickup_time');
            setDateLimits(dateInput);
            restoreScheduledFields();
            if (dateInput && !dateInput.value) {
                dateInput.value = formatDateLocal(getToday());
            }
            // Always populate the time slots so the select is never left disabled
            // when the user toggles back to Scheduled after picking ASAP.
            if (dateInput && dateInput.value) {
                populateTimeSlots(timeSelect, dateInput.value, timeSelect ? timeSelect.value : '');
            }
            wrapper.style.display = 'block';
        } else {
            wrapper.style.display = 'none';
            savePickupSchedule('asap', null);
        }
    }

    function initPickupSchedule() {
        var dateInput = document.getElementById('scheduled_pickup_date');
        var timeSelect = document.getElementById('scheduled_pickup_time');
        setDateLimits(dateInput);

        if (dateInput) {
            dateInput.addEventListener('change', function () {
                populateTimeSlots(timeSelect, dateInput.value, '');
                onScheduleChange();
            });
        }
        if (timeSelect) {
            timeSelect.addEventListener('change', onScheduleChange);
        }

        document.querySelectorAll('input[name="pickup_type_radio"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                applyPickupType(this.value);
            });
        });

        var checked = document.querySelector('input[name="pickup_type_radio"]:checked');
        if (checked) {
            applyPickupType(checked.value);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPickupSchedule);
    } else {
        initPickupSchedule();
    }
})();
