from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime

from domain.schemas.RecebimentoSchema import (
    RecebimentoDashboardItem,
    RecebimentoDetalheResponse,
    ComandaDetalhe,
    ItemConferencia,
    RecebimentoCompletoRequest,
    RecebimentoCompletoResponse,
    ComandaPaga,
    ComprovanteRecebimento,
)
from domain.schemas.FuncionarioSchema import FuncionarioResponse
from domain.schemas.ClienteSchema import ClienteResponse
from domain.schemas.AuthSchema import FuncionarioAuth

from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ClienteModel import ClienteDB
from infra.orm.RecebimentoModel import RecebimentoDB, RecebimentoComandaDB
from infra.database import get_async_db
from infra.dependencies import require_group
from infra.rate_limit import limiter
from services.AuditoriaService import AuditoriaService

router = APIRouter()

STATUS_ABERTA = 0
STATUS_FECHADA = 1
STATUS_CANCELADA = 2


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cliente_response(cliente: ClienteDB | None) -> ClienteResponse | None:
    if not cliente:
        return None
    return ClienteResponse(
        id=cliente.id,
        nome=cliente.nome,
        cpf=cliente.cpf,
        telefone=cliente.telefone,
        endereco=cliente.endereco,
    )


def _funcionario_response(funcionario: FuncionarioDB) -> FuncionarioResponse:
    return FuncionarioResponse(
        id=funcionario.id,
        nome=funcionario.nome,
        matricula=funcionario.matricula,
        cpf=funcionario.cpf,
        telefone=funcionario.telefone,
        grupo=funcionario.grupo,
    )


async def _montar_detalhe_comanda(db: AsyncSession, comanda: ComandaDB) -> ComandaDetalhe:
    """Monta o detalhe de uma comanda (cliente + itens com foto + total)."""
    # cliente
    cliente = None
    if comanda.cliente_id:
        res = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda.cliente_id))
        cliente = res.scalar_one_or_none()

    # itens (join com produto p/ nome, descrição e foto)
    res = await db.execute(
        select(ComandaProdutoDB, ProdutoDB)
        .outerjoin(ProdutoDB, ComandaProdutoDB.produto_id == ProdutoDB.id_produto)
        .where(ComandaProdutoDB.comanda_id == comanda.id)
    )
    linhas = res.all()

    itens: List[ItemConferencia] = []
    total = 0.0
    for cp, produto in linhas:
        subtotal = float(cp.quantidade) * float(cp.valor_unitario)
        total += subtotal
        itens.append(
            ItemConferencia(
                produto_id=cp.produto_id,
                nome=produto.nome if produto else f"Produto #{cp.produto_id}",
                descricao=produto.descricao if produto else None,
                foto=produto.foto if produto else None,
                quantidade=cp.quantidade,
                valor_unitario=float(cp.valor_unitario),
                subtotal=subtotal,
            )
        )

    return ComandaDetalhe(
        id=comanda.id,
        comanda=comanda.comanda,
        status=comanda.status,
        data_hora=comanda.data_hora,
        cliente=_cliente_response(cliente),
        itens=itens,
        total=total,
    )


# ── Dashboard: comandas abertas ──────────────────────────────────────────────

@router.get(
    "/recebimento/dashboard",
    response_model=List[RecebimentoDashboardItem],
    tags=["Recebimento"],
    summary="Dashboard completo com comandas abertas e fotos - grupo 1 e 3",
)
@limiter.limit("moderate")
async def recebimento_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        # comandas abertas + cliente
        res = await db.execute(
            select(ComandaDB, ClienteDB)
            .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
            .where(ComandaDB.status == STATUS_ABERTA)
        )
        linhas = res.all()

        dashboard: List[RecebimentoDashboardItem] = []
        for comanda, cliente in linhas:
            # total e quantidade de produtos da comanda
            res_itens = await db.execute(
                select(
                    func.coalesce(func.sum(ComandaProdutoDB.quantidade * ComandaProdutoDB.valor_unitario), 0),
                    func.coalesce(func.sum(ComandaProdutoDB.quantidade), 0),
                ).where(ComandaProdutoDB.comanda_id == comanda.id)
            )
            total, qtd = res_itens.one()

            dashboard.append(
                RecebimentoDashboardItem(
                    id=comanda.id,
                    comanda=comanda.comanda,
                    status=comanda.status,
                    cliente=_cliente_response(cliente),
                    total=float(total or 0),
                    quantidade_produtos=int(qtd or 0),
                    data_hora=comanda.data_hora,
                )
            )

        return dashboard

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao montar dashboard de recebimento: {str(e)}",
        )


