import json
import asyncio
from fastapi import FastAPI
from auth_utils import hash_password, verify_password, create_access_token
from db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from db.functions import create_user, get_user_by_email
from db.init_db import init_db
import aio_pika

# RabbitMQ Host
RABBITMQ_HOST = "rabbitmq"

# FastAPI Application
app = FastAPI()

# Application lifespan for initializing the database
@app.on_event("startup")
async def app_startup():
    await init_db()
    asyncio.create_task(consume_messages())


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "auth_service running"}


async def consume_messages():
    """
    Consume messages from RabbitMQ asynchronously.
    This function continuously listens for messages from the 'user_events' queue.
    """
    while True:
        try:
            # Establish RabbitMQ connection
            connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_HOST}")
            async with connection:
                channel = await connection.channel()
                queue = await channel.declare_queue("user_events", durable=True)

                # Consume messages from the queue
                await queue.consume(lambda message: handle_message(channel, message))
                print("Listening for messages...")
                await asyncio.Future()  # Keep the consumer running
        except aio_pika.exceptions.AMQPConnectionError:
            print("RabbitMQ not available. Retrying in 5 seconds...")
            await asyncio.sleep(5)


async def handle_message(channel, message: aio_pika.IncomingMessage):
    """Handle incoming messages from the RabbitMQ queue."""
    async with message.process():
        try:
            payload = json.loads(message.body.decode())
            async for db in get_db():  # Obtain a DB session
                if payload["event"] == "register_request":
                    response = await handle_registration(db, payload)
                elif payload["event"] == "login_request":
                    response = await handle_login(db, payload)
                else:
                    response = {"status": "error", "message": "Unknown event type"}

                # Send response back to the reply queue
                if message.reply_to:
                    await send_response(channel, message.reply_to, message.correlation_id, response)
        except Exception as e:
            print(f"Error handling message: {e}")


async def handle_registration(db: AsyncSession, payload: dict):
    """Handle user registration."""
    email = payload.get("email")
    password = payload.get("password")

    print("DEBUG: auth_service handle_registration email:", email, "password:", password)

    if not email or not password:
        return {"status": "error", "message": "Username and password are required"}
    print("DEBUG: auth_service handle_registration 1")
    existing_user = await get_user_by_email(db, email)
    print("DEBUG: auth_service handle_registration 2", existing_user)
    if existing_user:
        return {"status": "error", "message": f"User {email} already exists"}

    hashed_password = hash_password(password)
    print("DEBUG: auth_service handle_registration 3")
    # user_data = UserBase(email='www', hashed_password='...', is_active=True) доп вариант передачи ниже
    new_user = await create_user(db, {"email": email, "hashed_password": hashed_password, "is_active": True})
    print("DEBUG: auth_service handle_registration 4")
    return {"status": "success", "message": f"User {email} successfully registered"}


async def handle_login(db: AsyncSession, payload: dict):
    """Handle user login."""
    email = payload.get("email")
    password = payload.get("password")
    print("DEBUG: auth_service handle_login", email, password)

    if not email or not password:
        return {"status": "error", "message": "Username and password are required"}

    user = await get_user_by_email(db, email)

    print("DEBUG: auth_service handle_login user: ", user)
    if user and verify_password(password, user.hashed_password):
        token = create_access_token({"sub": email})
        return {
            "status": "success",
            "message": "Login successful",
            "token": token,
        }
    return {"status": "error", "message": "Invalid username or password"}


async def send_response(channel, reply_to: str, correlation_id: str, response: dict):
    """
    Send a response message to the specified RabbitMQ queue.
    :param channel: RabbitMQ channel
    :param reply_to: Queue to send the response
    :param correlation_id: ID for correlating request and response
    :param response: Response message
    """
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(response).encode(),
                correlation_id=correlation_id,
            ),
            routing_key=reply_to,
        )
    except Exception as e:
        print(f"Error sending response: {e}")
