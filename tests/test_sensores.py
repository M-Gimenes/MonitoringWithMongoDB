import pytest

from app.sensores import atualizar_sensor, buscar_sensor, inserir_sensor, listar_sensores, remover_sensor


def test_inserir_aplica_padroes(db, sensor_exemplo):
    assert inserir_sensor(db, sensor_exemplo()) == "CI-PLU-03"
    s = buscar_sensor(db, "CI-PLU-03")
    assert s["status"] == "operacional"
    assert s["limiares"]["chuva_1h_mm"] == {"atencao": 20, "alerta": 30, "emergencia": 60}


def test_codigo_duplicado_da_mensagem_clara(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    with pytest.raises(ValueError, match="CI-PLU-03"):
        inserir_sensor(db, sensor_exemplo())


def test_tipo_invalido(db, sensor_exemplo):
    with pytest.raises(ValueError):
        inserir_sensor(db, sensor_exemplo(tipo="radar"))


def test_coordenadas_fora_da_faixa(db, sensor_exemplo):
    with pytest.raises(ValueError, match="Longitude"):
        inserir_sensor(db, sensor_exemplo(localizacao={"type": "Point", "coordinates": [-411129, -20.8]}))


def test_listar_filtra_e_ordena(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="B"))
    inserir_sensor(db, sensor_exemplo(codigo="A"))
    inserir_sensor(db, sensor_exemplo(codigo="C", tipo="linigrafo"))
    assert [s["codigo"] for s in listar_sensores(db)] == ["A", "B", "C"]
    assert [s["codigo"] for s in listar_sensores(db, tipo="linigrafo")] == ["C"]


def test_atualizar(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    assert atualizar_sensor(db, "CI-PLU-03", {"status": "manutencao"}) is True
    assert buscar_sensor(db, "CI-PLU-03")["status"] == "manutencao"
    assert atualizar_sensor(db, "NAO-EXISTE", {"status": "inativo"}) is False
    with pytest.raises(ValueError):
        atualizar_sensor(db, "CI-PLU-03", {"status": "quebrado"})


def test_remover(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    assert remover_sensor(db, "CI-PLU-03") is True
    assert buscar_sensor(db, "CI-PLU-03") is None
    assert remover_sensor(db, "CI-PLU-03") is False
