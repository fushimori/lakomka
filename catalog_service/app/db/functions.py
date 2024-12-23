from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from db.models import Product

# Получение всех продуктов с пагинацией
async def get_all_products(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(Product).order_by(Product.name).offset(skip).limit(limit))
    return result.scalars().all()

# Получение одного продукта
async def get_product_by_id(db: AsyncSession, product_id: int):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    return result.scalar_one_or_none()

# Создание нового товара
async def create_product(db: AsyncSession, name: str, description: str, price: float, stock: int, category_id: int, seller_id: int):
    if price < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Price and stock must be non-negative.")
    new_product = Product(
        name=name,
        description=description,
        price=price,
        stock=stock,
        category_id=category_id,
        seller_id=seller_id
    )
    db.add(new_product)
    await db.commit()  # Сохраняем в базу данных
    await db.refresh(new_product)  # Обновляем объект с последними данными из базы
    return new_product

# Обновление продукта
# Обновление продукта
async def update_product(db: AsyncSession, product_id: int, name: str, description: str, price: float, stock: int):
    # Получаем продукт по ID
    product = await get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Проверка на отрицательные значения для цены и количества
    if price < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Price and stock must be non-negative.")
    
    # Обновление данных продукта
    product.name = name
    product.description = description
    product.price = price
    product.stock = stock
    await db.commit()
    await db.refresh(product)
    return product


# Удаление товара
async def delete_product(db: AsyncSession, product_id: int):
    product = await get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
    return product
