# real-time-stock-prediction

## About the Project

This project aims at designing and implement a system to predict the Bitcoin price for the next minute using statistical and machine learning tools. To achieve that, a scalable and elastic architecture to stream data in real-time and minimize latency is proposed. While based on mainly Microsoft Azure components, it can be reimplemented using other cloud providers or open-source projects. The system shows promising results with data fetching in a truly real-time manner using Socket programming (2-3 seconds between consecutive data points) and latency of 2-3 seconds from getting data to prediction. The architecture is based mainly on asynchronous programming mode due to scalability, non-blocking I/O operations like WebSocket communication and data fetching, and handling operations for multiple users concurrently. 

**Technologies used:**
* Python 10.0
* Azure Components: Azure EventHub (or Azure Eventhub AIO), Azure Function, Azure Instance Container, Container App Jobs
* Docker Containers
* River Library for Machine Learning model and online retraining
* MySQL
* FastAPI (or Flask for synchronous backend)
* TwelveData API

**Details**
The goal of the project is to predict the price of Bitcoin (or other listed stock) in real-time. Although changing from Bitcoin can be easily implemented, the choice of Bitcoin is the frequency of trade — 24/7 — which allows for more testing the application on real scenario. Another important aspect is horizon prediction: while it is more of personal decision, we have chosen to to predict prices for the next minutes while inputting data with the interval of 2-3 seconds. This primarily serves to build a robust system that manage data in truly real-time without interruptions. 

Utilizing a backend that efficiently processes live data feeds through sockets, the system ensures immediate data synchronization with a dynamic frontend, while simultaneously relaying information to an Azure Event Hub. The Event Hub distributes data among multiple Time Series prediction models housed in containers. These models, upon producing the prediction, return it back through the Event Hub to the backend for user consumption.

Periodically, a Central Management Container activates to process the historical data, retrain the models, and store the updated versions in Azure Blob Storage. This action triggers an Azure Function that initiates an API call to update the machine learning models in their respective containers, thus ensuring that predictions are based on the latest patterns and trends. Additionally, the system maintains a MySQL database that is refreshed with new stock historical data to support ongoing analysis and model retraining

**The Logical Flow of the Architecture:**

<img width="1258" alt="Screenshot 2023-12-01 at 20 28 32" src="https://github.com/barto-official/real-time-stock/assets/125658269/58682c4b-0a18-4975-99c8-76300c3d7eeb">

**Component Breakdown:**
* Frontend
* Backend
* Processing
* Models
* Online Retraining
