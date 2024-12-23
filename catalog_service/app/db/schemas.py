# catalog_service/app/db/schemas.py

from pydantic import BaseModel
from typing import List, Optional

# Схема для изображения товара
class ProductImageBase(BaseModel):
    image_url: str

    class Config:
        orm_mode = True  # Это важно для работы с SQLAlchemy моделями

# Схема для товара (Product)
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    active: bool
    category_id: int
    seller_id: int

    class Config:
        orm_mode = True

class Product(ProductBase):
    id: int
    category: Optional["Category"] = None  # Для связанного объекта Category
    seller: Optional["Seller"] = None  # Для связанного объекта Seller
    images: List[ProductImageBase] = []  # Список изображений товара

    class Config:
        orm_mode = True

class ProductImageBase(BaseModel):
    image_url: str  # Ссылка на изображение товара

    class Config:
        orm_mode = True  # Указываем, что это работает с SQLAlchemy моделями


# Схема для категории (Category)
class Category(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

# Схема для продавца (Seller)
class Seller(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True

# Схема для отзыва о товаре (Review)
class Review(BaseModel):
    id: int
    rating: int
    comment: Optional[str] = None

    class Config:
        orm_mode = True

# Схема для вопроса о товаре (Question)
class Question(BaseModel):
    id: int
    question: str
    answer: Optional[str] = None

    class Config:
        orm_mode = True

# Схема для связанного товара (RelatedProduct)
class RelatedProductBase(BaseModel):
    product_id: int
    related_product_id: int

    class Config:
        orm_mode = True
