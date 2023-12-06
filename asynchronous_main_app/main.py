from fastapi import FastAPI, Request, WebSocket, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import websockets
import threading
from typing import Dict
import json
import asyncio
from datetime import datetime
import time
import logging
import uvicorn
from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient
from azure.eventhub import EventData
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore

import logging.handlers

# Create logger
logger1 = logging.getLogger("my_logger")
logger1.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger1.addHandler(handler)
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")




### MAIN INDEX ###
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

### SOCKET CONNECTIONS ###
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_data: Dict[str, dict] = {}  # Stores client-specific data

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        asyncio.create_task(consume_messages(client_id))  # Start consuming messages from Event Hub
        self.active_connections[client_id] = websocket
        self.client_data[client_id] = {"real_stock_value": 0, "prediction": 0, "status": "Available", "cooldown": False, "stop_fetching": False}

    def start_cooldown(self, client_id: str, duration=120):
        self.client_data[client_id]['cooldown_start'] = time.time()
        self.client_data[client_id]['cooldown_duration'] = duration

    def get_remaining_cooldown(self, client_id: str) -> int:
        client_info = self.client_data.get(client_id, {})
        start = client_info.get('cooldown_start')
        duration = client_info.get('cooldown_duration')
        if start and duration:
            remaining = start + duration - time.time()
            return max(int(remaining), 0)
        return 0

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.client_data.pop(client_id, None)  # Clean up client data

    async def send_personal_message(self, message: str, client_id: str):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_text(message)

    # Method to update client-specific data
    def update_client_data(self, client_id: str, data: dict):
        if client_id in self.client_data:
            self.client_data[client_id].update(data)

    # Method to get client-specific data
    def get_client_data(self, client_id: str) -> dict:
        return self.client_data.get(client_id, {})


manager = WebSocketManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            client_data = manager.get_client_data(client_id)
            # Handle 'start_fetching' command
            if data == "start_fetching":
                # Check for cooldown status
                if not client_data.get('cooldown', False):
                    client_data['click_time'] = datetime.now().isoformat()  # Store the click time
                    manager.update_client_data(client_id, client_data)
                    asyncio.create_task(start_fetching(client_id)) # Pass client_id to the function
                else:
                    await manager.send_personal_message("Cannot start fetching. In cooldown period.", client_id)
            # Handle 'stop_fetching' command
            elif data == "stop_fetching":
                client_data['stop_fetching'] = True
                manager.update_client_data(client_id, client_data)
                await stop_job(client_id)  # Pass client_id to the function
    except Exception as e:
        logging.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        manager.disconnect(client_id)


### DATA FETCHING ###
async def fetch_twelvedata_data(client_id: str):
    start_time = asyncio.get_event_loop().time()
    uri = "wss://ws.twelvedata.com/v1/quotes/price?apikey=9c9b91b490fc4a2ba8552188068c72fe"

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action": "subscribe", "params": {"symbols": "BTC/USD"}}))

        while asyncio.get_event_loop().time() - start_time < 60:
            client_data = manager.get_client_data(client_id)
            if client_data.get('cooldown', False) or client_data.get('stop_fetching', False):
                break  # Stop fetching if 'cooldown' is True
            message = await ws.recv()  # Receive a message
            data = json.loads(message)
            if data['event'] != "subscribe-status":
                # Update client-specific data
                client_data['real_stock_value'] = data['price']
                manager.update_client_data(client_id, client_data)
                await emit_data(manager, client_id)  # Emit updated data to the specific client
                await produce_messages(data['price'])  # Pass client_id and data to the function
                logger1.info(f"Data fetched for client {client_id} at {datetime.now()}")


async def background_fetching(client_id: str):
    logger1.info(f"Data fetching started for client {client_id}.")
    client_data = manager.get_client_data(client_id)
    client_data['cooldown'] = False  # Ensure 'cooldown' is False when starting
    manager.update_client_data(client_id, client_data)
    await fetch_twelvedata_data(client_id)
    await stop_job(client_id)  # Automatically stop after 1 minute for the specific client


