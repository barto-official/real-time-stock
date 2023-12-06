
var countdownIntervalId = null;  // Interval ID variable
var previousValue = null; // Previous value for comparison
function generateUniqueId() {
    // Simple UUID generator or use a library
    return 'xxxx-xxxx-4xxx-yxxx-xxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function getOrCreateClientId() {
    let clientId = localStorage.getItem("clientId");
    if (!clientId) {
        clientId = generateUniqueId();
        localStorage.setItem("clientId", clientId);
    }
    return clientId;
}

var client_id = getOrCreateClientId();
var ws = new WebSocket(`wss://real-time-stock-prediction.azurewebsites.net/ws/${client_id}`);

ws.onopen = function() {
    console.log("Connected to WebSocket");
};

ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    handleIncomingData(data);
};

ws.onclose = function(event) {
    console.log("WebSocket closed");
};

ws.onerror = function(error) {
    console.log("WebSocket error:", error);
};

function startFetching() {
    console.log("startFetching called");
    ws.send("start_fetching"); // Send command to start fetching data
}

function stopFetching() {
    try {
        console.log("stopFetching called");
        ws.send("stop_fetching"); // Send command to stop fetching data
    } catch (error) {
        console.error("Error in stopFetching:", error);
    }
}

// Function to format the current date and time
function getCurrentDateTime() {
    var now = new Date();
    return now.getFullYear() + '-' + (now.getMonth() + 1).toString().padStart(2, '0') + '-' + now.getDate().toString().padStart(2, '0') + ' ' + now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0') + ':' + now.getSeconds().toString().padStart(2, '0');
    }

    // Function to handle start button click
function handleStartButtonClick() {
    // Capture the current date and time
    var currentDateTime = getCurrentDateTime();
    // Display the current date and time in the span with id="time_of_request"
    document.getElementById('time_of_request').innerText = currentDateTime;
}

// Adding event listener to the start button
document.getElementById('startButton').addEventListener('click', handleStartButtonClick);

function updateCurrency(changeValue) {
    const currencyContainer = document.getElementById('valueContainer');
    const percentageElem = currencyContainer.querySelector('.change-percentage');
    const amountElem = currencyContainer.querySelector('.change-amount');

    // Format the change value as needed, e.g., to percentage
    percentageElem.textContent = `${changeValue >= 0 ? '+' : ''}${changeValue.toFixed(3)}%`;
    amountElem.textContent = `(${Math.abs(changeValue).toFixed(3)})`;

    // Set text color based on positive or negative change
    const color = changeValue >= 0 ? 'green' : 'red';
    percentageElem.style.color = color;
    amountElem.style.color = color;

    // Change background color based on positive or negative change
    currencyContainer.style.backgroundColor = changeValue >= 0 ? '#90ee90' : '#ffcccb'; // Light green for positive, light red for negative

    // Remove the background color after a delay
    setTimeout(() => {
        currencyContainer.style.backgroundColor = ''; // Reset to default
    }, 1000);
}

// Function to update the datetime every second
function updateDateTime() {
    const datetimeElement = document.getElementById('datetime-value');
    datetimeElement.innerText = new Date().toLocaleString();
}

// Call updateDateTime every second (1000 milliseconds)
setInterval(updateDateTime, 1000);

// Initial call to display the time immediately on load
updateDateTime();


function handleIncomingData(data) {
    console.log(data);
    const currentValue = parseFloat(data.real_stock_value); // Parse it as a float
    const currencyContainer = document.getElementById('valueContainer');
    const valueLabel = currencyContainer.querySelector('.value-label'); // Select the label
    const prediction = parseFloat(data.prediction); // Parse it as a float

    // Compare with the previous value if it exists
    if (previousValue !== null) {
        const change = currentValue - previousValue;
        updateCurrency(change); // Update the currency display
    }

    // Update the previousValue for the next comparison
    previousValue = currentValue;
    valueLabel.innerText = currentValue.toFixed(2); // Display the value

    // Update other DOM elements with the received data
    console.log("Prediction", prediction.toFixed(3));
    document.getElementById('prediction-value').innerText = prediction.toFixed(3);
    document.getElementById('status-value').innerText = data.status;

    // Enable or disable the start and stop buttons based on the cooldown status
    const startButton = document.getElementById('startButton');
    const stopButton = document.getElementById('stopButton');
    if (data.cooldown) {
        startButton.disabled = true;
        startButton.style.opacity = 0.5;
        stopButton.disabled = true;
        stopButton.style.opacity = 0.5;
    } else if (data.status === 'Available') {
        startButton.disabled = false;
        startButton.style.opacity = 1;
        stopButton.style.opacity = 0.5;
        stopButton.disabled = true;
    } else if (data.status === 'Working') {
        startButton.disabled = true;
        startButton.style.opacity = 1;
        stopButton.style.opacity = 1;
        stopButton.disabled = false;
    } else {
        startButton.disabled = false;
        startButton.style.opacity = 1;
        stopButton.style.opacity = 1;
        stopButton.disabled = false;
    }

    // Handle cooldown status message
    handleCooldownStatus(data);
}

function handleCooldownStatus(data) {
    const statusElement = document.getElementById('status-value');
    if (data.status === 'Unavailable') {
        let countdown = Math.max(Math.floor(data.cooldown_time), 0);
        statusElement.innerText = `Status: Unavailable | The App available in: ${countdown} seconds`;

        if (countdownIntervalId !== null) {
            clearInterval(countdownIntervalId);
        }

        if (countdown > 0) {
            countdownIntervalId = setInterval(() => {
                countdown -= 1;
                statusElement.innerText = `Status: Unavailable | The App available in: ${countdown} seconds`;
                if (countdown <= 0) {
                    clearInterval(countdownIntervalId);
                    countdownIntervalId = null;
                    statusElement.innerText = `Status: Available`;
                }
            }, 1000);
        }
    } else {
        statusElement.innerText = `Status: ${data.status}`;
        if (countdownIntervalId !== null) {
            clearInterval(countdownIntervalId);
            countdownIntervalId = null;
        }
    }
}