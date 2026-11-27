"""As 5 buscas do sistema."""
import re
from datetime import date, datetime, time, timedelta

from pymongo.database import Database

from app.regras import FUSO, validar_ponto
from app.sensores import buscar_sensor


def alertas_ativos(db: Database) -> list[dict]:
    """1. Alertas ativos agora, do mais grave para o mais leve."""
    return list(db.alerts.find({"status": "ativo"}).sort([("nivel", -1), ("inicio", -1)]))


def leituras_por_periodo(db: Database, codigo_sensor: str, inicio: datetime, fim: datetime) -> list[dict]:
    """2. Leituras de um sensor num período (limites inclusivos)."""
    sensor = buscar_sensor(db, codigo_sensor)
    if sensor is None:
        raise ValueError(f"Sensor {codigo_sensor} não encontrado")
    filtro = {"sensor_id": sensor["_id"], "ts": {"$gte": inicio, "$lte": fim}}
    return list(db.telemetry.find(filtro).sort("ts", 1))


def resumo_diario(db: Database, dia: date) -> list[dict]:
    """3. Por sensor, no dia local: nº de leituras, temperatura máxima, maior rajada e chuva total."""
    inicio = datetime.combine(dia, time.min, tzinfo=FUSO)
    fim = inicio + timedelta(days=1)
    pipeline = [
        # Leituras com falha ou suspeitas não entram no resumo.
        {"$match": {"ts": {"$gte": inicio, "$lt": fim}, "qualidade": "ok"}},
        {"$group": {
            "_id": "$sensor_id",
            "leituras": {"$sum": 1},
            "temperatura_max": {"$max": "$medidas.temperatura_c"},
            "rajada_max": {"$max": "$medidas.rajada_kmh"},
            "chuva_total": {"$sum": "$medidas.chuva_mm"},
            "chuva_max": {"$max": "$medidas.chuva_mm"},
        }},
    ]
    grupos = list(db.telemetry.aggregate(pipeline))
    sensores = {s["_id"]: s for s in db.sensors.find({"_id": {"$in": [g["_id"] for g in grupos]}})}

    resumo = []
    for g in grupos:
        sensor = sensores.get(g["_id"])
        resumo.append({
            "codigo": sensor["codigo"] if sensor else "?",
            "nome": sensor["nome"] if sensor else "(sensor removido)",
            "leituras": g["leituras"],
            "temperatura_max": g["temperatura_max"],
            "rajada_max": g["rajada_max"],
            # Sem nenhuma medida de chuva no dia (ex.: linígrafo) → None, não 0.
            "chuva_total": g["chuva_total"] if g["chuva_max"] is not None else None,
        })
    return sorted(resumo, key=lambda r: r["nome"])


def sensores_proximos(db: Database, longitude: float, latitude: float, raio_km: float) -> list[dict]:
    """4. Sensores num raio de X km de um ponto, do mais perto para o mais longe."""
    validar_ponto(longitude, latitude)
    if not raio_km >= 0:
        raise ValueError("O raio deve ser zero ou positivo")
    filtro = {"localizacao": {"$near": {
        "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "$maxDistance": raio_km * 1000,
    }}}
    return list(db.sensors.find(filtro))


def alertas_por_bairro(db: Database, bairro: str) -> list[dict]:
    """5. Alertas que já atingiram um bairro (sem diferenciar maiúsculas)."""
    padrao = f"^{re.escape(bairro.strip())}$"
    filtro = {"bairros_afetados": {"$regex": padrao, "$options": "i"}}
    return list(db.alerts.find(filtro).sort("inicio", -1))
