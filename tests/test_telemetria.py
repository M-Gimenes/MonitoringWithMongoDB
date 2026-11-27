from datetime import datetime, timedelta, timezone

import pytest

from app.sensores import inserir_sensor
from app.telemetria import listar_leituras, registrar_leitura, remover_leituras

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def pluv(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())


def test_grava_leitura(db, pluv):
    assert registrar_leitura(db, "CI-PLU-03", {"chuva_mm": 1.0}, ts=T0) == []
    doc = db.telemetry.find_one()
    assert doc["ts"] == T0 and doc["medidas"] == {"chuva_mm": 1.0} and doc["qualidade"] == "ok"


def test_leitura_acima_gera_alerta(db, pluv):
    [a] = registrar_leitura(db, "CI-PLU-03", {"chuva_1h_mm": 34.2}, ts=T0)
    assert a["tipo"] == "chuva_intensa"


@pytest.mark.parametrize("q", ["falha", "suspeito"])
def test_qualidade_ruim_nao_gera_alerta(db, pluv, q):
    assert registrar_leitura(db, "CI-PLU-03", {"chuva_1h_mm": 99}, ts=T0, qualidade=q) == []
    assert db.alerts.count_documents({}) == 0
    assert db.telemetry.count_documents({}) == 1


def test_sensor_inexistente(db):
    with pytest.raises(ValueError, match="XX-01"):
        registrar_leitura(db, "XX-01", {"chuva_mm": 1})


def test_listar_e_remover(db, pluv, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="CI-PLU-05"))
    for h in range(5):
        registrar_leitura(db, "CI-PLU-03", {"chuva_mm": h}, ts=T0 + timedelta(hours=h))
    registrar_leitura(db, "CI-PLU-05", {"chuva_mm": 0}, ts=T0)
    ultimas = listar_leituras(db, "CI-PLU-03", limite=2)
    assert [l["ts"] for l in ultimas] == [T0 + timedelta(hours=4), T0 + timedelta(hours=3)]
    assert len(listar_leituras(db)) == 6
    assert remover_leituras(db, T0 + timedelta(hours=1), T0 + timedelta(hours=3), "CI-PLU-03") == 3
    assert db.telemetry.count_documents({}) == 3
