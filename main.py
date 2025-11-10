from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base, get_db
from models import User, Post
from pydantic import BaseModel
from passlib.context import CryptContext
import auth
from models import User
import models
import os
import google.generativeai as genai
from google.generativeai import generative_models, client

# Configurar Gemini
genai.configure(api_key="AIzaSyCsl8KyjVYG18AMfJ8B3gGl9D3WsAsBQL0")

model = genai.GenerativeModel("gemini-2.5-flash")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS
origins = ["https://P4blo-S4lcedo.github.io"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schemas
class RegisterSchema(BaseModel):
    email: str
    password: str

class TokenSchema(BaseModel):
    email: str
    password: str

class PostSchema(BaseModel):
    prompt: str

class PostRequest(BaseModel):
    prompt: str 

# Registro
@app.post("/register")
def register(user: RegisterSchema, db: Session = Depends(get_db)):
    # Verificar si el usuario ya existe
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    
    # Hashear la contraseña truncando a 72 caracteres
    hashed_password = pwd_context.hash(user.password[:72])
    
    # Crear objeto User
    db_user = User(email=user.email, password_hash=hashed_password)
    db.add(db_user)
    
    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"No se pudo registrar: {str(e)}")
    
    return {"msg": "Usuario creado", "user_id": db_user.id}

# Login
@app.post("/token")
def login(user: TokenSchema, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")
    token = auth.create_access_token({"sub": db_user.email})
    return {"access_token": token}


@app.post("/generate-post")
def generate_post(post: PostSchema, db: Session = Depends(get_db), token: str = Header(None)):
    """
    Genera un artículo usando IA (Gemini 2.5) basado en el prompt del usuario.
    Guarda el resultado en la base de datos.
    """
    # Verificar usuario (por ahora ejemplo)
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    # Generar contenido usando Gemini 2.5
    prompt_text = f"Escribe un artículo completo basado en esta idea: {post.prompt}. Incluye título y cuerpo."

    try:
        result = model.generate_content(prompt_text)
        generated_text = result.text or "No se pudo generar el texto"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando contenido: {e}")

    # Separar título y cuerpo
    lines = generated_text.split("\n")
    title = lines[0][:255]  # primera línea como título
    body = "\n".join(lines[1:]).strip()  # resto como cuerpo

    # Guardar post en DB
    db_post = Post(title=title, body=body, author_id=user.id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    return {
        "msg": "Post generado correctamente",
        "title": title,
        "body": body
    }


# Listar Posts
@app.get("/posts")
def list_posts(db: Session = Depends(get_db)):
    posts = db.query(models.Post).all()
    return [{"title": p.title, "body": p.body, "author_id": p.author_id, "created_at": p.created_at} for p in posts]
