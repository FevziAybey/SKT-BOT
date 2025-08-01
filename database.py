from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///skt_bot.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    products = relationship("Product", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    expiry_date = Column(Date, nullable=False)
    category = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="products")

def init_db():
    Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Kullanıcı işlemleri
def create_user(db, telegram_id, username):
    user = User(telegram_id=telegram_id, username=username)
    db.add(user)
    db.commit()
    return user

def get_user(db, telegram_id):
    return db.query(User).filter(User.telegram_id == telegram_id).first()

# Ürün işlemleri
def add_product(db, user_id, name, expiry_date, category=None, description=None):
    product = Product(
        name=name,
        expiry_date=expiry_date,
        category=category,
        description=description,
        user_id=user_id
    )
    db.add(product)
    db.commit()
    return product

def get_user_products(db, user_id):
    return db.query(Product).filter(Product.user_id == user_id).order_by(Product.expiry_date).all()

def get_expiring_products(db, days=7):
    from datetime import date, timedelta
    target_date = date.today() + timedelta(days=days)
    return db.query(Product).filter(Product.expiry_date <= target_date).all()

def delete_product(db, product_id, user_id):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == user_id
    ).first()
    if product:
        db.delete(product)
        db.commit()
        return True
    return False

def update_product(db, product_id, user_id, **kwargs):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == user_id
    ).first()
    if product:
        for key, value in kwargs.items():
            setattr(product, key, value)
        db.commit()
        return product
    return None 