import os
import json
import time
import logging
from confluent_kafka import Consumer
import psycopg2

logging.basicConfig(level=logging.INFO)

# Kafka config
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_SCORING_TOPIC = os.getenv("KAFKA_SCORING_TOPIC", "scoring")

# Postgres config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.getenv("POSTGRES_DB", "scores_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Connect to Postgres
def connect_postgres():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    conn.autocommit = True
    return conn

def insert_score(conn, transaction_id, score, fraud_flag):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO scores (transaction_id, score, fraud_flag)
            VALUES (%s, %s, %s)
            ON CONFLICT (transaction_id) DO NOTHING;
        """, (transaction_id, score, fraud_flag))

def run():
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'db-loader-group',
        'auto.offset.reset': 'earliest'
    })

    consumer.subscribe([KAFKA_SCORING_TOPIC])
    conn = connect_postgres()

    logging.info("db_loader started and listening to scoring topic...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logging.error(f"Kafka error: {msg.error()}")
                continue

            try:
                records = json.loads(msg.value().decode('utf-8'))
                for record in records:
                    transaction_id = record["transaction_id"]
                    score = float(record["score"])
                    fraud_flag = int(record["fraud_flag"])
                    insert_score(conn, transaction_id, score, fraud_flag)
                    logging.info(f"Saved score for transaction {transaction_id}")
            except Exception as e:
                logging.error(f"Error processing message: {e}")
    except KeyboardInterrupt:
        logging.info("Stopping db_loader...")
    finally:
        consumer.close()
        conn.close()

if __name__ == "__main__":
    run()
