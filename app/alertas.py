"""Alertas: geração automática a partir das leituras e CRUD da coleção alerts."""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.regras import ORIENTACOES, avaliar_medidas, canais_por_nivel, tipo_alerta

STATUS_ALERTA = ("ativo", "encerrado", "falso_positivo")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def processar_leitura(db: Database, sensor: dict, medidas: dict, ts: datetime) -> list[dict]:
    """Cria ou eleva alertas conforme os limiares do sensor.

    Devolve só os alertas criados ou com nível elevado.
    """
    alterados = []
    for item in avaliar_medidas(sensor.get("limiares", {}), medidas):
        existente = db.alerts.find_one({
            "status": "ativo",
            "gatilho.sensor_id": sensor["_id"],
            "gatilho.variavel": item["variavel"],
        })
        if existente is None:
            tipo = tipo_alerta(item["variavel"], sensor)
            alerta = {
                "tipo": tipo,
                "nivel": item["nivel"],
                "inicio": ts,
                "fim": None,
                "gatilho": {
                    "sensor_id": sensor["_id"],
                    "variavel": item["variavel"],
                    "valor_observado": item["valor_observado"],
                    "limiar": item["limiar"],
                },
                "bairros_afetados": [sensor.get("bairro") or sensor["municipio"]],
                "orientacao": ORIENTACOES[tipo],
                "canais": canais_por_nivel(item["nivel"]),
                "status": "ativo",
            }
            db.alerts.insert_one(alerta)
            alterados.append(alerta)
        elif item["nivel"] > existente["nivel"]:
            atualizado = db.alerts.find_one_and_update(
                {"_id": existente["_id"]},
                {"$set": {
                    "nivel": item["nivel"],
                    "gatilho.valor_observado": item["valor_observado"],
                    "gatilho.limiar": item["limiar"],
                    "canais": canais_por_nivel(item["nivel"]),
                }},
                return_document=ReturnDocument.AFTER,
            )
            alterados.append(atualizado)
    return alterados


def inserir_alerta(db: Database, dados: dict) -> ObjectId:
    if not dados.get("tipo") or not dados.get("nivel"):
        raise ValueError("Informe tipo e nivel do alerta")
    if dados["tipo"] not in ORIENTACOES:
        raise ValueError(f"Tipo de alerta inválido: {dados['tipo']}")
    if dados["nivel"] not in (1, 2, 3):
        raise ValueError("O nível deve ser 1, 2 ou 3")
    alerta = {
        "inicio": _agora(),
        "fim": None,
        "gatilho": None,
        "bairros_afetados": [],
        "orientacao": ORIENTACOES[dados["tipo"]],
        "canais": canais_por_nivel(dados["nivel"]),
        "status": "ativo",
        **dados,
    }
    return db.alerts.insert_one(alerta).inserted_id


def listar_alertas(db: Database, status: str | None = None) -> list[dict]:
    filtro = {"status": status} if status else {}
    return list(db.alerts.find(filtro).sort("inicio", -1))


def atualizar_alerta(db: Database, alerta_id: ObjectId, campos: dict) -> bool:
    campos = {k: v for k, v in campos.items() if k != "_id"}
    if not campos:
        return db.alerts.count_documents({"_id": alerta_id}) == 1
    return db.alerts.update_one({"_id": alerta_id}, {"$set": campos}).matched_count == 1


def encerrar_alerta(
    db: Database, alerta_id: ObjectId, status: str = "encerrado", fim: datetime | None = None
) -> bool:
    if status not in ("encerrado", "falso_positivo"):
        raise ValueError("Para encerrar, use o status 'encerrado' ou 'falso_positivo'")
    return atualizar_alerta(db, alerta_id, {"status": status, "fim": fim or _agora()})


def remover_alerta(db: Database, alerta_id: ObjectId) -> bool:
    return db.alerts.delete_one({"_id": alerta_id}).deleted_count == 1
