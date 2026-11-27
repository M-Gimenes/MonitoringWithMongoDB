from pymongo.errors import ServerSelectionTimeoutError

from app.alertas import inserir_alerta
from app.menu import main
from app.sensores import buscar_sensor, inserir_sensor


def entradas(monkeypatch, *valores):
    it = iter(valores)
    monkeypatch.setattr("builtins.input", lambda _="": next(it))


def test_busca_alertas_ativos_pelo_menu(db, monkeypatch, capsys):
    inserir_alerta(db, {"tipo": "chuva_intensa", "nivel": 2, "bairros_afetados": ["Centro"]})
    entradas(monkeypatch, "4", "1", "0", "0")
    main(db)
    assert "chuva_intensa" in capsys.readouterr().out


def test_opcao_invalida_nao_derruba(db, monkeypatch, capsys):
    entradas(monkeypatch, "x", "7", "0")
    main(db)
    assert "inválid" in capsys.readouterr().out.lower()


def test_leitura_de_sensor_inexistente_mostra_mensagem(db, monkeypatch, capsys):
    entradas(monkeypatch, "2", "2", "XX-01", "0", "0")
    main(db)
    assert "não encontrado" in capsys.readouterr().out


def test_latitude_fora_da_faixa_nao_derruba(db, monkeypatch, capsys):
    entradas(monkeypatch, "4", "4", "", "-208489", "5", "0", "0")
    main(db)
    saida = capsys.readouterr().out
    assert "Latitude" in saida and "Até logo!" in saida


def test_erro_do_banco_no_meio_da_demo_nao_derruba(db, monkeypatch, capsys):
    def cair(_db):
        raise ServerSelectionTimeoutError("conexão perdida")

    monkeypatch.setattr("app.menu.buscas.alertas_ativos", cair)
    entradas(monkeypatch, "4", "1", "0", "0")
    main(db)
    saida = capsys.readouterr().out
    assert "banco de dados" in saida and "Até logo!" in saida


def test_confirmar_com_sim_remove(db, sensor_exemplo, monkeypatch):
    inserir_sensor(db, sensor_exemplo())
    entradas(monkeypatch, "1", "4", "1", "sim", "0", "0")
    main(db)
    assert buscar_sensor(db, "CI-PLU-03") is None


def test_confirmar_com_nao_avisa_cancelamento(db, sensor_exemplo, monkeypatch, capsys):
    inserir_sensor(db, sensor_exemplo())
    entradas(monkeypatch, "1", "4", "1", "não", "0", "0")
    main(db)
    assert buscar_sensor(db, "CI-PLU-03") is not None
    assert "cancelada" in capsys.readouterr().out
