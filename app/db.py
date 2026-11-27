"""Conexão com o MongoDB e criação das coleções."""
import os

from pymongo import ASCENDING, GEOSPHERE, MongoClient
from pymongo.database import Database

DB_NAME = "risco_ambiental"
URI_PADRAO = "mongodb://localhost:27017"


def get_db(nome: str = DB_NAME, uri: str | None = None) -> Database:
    uri = uri or os.environ.get("MONGO_URI", URI_PADRAO)
    cliente = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=3000)
    return cliente[nome]


def criar_colecoes(db: Database) -> None:
    """Cria as coleções e índices. Pode ser chamada várias vezes."""
    existentes = set(db.list_collection_names())
    if "sensors" not in existentes:
        db.create_collection("sensors")
    if "telemetry" not in existentes:
        db.create_collection(
            "telemetry",
            timeseries={"timeField": "ts", "metaField": "sensor_id", "granularity": "minutes"},
        )
    if "alerts" not in existentes:
        db.create_collection("alerts")

    db.sensors.create_index([("codigo", ASCENDING)], unique=True)
    db.sensors.create_index([("localizacao", GEOSPHERE)])
