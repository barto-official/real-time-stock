import azure.functions as func
import logging
import requests
import time
from time import sleep

app = func.FunctionApp()

@app.function_name(name="Model_retraining")
@app.blob_trigger(arg_name="myblob", path="models/{name}",
                               connection="models") 
async def main(myblob: func.InputStream):
    # Log the name and size of the blob
    logging.info(f"Python Blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Size: {myblob.length} bytes")
    
    # URL of Containers with the models
    api_url = "http://model1-rtp-2023.fterebbdfab6fscu.westeurope.azurecontainer.io:8001/update-model"
    api_url2 = "http://model2-rtp-2023.ayctcdh0dre3hge6.westeurope.azurecontainer.io:8001/update-model"
    api_url3 = "http://model3-rtp-2023.bqgadxddh7h7fyes.westeurope.azurecontainer.io:8001/update-model"
    try:
        # Post request to API with the blob name or other relevant data
        response = requests.post(api_url, json={"blob_name": myblob.name})
        logging.info(f"API response for Model 1: {response.status_code}, {response.text}")
        time.sleep(180)

        response = requests.post(api_url2, json={"blob_name": myblob.name})
        time.sleep(180)
        logging.info(f"API response for Model 2: {response.status_code}, {response.text}")
        response = requests.post(api_url3, json={"blob_name": myblob.name})
        logging.info(f"API response for Model 3: {response.status_code}, {response.text}")
        logging.info("Function calls completed")
    except Exception as e:
        logging.error(f"API request failed: {e}")
    


