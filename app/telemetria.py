"""Leituras dos sensores (coleção time-series telemetry)."""
from datetime import datetime, timezone

from pymongo.database import Database

from app.alertas import processar_leitura
from app.sensores import buscar_sensor

QUALIDADES = ("ok", "suspeito", "falha")


def _sensor_ou_erro(db: Database, codigo: str) -> dict:
    sensor = buscar_sensor(db, codigo)
    if sensor is None:
        raise ValueError(f"Sensor {codigo} não encontrado")
    return sensor


def registrar_leitura(
    db: Database,
    codigo_sensor: str,
    medidas: dict,
    ts: datetime | None = None,
    qualidade: str = "ok",
) -> list[dict]:
    """Grava a leitura e devolve os alertas criados ou elevados por ela.

    Leituras com qualidade diferente de "ok" são gravadas, mas não geram alerta.
    """
    if qualidade not in QUALIDADES:
        raise ValueError(f"Qualidade inválida: {qualidade}. Use um de: {', '.join(QUALIDADES)}")
    sensor = _sensor_ou_erro(db, codigo_sensor)
    ts = ts or datetime.now(timezone.utc)
    db.telemetry.insert_one(
        {"ts": ts, "sensor_id": sensor["_id"], "medidas": medidas, "qualidade": qualidade}
    )
    if qualidade != "ok":
        return []
    return processar_leitura(db, sensor, medidas, ts)


def listar_leituras(db: Database, codigo_sensor: str | None = None, limite: int = 20) -> list[dict]:
    filtro = {}
    if codigo_sensor:
        filtro["sensor_id"] = _sensor_ou_erro(db, codigo_sensor)["_id"]
    return list(db.telemetry.find(filtro).sort("ts", -1).limit(limite))


def remover_leituras(
    db: Database, inicio: datetime, fim: datetime, codigo_sensor: str | None = None
) -> int:
    filtro = {"ts": {"$gte": inicio, "$lte": fim}}
    if codigo_sensor:
        filtro["sensor_id"] = _sensor_ou_erro(db, codigo_sensor)["_id"]
    return db.telemetry.delete_many(filtro).deleted_count
