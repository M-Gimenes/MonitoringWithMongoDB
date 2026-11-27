"""Leitura de dados digitados no terminal e formatação de datas.

Toda entrada inválida mostra "Valor inválido, tente de novo." e pergunta de novo.
Enter vazio devolve o valor padrão, quando há um.
"""
from datetime import date, datetime, timezone

from app.regras import FUSO

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_HORA = "%d/%m/%Y %H:%M"
INVALIDO = "Valor inválido, tente de novo."


def _perguntar(prompt: str, padrao_exibido: str | None) -> str:
    sufixo = f" [{padrao_exibido}]" if padrao_exibido not in (None, "") else ""
    return input(f"{prompt}{sufixo}: ").strip()


def ler_texto(prompt: str, padrao: str | None = None) -> str:
    while True:
        valor = _perguntar(prompt, padrao)
        if valor:
            return valor
        if padrao is not None:
            return padrao
        print(INVALIDO)


def ler_float(prompt: str, padrao: float | None = None) -> float:
    while True:
        valor = _perguntar(prompt, None if padrao is None else str(padrao))
        if not valor and padrao is not None:
            return padrao
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            print(INVALIDO)


def ler_float_opcional(prompt: str) -> float | None:
    """Como ler_float, mas Enter vazio devolve None (campo pulado)."""
    while True:
        valor = _perguntar(prompt, None)
        if not valor:
            return None
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            print(INVALIDO)


def ler_int(prompt: str, padrao: int | None = None) -> int:
    while True:
        valor = _perguntar(prompt, None if padrao is None else str(padrao))
        if not valor and padrao is not None:
            return padrao
        try:
            return int(valor)
        except ValueError:
            print(INVALIDO)


def ler_data_hora(prompt: str, padrao: datetime | None = None) -> datetime:
    """Lê dd/mm/aaaa hh:mm no horário de Brasília e devolve em UTC."""
    exibido = formatar_data_hora(padrao) if padrao else None
    while True:
        valor = _perguntar(f"{prompt} (dd/mm/aaaa hh:mm)", exibido)
        if not valor and padrao is not None:
            return padrao
        try:
            local = datetime.strptime(valor, FORMATO_DATA_HORA).replace(tzinfo=FUSO)
            return local.astimezone(timezone.utc)
        except ValueError:
            print(INVALIDO)


def ler_data(prompt: str, padrao: date | None = None) -> date:
    exibido = padrao.strftime(FORMATO_DATA) if padrao else None
    while True:
        valor = _perguntar(f"{prompt} (dd/mm/aaaa)", exibido)
        if not valor and padrao is not None:
            return padrao
        try:
            return datetime.strptime(valor, FORMATO_DATA).date()
        except ValueError:
            print(INVALIDO)


def escolher(titulo: str, opcoes: list[str], rotulo_zero: str = "Voltar") -> int | None:
    """Mostra opções numeradas. Devolve o índice (a partir de 0) ou None para 0."""
    print(f"\n{titulo}")
    for i, opcao in enumerate(opcoes, start=1):
        print(f"  {i}. {opcao}")
    print(f"  0. {rotulo_zero}")
    while True:
        valor = input("> ").strip()
        if valor == "0":
            return None
        if valor.isdigit() and 1 <= int(valor) <= len(opcoes):
            return int(valor) - 1
        print(INVALIDO)


def formatar_data_hora(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(FUSO).strftime(FORMATO_DATA_HORA)


def agora_local_date() -> date:
    return datetime.now(FUSO).date()