# ── Detalhe das comandas selecionadas (conferência) ──────────────────────────

@router.get(
    "/recebimento/comandas/detalhe/{comandas_ids}",
    response_model=RecebimentoDetalheResponse,
    tags=["Recebimento"],
    summary="Detalhar comandas para recebimento (produtos, fotos e total) - grupo 1 e 3",
)
@limiter.limit("moderate")
async def detalhar_comandas(
    comandas_ids: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        # aceita ids separados por vírgula: "5,12,3"
        try:
            ids = [int(x) for x in comandas_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IDs de comanda inválidos. Use números separados por vírgula.",
            )

        if not ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe ao menos uma comanda.",
            )

        detalhes: List[ComandaDetalhe] = []
        subtotal_geral = 0.0
        for cid in ids:
            res = await db.execute(select(ComandaDB).where(ComandaDB.id == cid))
            comanda = res.scalar_one_or_none()
            if not comanda:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Comanda {cid} não encontrada.",
                )
            detalhe = await _montar_detalhe_comanda(db, comanda)
            subtotal_geral += detalhe.total
            detalhes.append(detalhe)

        return RecebimentoDetalheResponse(
            comandas=detalhes,
            subtotal_geral=subtotal_geral,
            quantidade_comandas=len(detalhes),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao detalhar comandas: {str(e)}",
        )


# ── Recebimento completo ─────────────────────────────────────────────────────

@router.post(
    "/recebimento/completo",
    response_model=RecebimentoCompletoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Recebimento"],
    summary="Recebimento completo com desconto/acréscimo - grupo 1 e 3",
)
@limiter.limit("restrictive")
async def recebimento_completo(
    dados: RecebimentoCompletoRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        # funcionário responsável pelo recebimento
        res = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == dados.funcionario_id))
        funcionario = res.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Funcionário não encontrado.",
            )

        # cliente (opcional)
        cliente = None
        if dados.cliente_id:
            res = await db.execute(select(ClienteDB).where(ClienteDB.id == dados.cliente_id))
            cliente = res.scalar_one_or_none()
            if not cliente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cliente não encontrado.",
                )

        # carregar e validar todas as comandas (devem estar abertas)
        comandas: List[ComandaDB] = []
        comandas_pagas: List[ComandaPaga] = []
        subtotal_geral = 0.0
        for cid in dados.comandas_ids:
            res = await db.execute(select(ComandaDB).where(ComandaDB.id == cid))
            comanda = res.scalar_one_or_none()
            if not comanda:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Comanda {cid} não encontrada.",
                )
            if comanda.status != STATUS_ABERTA:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Comanda {comanda.comanda} não está aberta e não pode ser recebida.",
                )

            res_sub = await db.execute(
                select(
                    func.coalesce(func.sum(ComandaProdutoDB.quantidade * ComandaProdutoDB.valor_unitario), 0)
                ).where(ComandaProdutoDB.comanda_id == comanda.id)
            )
            subtotal = float(res_sub.scalar() or 0)
            subtotal_geral += subtotal
            comandas.append(comanda)
            comandas_pagas.append(ComandaPaga(id=comanda.id, comanda=comanda.comanda, subtotal=subtotal))

        desconto_total = float(dados.desconto_valor or 0)
        acrescimo_total = float(dados.acrescimo_valor or 0)
        if desconto_total < 0 or acrescimo_total < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Desconto e acréscimo não podem ser negativos.",
            )
        valor_final = max(0.0, subtotal_geral - desconto_total + acrescimo_total)

        agora = datetime.now()

        # 1) registrar o recebimento
        recebimento = RecebimentoDB(
            funcionario_id=funcionario.id,
            cliente_id=cliente.id if cliente else None,
            data_hora=agora,
            subtotal=subtotal_geral,
            desconto_valor=desconto_total,
            acrescimo_valor=acrescimo_total,
            valor_final=valor_final,
        )
        db.add(recebimento)
        await db.flush()  # garante o recebimento.id antes de vincular as comandas

        # 2) vincular comandas, fechá-las e ajustar cliente se informado
        for comanda, paga in zip(comandas, comandas_pagas):
            db.add(RecebimentoComandaDB(
                recebimento_id=recebimento.id,
                comanda_id=comanda.id,
                subtotal=paga.subtotal,
            ))
            comanda.status = STATUS_FECHADA
            if cliente:
                comanda.cliente_id = cliente.id

        await db.commit()
        await db.refresh(recebimento)

        # auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="RECEBIMENTO",
            recurso_id=recebimento.id,
            dados_novos=recebimento,
            request=request,
        )

        return RecebimentoCompletoResponse(
            sucesso=True,
            mensagem=f"Recebimento #{recebimento.id} efetuado com sucesso.",
            recebimento_id=recebimento.id,
            comandas_pagas=comandas_pagas,
            subtotal_geral=subtotal_geral,
            desconto_total=desconto_total,
            acrescimo_total=acrescimo_total,
            valor_final=valor_final,
            cliente=_cliente_response(cliente),
            funcionario=_funcionario_response(funcionario),
            data_hora=agora,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao efetuar recebimento: {str(e)}",
        )


