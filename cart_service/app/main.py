# cart_service/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from typing import List, AsyncGenerator
from db.schemas import CartItemBase, CartResponse
from db.functions import add_product_to_cart, remove_product_from_cart, update_product_quantity_in_cart, get_cart_items
from db.init_db import init_db
from fastapi.middleware.cors import CORSMiddleware


async def lifespan(app: FastAPI) -> AsyncGenerator:
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
# Получение всех товаров в корзине

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
