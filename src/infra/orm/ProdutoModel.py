# Leonardo Stuani Godoi
from infra import database
from sqlalchemy import Column, VARCHAR, Integer, BLOB, Numeric


class ProdutoDB(database.Base):
    __tablename__ = "tb_produto"

    id_produto = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(VARCHAR(100), nullable=False, index=True)
    descricao = Column(VARCHAR(200), nullable=False)
    foto = Column(BLOB, nullable=False)
    valor_unitario = Column(Numeric(11, 2), nullable=False)

    def __init__(self, nome, descricao, foto, valor_unitario):
        self.nome = nome
        self.descricao = descricao
        self.foto = foto
        self.valor_unitario = valor_unitario

