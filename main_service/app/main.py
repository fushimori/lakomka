# main_service/app/main.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid
import json
import time
import jwt
import httpx
import aio_pika
import asyncio

app = FastAPI()

# RabbitMQ connection setup
RABBITMQ_HOST = "rabbitmq"

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

AUTH_SERVICE_URL = "http://auth_service:8001"
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"


def decode_jwt(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


TIMEOUT = 5  # Максимальное время ожидания ответа в секундах


async def connection_rabbit():
    """Подключение к RabbitMQ с использованием aio_pika."""
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    channel = await connection.channel()
    return connection, channel


async def send_request_and_wait_for_response(message):
    """Send a request to RabbitMQ and wait for a response with a timeout."""
    try:
        connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
        channel = await connection.channel()
    except Exception as e:
        return {"error": f"RabbitMQ is not ready: {str(e)}"}

    # Declare a callback queue for the response
    result = await channel.declare_queue('', exclusive=False, auto_delete=True)
    callback_queue = result.name  # Используем result.name для получения имени очереди

    correlation_id = str(uuid.uuid4())

    response = None
    start_time = time.time()

    # Create a message handler for the response
    async def on_response(message: aio_pika.IncomingMessage):
        nonlocal response
        async with message.process():
            if message.properties.correlation_id == correlation_id:
                response = json.loads(message.body.decode())

    # Start consuming messages from the callback queue
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            reply_to=callback_queue,
            correlation_id=correlation_id
        ),
        routing_key='user_events'
    )

    # Start listening for responses
    await result.consume(on_response)

    print("Waiting for response...")

    # Wait for the response with timeout
    while response is None:
        await asyncio.sleep(0.1)  # Avoid blocking the event loop
        if time.time() - start_time > TIMEOUT:
            await connection.close()
            return {"error": "Request timed out. Please try again later."}

    await connection.close()
    return response


@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    try:
        jwt_token = request.cookies.get("access_token")
        if jwt_token:
            email = decode_jwt(jwt_token)

        else:
            email = None
    except HTTPException as e:
        print(f"DEBUG main service: JWT error - {e.detail}")
        email = None
    print("DEBUG: main_service check cookies: email - ", email)

    categories = [
        {"id": 1, "name": "Laptops"},
        {"id": 2, "name": "Desktops"},
        {"id": 3, "name": "Accessories"}
    ]

    products = [
        {"id": 1, "name": "MacBook Pro 16\"", "price": 2499.99, "image": "/static/images/macbook.jpg",
         "category_id": 1},
        {"id": 2, "name": "Dell XPS 15", "price": 1899.99, "image": "/static/images/dell.jpg", "category_id": 1},
        {"id": 3, "name": "Gaming Desktop", "price": 1499.99, "image": "/static/images/gaming_desktop.jpg",
         "category_id": 2}
    ]

    return templates.TemplateResponse("index.html", {"request": request, "email": email, "categories": categories, "products": products})

@app.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request):
    """Рендерит профиль с данными, полученными через API."""
    jwt_token = request.cookies.get("access_token")
    
    if not jwt_token:
        print("DEBUG: No JWT token found in cookies")
        return RedirectResponse(url="/login", status_code=303)

    try:
        # Декодируем payload
        email = decode_jwt(jwt_token)
        if not email:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: email not found"
            )
        print(f"DEBUG: Decoded JWT token for email: {email}")
    except HTTPException as e:
        print(f"DEBUG: JWT decoding error: {e.detail}")
        return RedirectResponse(url="/login", status_code=303)

    profile_data = None  # Инициализация переменной

    try:
        async with httpx.AsyncClient() as client:
            print(f"DEBUG: Sending request to auth_service for profile data with payload: {email}")
            response = await client.get(
                f"{AUTH_SERVICE_URL}/profile?email={email}",  # Переход на эндпоинт с email
            )
            response.raise_for_status()
            profile_data = response.json()  # Присваиваем данные профиля
            print(f"DEBUG: Received profile data from auth_service: {profile_data}")
    except httpx.HTTPStatusError as e:
        print(f"DEBUG: Error fetching profile from auth_service - Status: {e.response.status_code}, Body: {e.response.text}")
        return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        print(f"DEBUG: Unexpected error fetching profile from auth_service: {str(e)}")
        return RedirectResponse(url="/", status_code=500)

    if profile_data is None:
        print("DEBUG: No profile data received, redirecting to login.")
        return RedirectResponse(url="/login", status_code=303)
    print("Profile data being passed to template:", profile_data)

    return templates.TemplateResponse("profile.html", {"request": request, "profile": profile_data})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    """Send a registration request to the auth service."""
    message = {"event": "register_request", "email": email, "password": password}
    response = await send_request_and_wait_for_response(message)
    return response


@app.post("/login")
async def login_action(email: str = Form(...), password: str = Form(...)):
    """Send a login request to the auth service."""
    print("DEBUG: main_service in post login")
    message = {"event": "login_request", "email": email, "password": password}
    response = await send_request_and_wait_for_response(message)
    if response.get("status") == "success":
        token = response.get("token")
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="access_token", value=token, httponly=True, secure=True)
        return response
    else:
        return response


@app.get("/logout")
async def logout(response: Response):
    """Удаление токена и данных пользователя."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("user_data")
    return response