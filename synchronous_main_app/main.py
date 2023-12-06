import logging
import requests
import pandas as pd
from river import time_series
from datetime import datetime, timedelta
from model import fetch_twelvedata, train_model, save_model, load_model, update_and_predict
import os
import json
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
import pickle
import threading
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubConsumerClient, EventHubProducerClient, EventData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


global model
model = time_series.HoltWinters(
    alpha=0.3,
    beta=0.1,
    gamma=0.6,
    seasonality=12,
    multiplicative=True
)

# Event Hubs configuration
connection_str =
eventhub_name_consumer =
eventhub_name_producer =

# Create an Event Hub consumer client
consumer_client = EventHubConsumerClient.from_connection_string(
    connection_str,
    consumer_group=
    eventhub_name=eventhub_name_consumer
)

# Create a producer client to send messages to the event hub
producer_client = EventHubProducerClient.from_connection_string(connection_str, eventhub_name=eventhub_name_producer)

TWELVE_DATA_API_KEY = os.getnev("TWELVE_DATA_API_KEY")
EVENTHUB_CONNECTION_STRING = os.getenv("EVENTHUB_CONNECTION_STRING")
EVENTHUB_NAME_CONSUMER = os.getenv("EVENTHUB_NAME_CONSUMER")
EVENTHUB_NAME_PRODUCER = os.getenv("EVENTHUB_NAME_PRODUCER")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# Lock for thread-safe model updates
model_lock = threading.Lock()

def get_model():
    with model_lock:
        return model

def on_event(partition_context, event):
    # Logic to process the event
    data = json.loads(event.body_as_str())
    price = data['price']
    global model
    prediction, model = update_and_predict(model, float(price))
    print(f"Prediction: {prediction}")
    print(f"Model: {model}")
    # Produce the prediction to Event Hubs
    produce_results(prediction, 'model_3')


def produce_results(prediction, model):
    # Build the message data
    data_to_send = {
        'prediction': prediction,
        'model': model,
    }

    # Convert the data dictionary to a JSON string
    message = json.dumps(data_to_send)
    # Send the message
    event_data_batch = producer_client.create_batch()
    event_data_batch.add(EventData(message))
    producer_client.send_batch(event_data_batch)
    producer_client.close()
    print(prediction, "sent to Event Hub (!)")

def consume_messages():
    try:
        logging.info("Starting to consume messages from Event Hub")
        with consumer_client:
            consumer_client.receive(
                on_event=on_event,
                starting_position="-1",  # from the beginning of the partition
            )
        logging.info("Finished consuming messages")
    except Exception as e:
        logging.error("Error in consume_messages: %s", e)


class ModelUpdateRequest(BaseModel):
    blob_name: str


def update_model(request: ModelUpdateRequest):
    blob_name = request.blob_name

    with model_lock:
        # Logic to download the new model using blob_name
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=, blob=blob_name)

        with open("temp_model.pkl", "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())
            logging.info("Model downloaded successfully")

        # Load the new model
        global model
        with open("temp_model.pkl", "rb") as file:
            model = pickle.load(file)
        logging.info("Model updated successfully")
        # Delete the temp file
        os.remove("temp_model.pkl")
        #remove if exists
        if os.path.exists("model.pkl"):
            os.remove("model.pkl")
        if os.path.exists("data_initial.csv"):
            os.remove("data_initial.csv")

        return {"message": "Model updated successfully"}


def main():
    logging.info("Starting the application")

    # Fetch initial data, train the model, and save it
    data = fetch_twelvedata('AAPL', '1min', TWELVE_DATA_API_KEY, datetime.now() - timedelta(days=7), datetime.now() - timedelta(seconds=10))
    logging.info("Data fetched")

    global model
    with model_lock:
        model = train_model(data, model)
        save_model(model)

    # Start consuming messages
    consume_messages()


#replace this dummy text with request_data: ModelUpdateRequest when finish testing
@app.post("/update-model")
def api_update_model(blob_name: str = "default_blob_name"):
    logging.info(f"Received request to update model with blob name: {blob_name}")
    # Add your logic here or a dummy response
    return {"message": f"Model update request received for blob: {blob_name}"}


def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8001)
    logging.info("FastAPI started")


if __name__ == "__main__":
    fastapi_thread = threading.Thread(target=run_fastapi)
    fastapi_thread.start()
    main()


