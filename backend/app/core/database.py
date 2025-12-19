import os
from sqlmodel import Session, create_engine

# 优先从环境变量获取，否则使用默认的 SQLite
# Docker 中我们将设置为: mysql+pymysql://user:password@db:3306/opencompass_db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")

connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)

def get_session():
    with Session(engine) as session:
        yield session