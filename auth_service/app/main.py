# auth_service/app/main.py
import json
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.init_db import init_db
from db.functions import create_user, get_user_by_email
from auth_utils import hash_password, verify_password, create_access_token
import aio_pika

# RabbitMQ
RABBITMQ_HOST = "rabbitmq"

async def lifespan(app: FastAPI):
    """Логика инициализации и завершения работы приложения."""
    await init_db()  # Инициализация базы данных
    yield

app = FastAPI(lifespan=lifespan)

async def consume_messages():
    """Потребление сообщений из RabbitMQ."""
    try:
        connection = await aio_pika.connect_robust(f'amqp://guest:guest@{RABBITMQ_HOST}/')
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue("user_events", durable=True)
            print("Waiting for messages...")

            async def callback(message: aio_pika.IncomingMessage):
                """Обработка входящих сообщений."""
                async with message.process():
                    try:
                        body = message.body.decode()
                        message_data = json.loads(body)
                        await process_message(message_data, message.reply_to, message.correlation_id)
                    except Exception as e:
                        print(f"Error processing message: {e}")

            queue = await channel.declare_queue("user_events", durable=True)
            await queue.consume(callback)
            await asyncio.Future()  # Пребывание в цикле событий

    except aio_pika.exceptions.AMQPConnectionError:
        print("RabbitMQ not ready. Retrying in 5 seconds...")
        await asyncio.sleep(5)

async def process_message(message, reply_to, correlation_id):
    """Обработка входящего сообщения."""
    event = message.get("event")
    if event == "register_request":
        await handle_registration(message, reply_to, correlation_id)
    elif event == "login_request":
        await handle_login(message, reply_to, correlation_id)

async def handle_registration(message, reply_to, correlation_id, db: AsyncSession = Depends(get_db)):
    """Обработка запроса на регистрацию."""
    email = message.get("email")
    password = message.get("password")
    response = {}
    if not email or not password:
        response = {"status": "error", "message": "Invalid registration data"}
    else:
        # Проверяем, есть ли уже такой пользователь
        existing_user = await get_user_by_email(db, email)
        if existing_user:
            response = {"status": "error", "message": f"User {email} already exists"}
        else:
            # Хешируем пароль и создаем нового пользователя
            hashed_password = hash_password(password)
            user_data = {"email": email, "hashed_password": hashed_password, "is_active": True}
            new_user = await create_user(db, user_data)
            response = {"status": "success", "message": f"User {new_user.email} successfully registered"}

    # Отправляем ответ обратно в очередь RabbitMQ
    await send_response(reply_to, correlation_id, response)

async def handle_login(message, reply_to, correlation_id, db: AsyncSession = Depends(get_db)):
    """Обработка запроса на вход в систему."""
    email = message.get("email")
    password = message.get("password")

    response = {}
    if not email or not password:
        response = {"status": "error", "message": "Invalid login data"}
    else:
        user = await get_user_by_email(db, email)
        if user and verify_password(password, user.hashed_password):
            token = create_access_token({"sub": user.email})
            response = {
                "status": "success",
                "message": f"User {user.email} successfully logged in",
                "token": token,
            }
        else:
            response = {"status": "error", "message": "Invalid email or password"}

    await send_response(reply_to, correlation_id, response)

async def send_response(reply_to, correlation_id, response):
    """Отправка ответа в указанный queue."""
    connection = await aio_pika.connect_robust(f'amqp://guest:guest@{RABBITMQ_HOST}/')
    async with connection:
        channel = await connection.channel()
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(response).encode(),
                correlation_id=correlation_id
            ),
            routing_key=reply_to,
        )

@app.get("/")
async def health_check():
    """Эндпоинт проверки работоспособности."""
    return {"status": "auth_service running"}

async def start_consumer():
    """Запуск потребителя RabbitMQ."""
    await consume_messages()

@app.on_event("startup")
async def on_startup():
    """Запуск асинхронного потребителя при старте приложения."""
    asyncio.create_task(start_consumer())
