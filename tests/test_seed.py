from datetime import datetime, timezone

from app.seed import popular

AGORA = datetime(2026, 11, 27, 21, 0, tzinfo=timezone.utc)


def test_popular(db):
    cont = popular(db, dias=3, agora=AGORA)
    assert cont["sensors"] == 5 == db.sensors.count_documents({})
    assert cont["telemetry"] == db.telemetry.count_documents({}) > 0
    tipos = set(db.alerts.distinct("tipo"))
    assert {"chuva_intensa", "deslizamento", "enchente", "calor_extremo"} <= tipos
    assert db.alerts.count_documents({"status": "ativo"}) >= 1
    assert db.alerts.count_documents({"status": "encerrado"}) >= 1


def test_rio_nao_despenca_de_uma_hora_para_outra(db):
    popular(db, dias=3, agora=AGORA)
    sensor = db.sensors.find_one({"codigo": "CI-LIN-01"})
    niveis = [l["medidas"]["nivel_m"] for l in db.telemetry.find({"sensor_id": sensor["_id"]}).sort("ts", 1)]
    assert max(abs(b - a) for a, b in zip(niveis, niveis[1:])) < 0.6


def test_popular_duas_vezes_da_o_mesmo_resultado(db):
    assert popular(db, dias=3, agora=AGORA) == popular(db, dias=3, agora=AGORA)
