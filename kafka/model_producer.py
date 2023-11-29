from confluent_kafka import Producer

def produce_results(prediction, conf, topic):
    producer=Producer(conf)
    producer.produce(topic, key=str('prediction'), value=str(prediction))
    producer.flush()
    print(prediction, "sent to kafka (!)")
