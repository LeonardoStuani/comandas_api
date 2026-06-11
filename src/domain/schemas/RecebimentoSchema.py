from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from domain.schemas.FuncionarioSchema import FuncionarioResponse
from domain.schemas.ClienteSchema import ClienteResponse


# ── Dashboard ───────────────────────────────────────────────────────────────

class RecebimentoDashboardItem(BaseModel):
    """Item do dashboard simplificado - produtos são mostrados no detalhe."""
    id: int
    comanda: str
    status: int
    cliente: Optional[ClienteResponse] = None
    total: float
    quantidade_produtos: int
    data_hora: datetime


# ── Detalhe das comandas (conferência) ──────────────────────────────────────

class ItemConferencia(BaseModel):
    produto_id: int
    nome: str
    descricao: Optional[str] = None
    foto: Optional[bytes] = None
    quantidade: int
    valor_unitario: float
    subtotal: float


class ComandaDetalhe(BaseModel):
    id: int
    comanda: str
    status: int
    data_hora: datetime
    cliente: Optional[ClienteResponse] = None
    itens: List[ItemConferencia]
    total: float


class RecebimentoDetalheResponse(BaseModel):
    comandas: List[ComandaDetalhe]
    subtotal_geral: float
    quantidade_comandas: int


# ── Recebimento completo ─────────────────────────────────────────────────────

class RecebimentoCompletoRequest(BaseModel):
    """Request completa para recebimento com desconto/acréscimo por valor."""
    comandas_ids: List[int] = Field(..., min_length=1)
    cliente_id: Optional[int] = None
    funcionario_id: int
    desconto_valor: Optional[float] = None
    acrescimo_valor: Optional[float] = None


class ComandaPaga(BaseModel):
    id: int
    comanda: str
    subtotal: float


class RecebimentoCompletoResponse(BaseModel):
    """Response completa do recebimento realizado."""
    sucesso: bool
    mensagem: str
    recebimento_id: int
    comandas_pagas: List[ComandaPaga]
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float
    cliente: Optional[ClienteResponse] = None
    funcionario: FuncionarioResponse
    data_hora: datetime


# ── Comprovante ──────────────────────────────────────────────────────────────

class ComprovanteRecebimento(BaseModel):
    """Comprovante detalhado do recebimento."""
    cabecalho: Dict[str, Any]
    cliente: Optional[ClienteResponse] = None
    funcionario: Optional[FuncionarioResponse] = None
    comandas: List[ComandaDetalhe]
    resumo_valores: Dict[str, Any]
    recebimento: Dict[str, Any]
    rodape: Dict[str, Any]
    data_emissao: datetime
