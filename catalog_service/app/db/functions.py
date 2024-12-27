# catalog_service / app / db / functions.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from db.models import Product, Category, Seller
from db.schemas import ProductBase, Product as ProductSchema, CategorySchemas, ProductBase, SellerSchemas

# Получение всех продуктов с пагинацией
async def get_all_products(db: AsyncSession, category: int = None, search: str = '', skip: int = 0, limit: int = 100):
    # print("DEBUG CATALOG FUNCTION, get_all_products, search", search)
    if category:
        if search != '':
            print("DEBUG CATALOG FUNCTION, get_all_products, search", search)
            result = await db.execute(
                select(Product).filter(Product.category_id == category).filter(
                    Product.name.ilike(f"%{search}%")).order_by(Product.name).offset(skip).limit(limit))
        else:
            result = await db.execute(
                select(Product).filter(Product.category_id == category).order_by(Product.name).offset(skip).limit(
                    limit))
    elif search != '':
        result = await db.execute(select(Product).filter(
            Product.name.ilike(f"%{search}%")).order_by(Product.name).offset(skip).limit(limit))
    else:
        result = await db.execute(select(Product).order_by(Product.name).offset(skip).limit(limit))
    products = result.scalars().all()
    products_list = [ProductBase.from_orm(product) for product in products]

    products_dict = [product.dict() for product in products_list]

    return products_dict

# Получение одного продукта
async def get_product_by_id(db: AsyncSession, product_id: int):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    product = result.scalar_one_or_none()
    products_list = ProductBase.from_orm(product)

    products_dict = products_list.dict()
    print("DEBUG CATALOG FUNCTION, get_product_by_id, products_dict", products_dict)
    return products_dict

async def get_all_categories(db: AsyncSession):
    result = await db.execute(select(Category))
    categories = result.scalars().all()

    # Преобразуем SQLAlchemy объекты в Pydantic модели
    categories_list = [CategorySchemas.from_orm(category) for category in categories]

    categories_dict = [category.dict() for category in categories_list]

    return categories_dict

async def get_seller_by_id(db: AsyncSession, seller_id: int):
    result = await db.execute(select(Seller).filter(Seller.id == seller_id))
    seller = result.scalar_one_or_none()
    seller_id_list = SellerSchemas.from_orm(seller)

    seller_id_dict = seller_id_list.dict()
    print("DEBUG CATALOG FUNCTION, get_product_by_id, products_dict", seller_id_dict)
    return seller_id_dict

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