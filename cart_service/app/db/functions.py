# cart_service/app/db/functions.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from db.models import Cart, CartItem
from sqlalchemy.orm import joinedload
from sqlalchemy import text

async def get_cart_items(db: AsyncSession, user_id: int):
    """
    Получить товары из корзины пользователя.
    """
    # Запрос для получения корзины пользователя
    cart_result = await db.execute(select(Cart).filter(Cart.user_id == user_id))
    cart = cart_result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    # Запрос для получения товаров в корзине
    cart_items_result = await db.execute(select(CartItem).filter(CartItem.cart_id == cart.id))
    cart_items = cart_items_result.scalars().all()

    # Формируем список товаров
    items = [
        {"product_id": item.product_id, "quantity": item.quantity}
        for item in cart_items
    ]
    print("DEBUG: cart items: ", items)

    return items

# Получение корзины по ID пользователя
async def get_cart_by_user_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(Cart).filter(Cart.user_id == user_id))
    return result.scalar_one_or_none()

# Добавление товара в корзину
async def add_product_to_cart(db: AsyncSession, user_id: int, product_id: int, quantity: int = 1):
    # Проверим, есть ли корзина для данного пользователя
    cart = await get_cart_by_user_id(db, user_id)
    print("DEBUG CART SERVICE add_product_to_cart, cart: ", cart)
    if not cart:
        # Если корзины нет, создадим новую
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    # Проверим, есть ли уже товар в корзине
    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if cart_item:
        # Если товар уже есть в корзине, обновим его количество
        cart_item.quantity += quantity
    else:
        # Если товара нет в корзине, добавим новый элемент
        new_item = CartItem(product_id=product_id, quantity=quantity, cart_id=cart.id)
        db.add(new_item)
    
    await db.commit()
    return cart

# Удаление товара из корзины
async def remove_product_from_cart(db: AsyncSession, user_id: int, product_id: int):
    # Получаем корзину пользователя
    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Ищем товар в корзине
    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Product not found in the cart")

    # Удаляем товар
    await db.delete(cart_item)
    await db.commit()
    return cart

# Обновление количества товара в корзине
async def update_product_quantity_in_cart(db: AsyncSession, user_id: int, product_id: int, quantity: int):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")

    # Получаем корзину пользователя
    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Ищем товар в корзине
    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Product not found in the cart")

    # Обновляем количество
    cart_item.quantity = quantity
    await db.commit()
    return cart

# Получение всех товаров в корзине
async def get_all_cart_items(db: AsyncSession, user_id: int):
    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Возвращаем список товаров в корзине
    return cart.items
