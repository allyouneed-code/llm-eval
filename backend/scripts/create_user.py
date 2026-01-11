# backend/scripts/create_user.py
import sys
import os

# 将 backend 目录加入 python 路径，以便导入 app 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.utils.security_lite import hash_password

def create_user(username, password, role="user"):
    with Session(engine) as session:
        # 1. 查重
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing:
            print(f"❌ 用户 {username} 已存在！")
            return

        # 2. 创建
        user = User(
            username=username,
            hashed_password=hash_password(password),
            role=role,
            is_active=True
        )
        session.add(user)
        session.commit()
        print(f"✅ 用户 {username} (角色: {role}) 创建成功！")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python scripts/create_user.py <username> <password> [role]")
        print("示例: python scripts/create_user.py new_dev 123456 user")
    else:
        u = sys.argv[1]
        p = sys.argv[2]
        r = sys.argv[3] if len(sys.argv) > 3 else "user"
        create_user(u, p, r)