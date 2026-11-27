from datetime import date, datetime, timedelta, timezone

import pytest

from app import buscas
from app.alertas import encerrar_alerta, inserir_alerta
from app.sensores import inserir_sensor, remover_sensor
from app.telemetria import registrar_leitura

UTC = timezone.utc


def test_alertas_ativos_ordenados(db):
    inserir_alerta(db, {"tipo": "vendaval", "nivel": 1})
    inserir_alerta(db, {"tipo": "enchente", "nivel": 3})
    encerrar_alerta(db, inserir_alerta(db, {"tipo": "calor_extremo", "nivel": 2}))
    assert [a["nivel"] for a in buscas.alertas_ativos(db)] == [3, 1]


def test_leituras_por_periodo(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    t0 = datetime(2026, 11, 27, 0, 0, tzinfo=UTC)
    for h in range(6):
        registrar_leitura(db, "CI-PLU-03", {"chuva_mm": h}, ts=t0 + timedelta(hours=h))
    res = buscas.leituras_por_periodo(db, "CI-PLU-03", t0 + timedelta(hours=1), t0 + timedelta(hours=3))
    assert [l["medidas"]["chuva_mm"] for l in res] == [1, 2, 3]
    with pytest.raises(ValueError):
        buscas.leituras_por_periodo(db, "XX", t0, t0)


def test_resumo_diario(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="EST", nome="Estação", tipo="estacao_meteorologica"))
    inserir_sensor(db, sensor_exemplo(codigo="PLU", nome="Pluviômetro"))
    inserir_sensor(db, sensor_exemplo(codigo="LIN", nome="Linígrafo", tipo="linigrafo"))
    d = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)  # 12:00 em Brasília
    registrar_leitura(db, "EST", {"temperatura_c": 33.0, "rajada_kmh": 20}, ts=d)
    registrar_leitura(db, "EST", {"temperatura_c": 36.5, "rajada_kmh": 45}, ts=d + timedelta(hours=1))
    registrar_leitura(db, "PLU", {"chuva_mm": 2.0}, ts=d)
    registrar_leitura(db, "PLU", {"chuva_mm": 3.5}, ts=datetime(2026, 11, 28, 2, 0, tzinfo=UTC))  # 23:00 do dia 27
    registrar_leitura(db, "PLU", {"chuva_mm": 9.9}, ts=datetime(2026, 11, 28, 3, 0, tzinfo=UTC))  # já é dia 28
    registrar_leitura(db, "LIN", {"nivel_m": 2.1}, ts=d)
    res = {r["codigo"]: r for r in buscas.resumo_diario(db, date(2026, 11, 27))}
    assert res["EST"]["temperatura_max"] == 36.5 and res["EST"]["rajada_max"] == 45
    assert res["PLU"]["chuva_total"] == 5.5 and res["PLU"]["leituras"] == 2
    assert res["LIN"]["chuva_total"] is None
    remover_sensor(db, "LIN")
    nomes = [r["nome"] for r in buscas.resumo_diario(db, date(2026, 11, 27))]
    assert "(sensor removido)" in nomes


def test_sensores_proximos(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="CENTRO", localizacao={"type": "Point", "coordinates": [-41.1129, -20.8489]}))
    inserir_sensor(db, sensor_exemplo(codigo="CASTELO", localizacao={"type": "Point", "coordinates": [-41.1847, -20.6033]}))
    assert [s["codigo"] for s in buscas.sensores_proximos(db, -41.1129, -20.8489, 5)] == ["CENTRO"]
    assert [s["codigo"] for s in buscas.sensores_proximos(db, -41.1129, -20.8489, 50)] == ["CENTRO", "CASTELO"]


@pytest.mark.parametrize("lon, lat, raio", [
    (-41.1, -208489, 5),          # latitude sem o ponto decimal
    (-411129, -20.8, 5),          # longitude sem o ponto decimal
    (-41.1, -20.8, -5),           # raio negativo
    (float("nan"), -20.8, 5),
])
def test_sensores_proximos_rejeita_valores_fora_da_faixa(db, lon, lat, raio):
    with pytest.raises(ValueError):
        buscas.sensores_proximos(db, lon, lat, raio)


def test_resumo_diario_ignora_leituras_com_falha(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    d = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)
    registrar_leitura(db, "CI-PLU-03", {"chuva_mm": 1.0}, ts=d)
    registrar_leitura(db, "CI-PLU-03", {"chuva_mm": 999.0}, ts=d + timedelta(hours=1), qualidade="falha")
    [r] = buscas.resumo_diario(db, date(2026, 11, 27))
    assert r["chuva_total"] == 1.0 and r["leituras"] == 1


def test_alertas_por_bairro_sem_diferenciar_maiusculas(db):
    inserir_alerta(db, {"tipo": "deslizamento", "nivel": 2, "bairros_afetados": ["Gilson Carone"]})
    inserir_alerta(db, {"tipo": "enchente", "nivel": 2, "bairros_afetados": ["Centro"]})
    res = buscas.alertas_por_bairro(db, "gilson carone")
    assert [a["tipo"] for a in res] == ["deslizamento"]
