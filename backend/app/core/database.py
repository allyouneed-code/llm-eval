# backend/app/core/database.py
from sqlmodel import Session, create_engine

# 1. 数据库 URL 配置
DATABASE_URL = "sqlite:///./local_dev.db"

# 2. 创建 Engine
# connect_args={"check_same_thread": False} 是 SQLite 必须的
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

# 3. 定义依赖注入函数 (get_session)
# 以前写在 router 里，现在放这里，大家都来这里引用
def get_session():
    with Session(engine) as session:
        yield session