#Leonardo Stuani Godoi
from fastapi import FastAPI
from typer.cli import app
from settings import HOST, PORT, RELOAD
import uvicorn

from routers.FuncionarioRouter import router as funcionario_router
from routers.ClienteRouter import router as cliente_router

app = FastAPI()

app.include_router(funcionario_router)
app.include_router(cliente_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=RELOAD)

# rota padrão
@app.get("/", tags=["Root"], status_code=200)
def root():
    return {"detail":"API Pastelaria", "Swagger UI": "http://127.0.0.1:8000/docs", "ReDoc": "http://127.0.0.1:8000/redoc" }