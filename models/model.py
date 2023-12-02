import requests
import pandas as pd
from river import time_series
from datetime import datetime
import pickle
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_twelvedata(symbol, interval, api_key, start_date=None, end_date=None):
    """
        Fetches time series data from the Twelve Data API for a given symbol and interval using HTTP GET requests.

        :param symbol: The symbol for the data retrieval.
        :param interval: The interval for the data retrieval. If 1 minute, then only last 7 days available.
        :param api_key: The API key for the data retrieval.
        :param start_date: The start date for the data retrieval (optional).
        :param end_date: The end date for the data retrieval (optional).
        :return: A pandas DataFrame with the price data (the earliest data last for chronological time-series order),
        and the raw data as a dictionary.
        """
    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": api_key,
        "start_date": start_date,
        "end_date": end_date
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        data = response.json()
        logger.info("Data fetched at {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        df = pd.DataFrame(data['values'])

        df['datetime'] = pd.to_datetime(df['datetime'])
        df.drop(columns=['datetime', 'high', 'low', 'close'], inplace=True)
        return df.iloc[::-1]
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTPError occurred: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException occurred: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

def train_model(data, model):
    """
    Trains a HoltWinters time series model on the provided data. Takes only one variable because it is a real-time model.
    Check River documentation for more info.
    :param data:
    :param model:
    :return:
    """
    for timestamp, value in data["open"].items():
        numeric_value = float(value)
        model = model.learn_one(numeric_value)
    logging.info("Model trained")
    return model

def save_model(model, filename='model.pkl'):
    """
    Saves a model to a pickle file.
    :param model:
    :param filename:
    """
    with open(filename, 'wb') as file:
        pickle.dump(model, file)
    logging.info("Model saved")

def load_model(filename='model_initial.pkl'):
    """
    Loads a model from a pickle file.
    :param filename:
    :return: pickle model.
    """
    if os.path.exists(filename):
        with open(filename, 'rb') as file:
            logging.info("Model loaded")
            return pickle.load(file)
    else:
        logging.info("Model not found")
        return None

def update_and_predict(model, new_value):
    """
    Updates the model with a new value and generates a prediction for the next 5 minutes.
    :param model:
    :param new_value:
    :return:
    """
    # Prediction for next 2 minutes (if needed)
    horizon1, horizon2, horizon3, horizon4, horizon5 = model.forecast(horizon=5)
    # Update the model with the new value
    model = model.learn_one(new_value)
    logging.info("Model updated")
    # Return the prediction for the next 2 minutes
    return horizon2, model




