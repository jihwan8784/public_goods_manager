import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select

load_dotenv()  # .env 파일 읽기

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///shop.db")

# 통역사(psycopg2)를 주소에 직접 지정 (Vercel에서 No module named 'psycopg' 방지)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class CustomerIn(SQLModel):  # 입력 형식
    name: str
    email: str
    product: str


class Customer(CustomerIn, table=True):  # DB 표
    id: int | None = Field(default=None, primary_key=True)


SQLModel.metadata.create_all(engine)  # 표 만들기

app = FastAPI(title="동아고등학교 쇼핑몰 API")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "동아고 쇼핑몰 서버가 동작 중입니다"}


@app.get("/customers")
def get_customers():
    with Session(engine) as session:
        return session.exec(select(Customer)).all()


@app.post("/customers")
def create_customer(customer: CustomerIn):
    with Session(engine) as session:
        new = Customer.model_validate(customer)
        session.add(new)
        session.commit()
        session.refresh(new)
        return new
