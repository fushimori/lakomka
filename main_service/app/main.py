from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import pika
import uuid
import json
import time
import httpx

app = FastAPI()

# RabbitMQ connection setup
RABBITMQ_HOST = "rabbitmq"

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
channel = connection.channel()


# Declare a queue
channel.queue_declare(queue='user_events')

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

AUTH_SERVICE_URL = "http://auth_service:8000"


def connection_rabbit():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue='user_events')

TIMEOUT = 5  # Максимальное время ожидания ответа в секундах

def send_request_and_wait_for_response(message):
    """Send a request to RabbitMQ and wait for a response with a timeout."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    # Declare a callback queue for the response
    result = channel.queue_declare(queue='', exclusive=True)
    callback_queue = result.method.queue

    correlation_id = str(uuid.uuid4())

    response = None
    start_time = time.time()

    def on_response(ch, method, properties, body):
        nonlocal response
        if properties.correlation_id == correlation_id:
            response = json.loads(body)

    # Consume messages from the callback queue
    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    # Send the request message
    channel.basic_publish(
        exchange='',
        routing_key='user_events',
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=correlation_id
        ),
        body=json.dumps(message)
    )

    print("Waiting for response...")

    # Ждем ответа с тайм-аутом
    while response is None:
        connection.process_data_events()  # Process RabbitMQ events
        # Проверяем, прошло ли время ожидания
        if time.time() - start_time > TIMEOUT:
            connection.close()
            return {"error": "Request timed out. Please try again later."}

    connection.close()
    return response


@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

# @app.post("/register")
# async def register(username: str = Form(...), password: str = Form(...)):
#     try:
#         connection_rabbit()
#         print("Отправляем форму")
#         message = json.dumps({"event": "register_request", "username": username, "password": password})
#         channel.basic_publish(exchange='', routing_key='user_events', body=message)
#         return {"message": "Registration request sent to auth service"}
#     except Exception as e:
#         return {"error": f"Failed to send message to RabbitMQ: {e}"}
#
# @app.post("/login")
# async def login_action(username: str, password: str):
#     async with httpx.AsyncClient() as client:
#         # connection_rabbit()
#         response = await client.get(f"{AUTH_SERVICE_URL}/check_user/{username}")
#         if response.status_code == 200:
#             return {"message": "Logged in successfully"}
#         else:
#             return {"message": "User not found"}


@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    """Send a registration request to the auth service."""
    message = {"event": "register_request", "username": username, "password": password}
    response = send_request_and_wait_for_response(message)
    return response


@app.post("/login")
async def login_action(username: str = Form(...), password: str = Form(...)):
    """Send a login request to the auth service."""
    print("DEBUG: main_service in post login")
    message = {"event": "login_request", "username": username, "password": password}
    response = send_request_and_wait_for_response(message)
    return response
