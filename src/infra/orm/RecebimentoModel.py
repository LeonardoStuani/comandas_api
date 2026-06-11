from sqlalchemy import Column, Integer, DateTime, DECIMAL, ForeignKey
from infra.database import Base


# Registro de um recebimento (pagamento) efetuado no caixa.
# Guarda o funcionário responsável, o cliente (se informado), a data/hora da
# transação e os valores (subtotal, descontos/acréscimos e valor final).
class RecebimentoDB(Base):
    __tablename__ = "tb_recebimento"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("tb_funcionario.id", ondelete="RESTRICT"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("tb_cliente.id", ondelete="RESTRICT"), nullable=True, default=None)
    data_hora = Column(DateTime, nullable=False)
    subtotal = Column(DECIMAL(10, 2), nullable=False, default=0)
    desconto_valor = Column(DECIMAL(10, 2), nullable=False, default=0)
    acrescimo_valor = Column(DECIMAL(10, 2), nullable=False, default=0)
    valor_final = Column(DECIMAL(10, 2), nullable=False, default=0)


# Comandas envolvidas em um recebimento (uma transação pode quitar várias).
class RecebimentoComandaDB(Base):
    __tablename__ = "tb_recebimento_comanda"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    recebimento_id = Column(Integer, ForeignKey("tb_recebimento.id", ondelete="CASCADE"), nullable=False)
    comanda_id = Column(Integer, ForeignKey("tb_comanda.id", ondelete="RESTRICT"), nullable=False)
    subtotal = Column(DECIMAL(10, 2), nullable=False, default=0)
