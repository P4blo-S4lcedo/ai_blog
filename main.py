from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import models
from sqlalchemy.orm import Session
from database import Base, engine, get_db
from models import User, Post
from pydantic import BaseModel
from passlib.context import CryptContext
import google.generativeai as genai
from google.generativeai import generative_models, client
import auth
import logging
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="AI Blog API",
    description="API para artículos generados con IA",
    version="1.0"
)

# ---- Swagger personalizado para aceptar token SIN Bearer ----
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "TokenAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Pega aquí tu token SIN la palabra Bearer"
        }
    }

    # Hacer que todas las rutas protegidas usen TokenAuth
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method in ["post", "put", "delete"]:
                openapi_schema["paths"][path][method]["security"] = [{"TokenAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
# ------------------------------------------------------------

# CORS
origins = ["https://P4blo-S4lcedo.github.io"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Schemas
class RegisterSchema(BaseModel):
    email: str
    password: str


class TokenSchema(BaseModel):
    email: str
    password: str


class PostSchema(BaseModel):
    prompt: str


# ------- ENDPOINTS PÚBLICOS -------

@app.post("/register")
def register(user: RegisterSchema, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    hashed_password = pwd_context.hash(user.password[:72])
    db_user = User(email=user.email, password_hash=hashed_password)
    db.add(db_user)

    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"No se pudo registrar: {str(e)}")

    return {"msg": "Usuario creado", "user_id": db_user.id}


@app.post("/token")
def login(user: TokenSchema, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")

    token = auth.create_access_token({"sub": db_user.email})
    return {"access_token": token}


@app.get("/posts")
def list_posts(db: Session = Depends(get_db)):
    posts = db.query(models.Post).all()
    return [
        {"title": p.title, "body": p.body, "author_id": p.author_id, "created_at": p.created_at}
        for p in posts
    ]


# ------- ENDPOINTS PROTEGIDOS -------

@app.post("/generate-post")
def generate_post(
    post: PostSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    genai.configure(api_key="TU_API_KEY")

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt_text = (
        f"Escribe un artículo completo basado en esta idea: {post.prompt}. "
        "Incluye título y cuerpo. Solo el artículo."
    )

    try:
        result = model.generate_content(prompt_text)
        generated_text = result.text or "No se pudo generar el texto"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando contenido: {e}")

    lines = generated_text.split("\n")
    title = lines[0][:255]
    body = "\n".join(lines[1:]).strip()

    db_post = Post(title=title, body=body, author_id=current_user.id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    return {"msg": "Post generado correctamente", "title": title, "body": body}


@app.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso")

    db.delete(post)
    db.commit()

    return {"msg": "Post eliminado correctamente"}
