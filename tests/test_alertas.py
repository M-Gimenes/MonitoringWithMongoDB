from datetime import datetime, timezone

import pytest

from app.alertas import (
    atualizar_alerta,
    encerrar_alerta,
    inserir_alerta,
    listar_alertas,
    processar_leitura,
    remover_alerta,
)
from app.regras import ORIENTACOES
from app.sensores import buscar_sensor, inserir_sensor

TS = datetime(2026, 11, 27, 13, 10, tzinfo=timezone.utc)


@pytest.fixture
def pluv(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    return buscar_sensor(db, "CI-PLU-03")


def test_cria_alerta_completo(db, pluv):
    [a] = processar_leitura(db, pluv, {"chuva_1h_mm": 34.2}, TS)
    assert a["tipo"] == "chuva_intensa" and a["nivel"] == 2 and a["status"] == "ativo"
    assert a["inicio"] == TS and a["fim"] is None
    assert a["gatilho"] == {
        "sensor_id": pluv["_id"], "variavel": "chuva_1h_mm", "valor_observado": 34.2, "limiar": 30,
    }
    assert a["bairros_afetados"] == ["Gilson Carone"]
    assert a["canais"] == ["sms_40199", "site_prefeitura"]
    assert a["orientacao"] == ORIENTACOES["chuva_intensa"]


def test_duas_variaveis_dois_alertas(db, pluv):
    alertas = processar_leitura(db, pluv, {"chuva_1h_mm": 34, "chuva_24h_mm": 55}, TS)
    assert {a["tipo"] for a in alertas} == {"chuva_intensa", "deslizamento"}


def test_nao_duplica_sobe_mas_nao_desce(db, pluv):
    processar_leitura(db, pluv, {"chuva_1h_mm": 34}, TS)
    assert processar_leitura(db, pluv, {"chuva_1h_mm": 35}, TS) == []
    [a] = processar_leitura(db, pluv, {"chuva_1h_mm": 65}, TS)
    assert a["nivel"] == 3 and a["gatilho"]["valor_observado"] == 65 and a["gatilho"]["limiar"] == 60
    processar_leitura(db, pluv, {"chuva_1h_mm": 25}, TS)
    assert db.alerts.count_documents({}) == 1
    assert db.alerts.find_one()["nivel"] == 3


def test_apos_encerrar_cria_novo(db, pluv):
    [a] = processar_leitura(db, pluv, {"chuva_1h_mm": 34}, TS)
    encerrar_alerta(db, a["_id"])
    processar_leitura(db, pluv, {"chuva_1h_mm": 34}, TS)
    assert db.alerts.count_documents({}) == 2


def test_sensor_sem_bairro_usa_municipio(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="CS-LIN-01", tipo="linigrafo", bairro=None, municipio="Castelo"))
    [a] = processar_leitura(db, buscar_sensor(db, "CS-LIN-01"), {"nivel_m": 4.2}, TS)
    assert a["bairros_afetados"] == ["Castelo"] and a["tipo"] == "enchente"


def test_crud_manual(db):
    aid = inserir_alerta(db, {"tipo": "vendaval", "nivel": 1})
    [a] = listar_alertas(db, status="ativo")
    assert a["canais"] == ["site_prefeitura"] and a["gatilho"] is None
    assert atualizar_alerta(db, aid, {"bairros_afetados": ["Centro"]}) is True
    assert encerrar_alerta(db, aid, status="falso_positivo") is True
    a = db.alerts.find_one({"_id": aid})
    assert a["status"] == "falso_positivo" and a["fim"] is not None
    assert listar_alertas(db, status="ativo") == []
    with pytest.raises(ValueError):
        encerrar_alerta(db, aid, status="ativo")
    assert remover_alerta(db, aid) is True and db.alerts.count_documents({}) == 0
