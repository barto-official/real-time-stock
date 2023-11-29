from river import time_series
from model_consumer import consume_messages
from model_producer import produce_results
from model import fetch_twelvedata, train_model, save_model, load_model, update_and_predict
from confluent_kafka import Consumer, KafkaError, Producer
from datetime import datetime, timedelta
import pandas as pd
import pickle
import os
import requests

#api_key= #GIVE YOUR API KEY HERE


### KAFKA CONFIGURATION
conf_consumer = {
    'bootstrap.servers': "host.docker.internal:9092",  # Replace with your server
    'group.id': "4",               # Consumer group ID
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf_consumer)
# Subscribe to the topic
consumer.subscribe(['apple-data'])  # Replace with your topic

conf_producer = {
    'bootstrap.servers': "host.docker.internal:9092",  # Replace with your server
}
topic_producer = "results"

### KAFKA CONFIGURATION

model = time_series.HoltWinters(
    alpha=0.3,
    beta=0.1,
    gamma=0.6,
    seasonality=12,
    multiplicative=True
)

data = fetch_twelvedata('AAPL', '1min', api_key, datetime.now() - timedelta(days=7), datetime.now()-timedelta(seconds=10))#for last 7 days:
data.to_csv('data_initial.csv')

#Download data and train model
model = train_model(data, model)
save_model(model)

try:
    while True:
        # Consume messages from Kafka
        message = consume_messages(consumer)
        # Update the model with the new value
        if message is not None:
            print(message)
            new_value = float(message)
            prediction, model = update_and_predict(model, new_value)
            print(f"Prediction: {prediction}")
            print(f"Model: {model}")
            #save_model(model)
            # Produce the prediction to Kafka
            produce_results(prediction, conf_producer, topic_producer)
        else:
            print("Empty message")
finally:
    # Close the consumer when done
    consumer.close()

