from flask import Flask, render_template
from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta,timezone
import websocket
import threading
import json
from azure.eventhub import EventHubProducerClient, EventData, EventHubConsumerClient


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with your actual secret key
socketio = SocketIO(app)
scheduler = BackgroundScheduler()
prediction = "—"
real_stock_value = "0"
status = "Available"
ws=None
previous_data= None
websocket_thread=None
cooldown = False

@socketio.on('start_fetching')
def handle_start_fetching():
    if not cooldown:
        global click_time
        click_time = datetime.now()
        start_fetching()
    else:
        print("Cannot start fetching. In cooldown period.")

def start_fetching():
    """Starts fetching data every 5 seconds for up to 1 minute."""
    if not cooldown:
        start_twelvedata_websocket()
        #Schedule to automatically stop after 1 minute
        scheduler.add_job(stop_job, 'date', run_date=datetime.now() + timedelta(minutes=1), id='stop_job')
        print("Data fetching started.")
        global status
        status = "Working"
    else:
        print("Cannot start fetching. In cooldown period.")


@socketio.on('stop_fetching')
def handle_stop_fetching():
    stop_job()


def stop_job():
    """Stops the data fetching job."""
    fetch_job_id = 'sp500_fetch_job'
    if scheduler.get_job(fetch_job_id):
        scheduler.remove_job(fetch_job_id)
    global ws, websocket_thread, cooldown
    cooldown = True
    if ws:
        ws.close()
        ws = None
    if websocket_thread:
        websocket_thread.join()
        websocket_thread = None
    # Schedule to end cooldown period after 2 minutes
    scheduler.add_job(end_cooldown, 'date', run_date=datetime.now() + timedelta(minutes=2), id='cooldown_job')
    print(f"Data fetching stopped at {datetime.now()}")
    global status
    status = "Unavailable"
    emit_data()

def end_cooldown():
    """Ends the cooldown period."""
    global cooldown, status
    status = "Available"
    cooldown = False
    print(f"Cooldown ended at {datetime.now()}")
    emit_data()

def fetch_data(ws, message):
    if (json.loads(message))['event'] != "subscribe-status":
        global latest_data
        global real_stock_value
        latest_data = json.loads(message)  # Update the latest data
        real_stock_value = latest_data['price']
        print(f"Data fetched at {datetime.now()}")
        emit_data()


def emit_data():
    """Emit data to the frontend."""
    now = datetime.now(timezone.utc)  # Get an aware current time
    # Assuming that your scheduler uses aware datetimes as well
    # If not, you might need to remove timezone.utc to make it naive
    remaining_cooldown = (scheduler.get_job('cooldown_job').next_run_time - now).total_seconds() if cooldown else 0
    data_to_send = {
        'real_stock_value': real_stock_value,
        'prediction': prediction,
        'status': status,
        'cooldown': cooldown,  # Send the cooldown status to the frontend
        'cooldown_time': remaining_cooldown,  # Send remaining cooldown time to the frontend
        'click_time': click_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    socketio.emit('update_data', data_to_send)

# Event-hub configuration
#--------------------------------------------------------------
# Azure Event Hubs configuration
connection_str =
eventhub_name_consumer =
eventhub_name_producer = 

#Create Event Hub consumer and producer clients
consumer_client = EventHubConsumerClient.from_connection_string(
    connection_str,
    consumer_group=,
    eventhub_name=eventhub_name_consumer
)

producer_client = EventHubProducerClient.from_connection_string(
    connection_str,
    eventhub_name=eventhub_name_producer
)

# DATA FETCHING
#--------------------------------------------------------------
latest_data = None  # Global variable to store the latest data

def on_error(ws, error):
    print("Error", error.message)

def on_close(ws, close_status_code, close_msg):
    print("### WebSocket Closed ###")

def on_open(ws):
    def run(*args):
        # Subscribe to Apple's stock
        data = {"action": "subscribe", "params": {"symbols": "BTC/USD"}}
        ws.send(json.dumps(data))
    threading.Thread(target=run).start()
    print("### WebSocket Opened ###")


def start_twelvedata_websocket():
    global ws, websocket_thread
    websocket_url = "wss://ws.twelvedata.com/v1/quotes/price?apikey=YOUR_API_KEY"
    ws = websocket.WebSocketApp(websocket_url,
                                on_open=on_open,
                                on_message=fetch_data,
                                on_error=on_error,
                                on_close=on_close)

    # Start a thread to run the WebSocket for a limited time
    websocket_thread = threading.Thread(target=lambda: ws.run_forever())
    websocket_thread.start()



import queue

# Queue for passing messages from the consumer to the processing logic
message_queue = queue.Queue()

#Function to handle received events
def on_event_consumer(partition_context, event):
    global prediction
    event_data = json.loads(event.body_as_str())  # Minimal processing
    prediction, model=float(event_data['prediction']), event_data['model']
    print(f"Received prediction: {prediction} from model: {model}")
    partition_context.update_checkpoint(event)

# Function to consume messages
def consume_messages():
    try:
        with consumer_client:
            consumer_client.receive(
                on_event=on_event_consumer,
                starting_position="-1",  # Start from the earliest available event
            )
    except Exception as e:
        print(f"Error in consume_messages: {e}")

# Function to produce messages
def produce_messages():
    global latest_data, previous_data
    try:
        while True:
            if latest_data != previous_data:
                previous_data = latest_data
                message_json = json.dumps(latest_data)
                event = EventData(message_json)
                producer_client.send_batch([event])
                print("Message sent to Event Hub")
    except Exception as e:
        print(f"Error sending to Event Hub: {e}")

# Start the consumer and producer in separate threads
consumer_thread = threading.Thread(target=consume_messages, daemon=True)
producer_thread = threading.Thread(target=produce_messages, daemon=True)

#--------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Start the background threads first
    consumer_thread.start()
    producer_thread.start()
    # Start the scheduler
    scheduler.start()

    # Now start the Flask-SocketIO server
    try:
        socketio.run(app, debug=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        # Optionally, join your threads here or handle their closure
        consumer_thread.join()
        producer_thread.join()
