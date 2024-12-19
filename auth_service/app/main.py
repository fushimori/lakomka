import pika
import json
from fastapi import FastAPI, Request, Form
from auth_utils import hash_password, verify_password
from database import get_user, add_user
import threading
import time

RABBITMQ_HOST = "rabbitmq"
app = FastAPI()

def consume_messages():
    """Consume messages from RabbitMQ."""
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue='user_events')

            def callback(ch, method, properties, body):
                """Handle incoming messages."""
                try:
                    message = json.loads(body)
                    print(f"Received message: {message}")
                    if message.get("event") == "register_request":
                        handle_registration(message, properties.reply_to, properties.correlation_id)
                    elif message.get("event") == "login_request":
                        handle_login(message, properties.reply_to, properties.correlation_id)
                except Exception as e:
                    print(f"Error processing message: {e}")

            channel.basic_consume(queue='user_events', on_message_callback=callback, auto_ack=True)
            print("Waiting for messages...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ not ready. Retrying in 5 seconds...")
            time.sleep(5)


def handle_registration(message, reply_to, correlation_id):
    """Handle registration requests and send responses."""
    username = message.get("username")
    password = message.get("password")

    response = {}

    if not username or not password:
        response = {"status": "error", "message": "Invalid registration data"}
    else:
        existing_user = get_user(username)
        if existing_user:
            response = {"status": "error", "message": f"User {username} already exists"}
        else:
            hashed_password = hash_password(password)
            add_user(username, hashed_password)
            response = {"status": "success", "message": f"User {username} successfully registered"}

    send_response(reply_to, correlation_id, response)


def handle_login(message, reply_to, correlation_id):
    """Handle login requests and send responses."""
    username = message.get("username")
    password = message.get("password")

    response = {}

    if not username or not password:
        response = {"status": "error", "message": "Invalid login data"}
    else:
        user = get_user(username)
        if user and verify_password(password, user["password"]):
            print("Debug: auth service here 1")
            response = {"status": "success", "message": f"User {username} successfully logged in"}
        else:
            print("Debug: auth service here 2")
            response = {"status": "error", "message": "Invalid username or password"}

    send_response(reply_to, correlation_id, response)


def send_response(reply_to, correlation_id, response):
    """Send a response to the specified queue."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    channel.basic_publish(
        exchange='',
        routing_key=reply_to,
        properties=pika.BasicProperties(correlation_id=correlation_id),
        body=json.dumps(response)
    )
    connection.close()

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "auth_service running"}



def start_consumer():
    """Start the RabbitMQ consumer in a separate thread."""
    consumer_thread = threading.Thread(target=consume_messages, daemon=True)
    consumer_thread.start()


start_consumer()
# consume_messages()
