from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class ProdutoCreate(BaseModel):
    nome: str
    descricao: str
    foto: bytes
    valor_unitario: Decimal


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    foto: Optional[bytes] = None
    valor_unitario: Optional[Decimal] = None


class ProdutoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_produto: int
    nome: str
    descricao: str
    valor_unitario: Decimal