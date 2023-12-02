import logging
import requests
from river import time_series
from datetime import datetime, timedelta
from model import fetch_twelvedata, train_model, save_model, update_and_predict
import os
import json
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
import pickle
import threading
from azure.storage.blob import BlobServiceClient
from azure.eventhub import EventHubConsumerClient, EventHubProducerClient, EventData


# Event Hubs configuration
EVENTHUB_CONNECTION_STRING="Endpoint=sb://real-time-data-class.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=Jjoyt121OZZ/nJl8QOc0KfvDKYxP8NREt+AEhIOua5k="
EVENTHUB_NAME_CONSUMER="raw_data"
EVENTHUB_NAME_PRODUCER="results"
EVENTHUB_NAME_CONSUMER_GROUP="models"
TWELVE_DATA_API_KEY="9c9b91b490fc4a2ba8552188068c72fe"
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=rtpstorage2023;AccountKey=tXCLgQo5ZLcoLc4FINk49mbHhJwigbKDW8DMF885ErM7W1O4OwOPG74oLXIVGKiyNLGzLI0iYfHt+ASt3MfEXQ==;EndpointSuffix=core.windows.net"
BLOB_CONTAINER="models"

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

global blob_name
blob_name = None

# Create an Event Hub consumer client
consumer_client = EventHubConsumerClient.from_connection_string(
    EVENTHUB_CONNECTION_STRING,
    consumer_group=EVENTHUB_NAME_CONSUMER_GROUP,
    eventhub_name=EVENTHUB_NAME_CONSUMER
)

# Create a producer client to send messages to the event hub
producer_client = EventHubProducerClient.from_connection_string(EVENTHUB_CONNECTION_STRING, eventhub_name=EVENTHUB_NAME_PRODUCER)

# Lock for thread-safe model updates
model_lock = threading.Lock()

def on_event(partition_context, event):
    try:
        # Logic to process the event
        data = json.loads(event.body_as_str())
        price = data['price']
        global model
        prediction, model = update_and_predict(model, float(price))
        # Produce the prediction to Event Hubs
        produce_results(prediction, model)
        logging.info("Prediction: %s", prediction)
    except Exception as e:
        logging.error("Error in on_event: %s", e)


def produce_results(prediction, model):
    """
    Produce the prediction to Event Hubs.
    :param prediction:
    :param model:
    :return:
    """
    try:
        global blob_name
        if blob_name is None:
            blob_name = "tentative_model.pkl"
        # Build the message data
        data_to_send = {
            'prediction': prediction,
            'model': blob_name,
            'model_instance': "model_3"
        }

        # Convert the data dictionary to a JSON string
        message = json.dumps(data_to_send)
        # Send the message
        event_data_batch = producer_client.create_batch()
        event_data_batch.add(EventData(message))
        producer_client.send_batch(event_data_batch)
        #Don't close the client to speed up the process because the process will be continous
        #producer_client.close()
        logging.debug("Message sent successfully")
    except Exception as e:
        logging.error("Error in produce_results: %s", e)

def consume_messages():
    """
    Consume messages from Event Hub. This function will run forever.
    """
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
    """
    Update the model with the new model from blob storage.
    :param request:
    :return:
    """
    global blob_name
    blob_name = request.blob_name

    with model_lock:
        # Logic to download the new model using blob_name
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER, blob=blob_name)

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

        return blob_name

@app.post("/update-model")
def api_update_model(request_data: ModelUpdateRequest):
    """
    API endpoint to update the model. The request body should contain the blob name of the new model.
    :param blob_name:
    :return:
    """
    blob_name = request_data.blob_name
    logging.info(f"Received request to update model with blob name: {blob_name}")
    # Add your logic here or a dummy response
    update_model(ModelUpdateRequest(blob_name=blob_name))
    return {"message": f"Model update request received for blob: {blob_name}"}


def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8001)
    logging.info("FastAPI started")


def main():
    logging.info("Starting the application")
    # Fetch initial data, train the model, and save it
    data = fetch_twelvedata('BTC/USD', '1min', TWELVE_DATA_API_KEY, datetime.now() - timedelta(days=7), datetime.now() - timedelta(seconds=10))
    logging.info("Data fetched")

    global model
    with model_lock:
        model = train_model(data, model)
        save_model(model)

    # Start consuming messages
    consume_messages()


if __name__ == "__main__":
    fastapi_thread = threading.Thread(target=run_fastapi)
    fastapi_thread.start()
    main()