async def start_fetching(client_id: str):
    client_data = manager.get_client_data(client_id)
    if not client_data.get('cooldown', False):
        client_data['status'] = "Working"
        manager.update_client_data(client_id, client_data)
        await emit_data(manager, client_id)  # Emit data for the specific client
        await background_fetching(client_id)  # Pass client_id to background task
    else:
        logger1.info(f"Cannot start fetching for client {client_id}. In cooldown period.")


async def stop_job(client_id: str):
    manager.start_cooldown(client_id, 120) # Start cooldown for 2 minutes
    logger1.info("Stopping data fetching...")
    client_data = manager.get_client_data(client_id)
    client_data['cooldown'] = True
    client_data['stop_fetching'] = False
    client_data['status'] = "Unavailable"
    manager.update_client_data(client_id, client_data)
    logger1.info(f"Data fetching stopped for client {client_id}.")
    await emit_data(manager, client_id)  # Emit data for the specific client
    await asyncio.sleep(120)  # Cooldown for 2 minutes
    await end_cooldown(client_id)  # Pass client_id to cooldown ending task


async def end_cooldown(client_id: str):
    client_data = manager.get_client_data(client_id)
    client_data['status'] = "Available"
    client_data['cooldown'] = False
    manager.update_client_data(client_id, client_data)
    await emit_data(manager, client_id)  # Emit data for the specific client
    logger1.info(f"Cooldown ended for client {client_id}.")

async def emit_data(manager: WebSocketManager, client_id: str):
    remaining_cooldown = manager.get_remaining_cooldown(client_id)
    client_data = manager.get_client_data(client_id)
    data_to_send = {
        'real_stock_value': client_data.get('real_stock_value', 0),
        'prediction': client_data.get('prediction', 0),
        'status': client_data.get('status', 'Unavailable'),
        'cooldown': client_data.get('cooldown', False),
        'cooldown_time': remaining_cooldown,
    }
    await manager.send_personal_message(json.dumps(data_to_send), client_id)

### EVENT HUB ###
# Azure Event Hubs configuration
connection_str = "Endpoint=sb://real-time-data-class.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=Jjoyt121OZZ/nJl8QOc0KfvDKYxP8NREt+AEhIOua5k="
eventhub_name_consumer = "results"
eventhub_name_producer = "raw_data"

checkpoint_store = BlobCheckpointStore.from_connection_string("DefaultEndpointsProtocol=https;AccountName=rtpstorage2023;AccountKey=tXCLgQo5ZLcoLc4FINk49mbHhJwigbKDW8DMF885ErM7W1O4OwOPG74oLXIVGKiyNLGzLI0iYfHt+ASt3MfEXQ==;EndpointSuffix=core.windows.net", "$logs")

#Create Event Hub consumer and producer clients
consumer_client = EventHubConsumerClient.from_connection_string(
    connection_str,
    consumer_group="$Default",
    eventhub_name=eventhub_name_consumer,
    checkpoint_store=checkpoint_store,
    logging_enable=True
)

producer_client = EventHubProducerClient.from_connection_string(
    connection_str,
    eventhub_name=eventhub_name_producer
)

def create_event_consumer(client_id):
    async def on_event(partition_context, event):
        return await on_event_consumer(client_id, partition_context, event)
    return on_event

async def on_event_consumer(client_id, partition_context, event):
    event_data = json.loads(event.body_as_str())  # Minimal processing
    prediction, model, model_instance = float(event_data['prediction']), event_data['model'], event_data['model_instance']
    await partition_context.update_checkpoint(event)  # Update checkpoint so we can read from last position
    client_data = manager.get_client_data(client_id)
    client_data['prediction'] = prediction
    # emit data
    manager.update_client_data(client_id, client_data)
    await emit_data(manager, client_id)

async def consume_messages(client_id):
    logger1.info("Consuming messages...")
    on_event_with_client_id = create_event_consumer(client_id)
    async with consumer_client:
        await consumer_client.receive(on_event=on_event_with_client_id, starting_position="-1")



async def produce_messages(data):
    async with producer_client:
        message_json = json.dumps(data)
        event = EventData(message_json)
        await producer_client.send_batch([event])  # Add 'await' for the async operation
        logger1.info("Message sent to Event Hub")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level='info')


