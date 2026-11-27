from app.alertas import inserir_alerta
from app.menu import main


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
