from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse
)

from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db

router = APIRouter()


@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"])
async def get_produtos(db: Session = Depends(get_db)):
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/produto/{id_produto}", response_model=ProdutoResponse, tags=["Produto"])
async def get_produto(id_produto: int, db: Session = Depends(get_db)):
    produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()

    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    return produto


@router.post(
    "/produto/",
    response_model=ProdutoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Produto"]
)
async def post_produto(produto_data: ProdutoCreate, db: Session = Depends(get_db)):
    try:
        novo_produto = ProdutoDB(
            nome=produto_data.nome,
            descricao=produto_data.descricao,
            foto=produto_data.foto,
            valor_unitario=produto_data.valor_unitario
        )

        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)

        return novo_produto

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/produto/{id_produto}", response_model=ProdutoResponse, tags=["Produto"])
async def put_produto(id_produto: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db)):
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()

        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")

        update_data = produto_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(produto, field, value)

        db.commit()
        db.refresh(produto)

        return produto

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/produto/{id_produto}", status_code=status.HTTP_204_NO_CONTENT, tags=["Produto"])
async def delete_produto(id_produto: int, db: Session = Depends(get_db)):
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id_produto == id_produto).first()

        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")

        db.delete(produto)
        db.commit()

        return None

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))