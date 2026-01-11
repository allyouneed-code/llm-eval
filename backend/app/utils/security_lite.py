import hashlib
import hmac
import secrets
import json
import base64
import time
from typing import Optional

# === 配置 ===
# 注意：在生产环境中，这个 KEY 应该改为从环境变量读取，或者设置一个非常复杂的随机字符串
SECRET_KEY = "CHANGE_THIS_TO_A_LONG_RANDOM_STRING_IN_PROD"
ALGORITHM = "HS256"

# ---------------------------------------------------------
# 1. 密码哈希 (替代 passlib/bcrypt)
# ---------------------------------------------------------

def hash_password(password: str) -> str:
    """
    使用 PBKDF2_HMAC_SHA256 进行加盐哈希。
    这是 NIST 推荐的标准算法之一，足够安全。
    """
    salt = secrets.token_hex(16) # 生成随机盐值
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000 # 迭代 10万次，增加破解成本
    )
    # 存储格式: salt$hashed_key
    return f"{salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证输入的明文密码是否与数据库中的哈希匹配
    """
    try:
        salt, key = hashed_password.split('$')
        new_key = hashlib.pbkdf2_hmac(
            'sha256', 
            plain_password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        )
        # 使用 hmac.compare_digest 防止时序攻击 (Timing Attack)
        return hmac.compare_digest(new_key.hex(), key)
    except Exception:
        return False

# ---------------------------------------------------------
# 2. Token 生成 (替代 python-jose/jwt)
# ---------------------------------------------------------

def create_access_token(data: dict, expires_seconds: int = 3600 * 24) -> str:
    """
    生成一个简单的签名 Token (机制类似 JWT，但完全手写零依赖)
    格式: Base64(JsonPayload).Signature
    """
    payload = data.copy()
    payload["exp"] = int(time.time()) + expires_seconds
    
    # 序列化为 JSON 并 Base64 编码
    json_str = json.dumps(payload, separators=(",", ":"))
    b64_payload = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
    
    # 计算签名
    signature = hmac.new(
        SECRET_KEY.encode(), 
        b64_payload.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    return f"{b64_payload}.{signature}"

def decode_access_token(token: str) -> Optional[dict]:
    """
    验证签名并解析 Token 内容
    """
    try:
        if not token or "." not in token:
            return None
            
        b64_payload, signature = token.split('.')
        
        # 1. 重新计算签名进行比对
        expected_sig = hmac.new(
            SECRET_KEY.encode(), 
            b64_payload.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None # 签名无效，Token 被篡改
            
        # 2. 解码 Payload (Base64 需要补全 padding)
        padding = '=' * (4 - len(b64_payload) % 4)
        json_str = base64.urlsafe_b64decode(b64_payload + padding).decode()
        payload = json.loads(json_str)
        
        # 3. 检查是否过期
        if payload.get("exp", 0) < time.time():
            return None # 已过期
            
        return payload
    except Exception:
        return None