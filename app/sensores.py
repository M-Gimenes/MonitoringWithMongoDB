"""CRUD da coleção sensors."""
import copy

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.regras import LIMIARES_PADRAO, TIPOS_SENSOR

STATUS_SENSOR = ("operacional", "manutencao", "inativo")


def _validar_status(status: str) -> None:
    if status not in STATUS_SENSOR:
        raise ValueError(f"Status inválido: {status}. Use um de: {', '.join(STATUS_SENSOR)}")


def inserir_sensor(db: Database, dados: dict) -> str:
    for campo in ("codigo", "nome", "tipo"):
        if not dados.get(campo):
            raise ValueError(f"Campo obrigatório ausente: {campo}")
    if dados["tipo"] not in TIPOS_SENSOR:
        raise ValueError(f"Tipo inválido: {dados['tipo']}. Use um de: {', '.join(TIPOS_SENSOR)}")

    doc = {chave: valor for chave, valor in dados.items() if valor is not None}
    doc.setdefault("status", "operacional")
    doc.setdefault("limiares", copy.deepcopy(LIMIARES_PADRAO[doc["tipo"]]))
    _validar_status(doc["status"])

    try:
        db.sensors.insert_one(doc)
    except DuplicateKeyError:
        raise ValueError(f"Já existe um sensor com o código {doc['codigo']}") from None
    return doc["codigo"]


def listar_sensores(db: Database, tipo: str | None = None) -> list[dict]:
    filtro = {"tipo": tipo} if tipo else {}
    return list(db.sensors.find(filtro).sort("codigo", 1))


def buscar_sensor(db: Database, codigo: str) -> dict | None:
    return db.sensors.find_one({"codigo": codigo})


def atualizar_sensor(db: Database, codigo: str, campos: dict) -> bool:
    campos = {k: v for k, v in campos.items() if k not in ("codigo", "_id")}
    if "status" in campos:
        _validar_status(campos["status"])
    if not campos:
        return buscar_sensor(db, codigo) is not None
    resultado = db.sensors.update_one({"codigo": codigo}, {"$set": campos})
    return resultado.matched_count == 1


def remover_sensor(db: Database, codigo: str) -> bool:
    return db.sensors.delete_one({"codigo": codigo}).deleted_count == 1