# ── Comprovante ──────────────────────────────────────────────────────────────

@router.get(
    "/recebimento/comprovante/{recebimento_id}",
    response_model=ComprovanteRecebimento,
    tags=["Recebimento"],
    summary="Gerar comprovante de recebimento - grupo 1 e 3",
)
@limiter.limit("moderate")
async def comprovante_recebimento(
    recebimento_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        res = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == recebimento_id))
        recebimento = res.scalar_one_or_none()
        if not recebimento:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recebimento não encontrado.",
            )

        # funcionário responsável
        res = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id))
        funcionario = res.scalar_one_or_none()

        # cliente (opcional)
        cliente = None
        if recebimento.cliente_id:
            res = await db.execute(select(ClienteDB).where(ClienteDB.id == recebimento.cliente_id))
            cliente = res.scalar_one_or_none()

        # comandas quitadas neste recebimento
        res = await db.execute(
            select(RecebimentoComandaDB.comanda_id).where(RecebimentoComandaDB.recebimento_id == recebimento_id)
        )
        comanda_ids = [r[0] for r in res.all()]

        detalhes: List[ComandaDetalhe] = []
        for cid in comanda_ids:
            res = await db.execute(select(ComandaDB).where(ComandaDB.id == cid))
            comanda = res.scalar_one_or_none()
            if comanda:
                detalhes.append(await _montar_detalhe_comanda(db, comanda))

        agora = datetime.now()

        return ComprovanteRecebimento(
            cabecalho={
                "titulo": "COMPROVANTE DE RECEBIMENTO",
                "estabelecimento": "Comandas Stuani",
                "documento": "Não fiscal",
                "recebimento_id": recebimento.id,
            },
            cliente=_cliente_response(cliente),
            funcionario=_funcionario_response(funcionario) if funcionario else None,
            comandas=detalhes,
            resumo_valores={
                "subtotal": float(recebimento.subtotal),
                "desconto": float(recebimento.desconto_valor),
                "acrescimo": float(recebimento.acrescimo_valor),
                "valor_final": float(recebimento.valor_final),
            },
            recebimento={
                "id": recebimento.id,
                "data_hora": recebimento.data_hora.isoformat() if recebimento.data_hora else None,
                "quantidade_comandas": len(detalhes),
            },
            rodape={
                "mensagem": "Obrigado pela preferência! Volte sempre.",
            },
            data_emissao=agora,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar comprovante: {str(e)}",
        )
