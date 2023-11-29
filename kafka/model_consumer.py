from confluent_kafka import Consumer, KafkaError
import json

def consume_messages(consumer):
    try:
        msg = consumer.poll(3.0)

        if msg is None: pass
            #return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF: pass
                #return None
            else:
                print(msg.error())
                #return None

        # Extract your data (assuming JSON format)
        data = json.loads(msg.value().decode('utf-8'))
        data = data['price']
        print("Received message: ", data)
        return data

    except Exception as e:
        print("Error in consume_messages: ", e)


