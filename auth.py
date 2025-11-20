from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User

SECRET_KEY = "clavesupersecreta123456789"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 👉 Permite pegar el token en Swagger sin "Bearer"
auth_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials=Depends(auth_scheme), db: Session = Depends(get_db)):
    if credentials is None:
        raise HTTPException(status_code=403, detail="Not authenticated")

    # 👉 Token recibido directamente, sin "Bearer "
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=403, detail="Token inválido")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado")

    return user
