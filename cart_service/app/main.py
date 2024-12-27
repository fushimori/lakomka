# cart_service/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from typing import List, AsyncGenerator
from db.schemas import CartItemBase, CartResponse
from db.functions import add_product_to_cart, remove_product_from_cart, update_product_quantity_in_cart, get_cart_items, get_cart_by_user_id
from db.init_db import init_db
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordBearer
from db.models import Cart, CartItem
import jwt



SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


async def lifespan(app: FastAPI) -> AsyncGenerator:
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/cart/add")
async def add_to_cart(product_id: int = None, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)
    cart = await add_product_to_cart(db, user_id, product_id)
    print("DEBUG CART SERVICE add_to_cart, user_id:", user_id, "token:", token)# Получаем user_id из токена
    print("DEBUG CART SERVICE add_to_cart, cart:", cart)
    # Здесь логика добавления товара в корзину для user_id
    if cart:
        return {"success": True, "message": "Product added to cart"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add product to cart")


@app.get("/check_cart")
async def check_cart(product_id: int = None, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)  # Проверка токена
    print("DEBUG CART SERVICE check_cart, user_id: ", user_id)
    # Проверка, есть ли корзина у пользователя
    cart = await get_cart_by_user_id(db, user_id)
    print("DEBUG CART SERVICE check_cart, cart: ", cart)
    if not cart:
        return {"exists": False}

    # Проверка, есть ли товар в корзине
    cart_item = await db.execute(
        select(CartItem).filter(
            CartItem.product_id == product_id,
            CartItem.cart_id == cart.id
        )
    )
    cart_item = cart_item.scalar_one_or_none()
    print("DEBUG CART SERVICE check_cart, cart_item: ", cart_item)

    if cart_item:
        return {"exists": True}
    return {"exists": False}


@app.get("/cart/{user_id}")
async def get_cart(user_id: int, db: AsyncSession = Depends(get_db)):
    items = await get_cart_items(db, user_id)
    print("DEBUG: cart items: ", items)
    return items

# Добавление товара в корзину
@app.post("/cart/{user_id}", response_model=CartResponse)
async def add_to_cart(user_id: int, product: CartItemBase, db: AsyncSession = Depends(get_db)):
    cart = await add_product_to_cart(db, user_id, product.product_id, product.quantity)
    return cart

# Обновление количества товара в корзине
@app.put("/cart/{user_id}/{product_id}", response_model=CartResponse)
async def update_cart_item_quantity(user_id: int, product_id: int, quantity: int, db: AsyncSession = Depends(get_db)):
    cart = await update_product_quantity_in_cart(db, user_id, product_id, quantity)
    return cart

# Удаление товара из корзины
@app.delete("/cart/{user_id}/{product_id}", response_model=CartResponse)
async def remove_from_cart(user_id: int, product_id: int, db: AsyncSession = Depends(get_db)):
    cart = await remove_product_from_cart(db, user_id, product_id)
    return cart

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "cart_service running"}
