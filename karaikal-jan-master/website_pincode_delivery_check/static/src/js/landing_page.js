window.selectOption = function (option) {
    var errorDiv = document.getElementById('error-message');
    errorDiv.style.display = 'none';
    errorDiv.innerText = '';

    var pickupPanel = document.getElementById('pickup-panel');
    var deliveryPanel = document.getElementById('delivery-panel');

    if (option === 'store_pickup') {
        pickupPanel.style.display = 'block';
        deliveryPanel.style.display = 'none';
    } else if (option === 'local_delivery') {
        pickupPanel.style.display = 'none';
        deliveryPanel.style.display = 'block';
    } else if (option === 'pan_india') {
        pickupPanel.style.display = 'none';
        deliveryPanel.style.display = 'none';
        window.submitSelection('pan_india');
    }
};

window.confirmPickup = function () {
    var storeSelect = document.getElementById('store-select');
    var storeId = storeSelect.value;
    if (!storeId) {
        alert('Please select a store first.');
        return;
    }
    window.submitSelection('store_pickup', { store_id: parseInt(storeId) });
};

window.confirmDelivery = function () {
    var zipInput = document.getElementById('delivery-zip');
    var zipCode = zipInput.value.trim();
    if (!zipCode) {
        alert('Please enter a delivery pincode.');
        return;
    }
    window.submitSelection('local_delivery', { zip_code: zipCode });
};

window.submitSelection = function (option, extraData) {
    extraData = extraData || {};
    var errorDiv = document.getElementById('error-message');
    errorDiv.style.display = 'none';
    errorDiv.innerText = '';

    var params = Object.assign({ delivery_option: option }, extraData);

    fetch('/landing/select', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            params: params,
        }),
    })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.error) {
                errorDiv.innerText = data.error.message || 'An error occurred.';
                errorDiv.style.display = 'block';
            } else if (data.result && data.result.status === 'success') {
                window.location.href = '/shop';
            } else if (data.result && data.result.status === 'error') {
                errorDiv.innerText = data.result.message || 'Validation failed.';
                errorDiv.style.display = 'block';
            }
        })
        .catch(function () {
            errorDiv.innerText = 'Network error. Please try again.';
            errorDiv.style.display = 'block';
        });
};