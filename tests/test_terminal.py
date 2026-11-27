from datetime import date, datetime, timezone

from app import terminal


def entradas(monkeypatch, *valores):
    it = iter(valores)
    monkeypatch.setattr("builtins.input", lambda _="": next(it))


def test_float_com_virgula_e_reentrada(monkeypatch, capsys):
    entradas(monkeypatch, "abc", "3,5")
    assert terminal.ler_float("x: ") == 3.5
    assert "Valor inválido" in capsys.readouterr().out


def test_padrao_no_enter(monkeypatch):
    entradas(monkeypatch, "")
    assert terminal.ler_float("x: ", padrao=20.0) == 20.0


def test_data_hora_em_brasilia_vira_utc(monkeypatch):
    entradas(monkeypatch, "31/02/2026 10:00", "27/11/2026 11:00")
    assert terminal.ler_data_hora("x: ") == datetime(2026, 11, 27, 14, 0, tzinfo=timezone.utc)


def test_data(monkeypatch):
    entradas(monkeypatch, "27/11/2026")
    assert terminal.ler_data("x: ") == date(2026, 11, 27)


def test_escolher(monkeypatch):
    entradas(monkeypatch, "9", "2")
    assert terminal.escolher("t", ["a", "b"]) == 1
    entradas(monkeypatch, "0")
    assert terminal.escolher("t", ["a", "b"]) is None


def test_formatar():
    assert terminal.formatar_data_hora(datetime(2026, 11, 27, 14, 0, tzinfo=timezone.utc)) == "27/11/2026 11:00"
