"""Apresentação, leitura de dados e formatação de datas no terminal.

Toda entrada inválida mostra "Valor inválido, tente de novo." e pergunta de novo.
Enter vazio devolve o valor padrão, quando há um.
"""
import os
import sys
from datetime import date, datetime, timezone
from shutil import get_terminal_size
from textwrap import wrap

from app.regras import FUSO

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_HORA = "%d/%m/%Y %H:%M"
INVALIDO = "Valor inválido, tente de novo."
ESTILOS = {
    "titulo": "1", "destaque": "1;96", "discreto": "90", "ok": "1;92",
    "aviso": "1;93", "erro": "1;91", "info": "96", "alerta": "1;38;5;208",
}
ROTULOS = {"ok": "OK", "aviso": "ATENÇÃO", "erro": "ERRO", "info": "INFO"}


def _tem_ansi() -> bool:
    if not sys.stdout.isatty() or os.getenv("TERM") == "dumb":
        return False
    return os.name != "nt" or bool(os.getenv("WT_SESSION") or os.getenv("ANSICON"))


def _estilo(texto: str, estilo: str) -> str:
    if _tem_ansi() and "NO_COLOR" not in os.environ:
        return f"\033[{ESTILOS[estilo]}m{texto}\033[0m"
    return texto


def simbolo(grafico: str, simples: str) -> str:
    try:
        grafico.encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        return simples
    return grafico


def _largura() -> int:
    return min(get_terminal_size((88, 24)).columns, 104)


def limpar_tela() -> None:
    if _tem_ansi() and sys.stdin.isatty():
        print("\033[2J\033[H", end="")


def cabecalho(titulo: str, local: str, detalhe: str = "") -> None:
    largura = min(_largura(), 76)
    if largura < 18:
        print(f"\n{local}\n{titulo}")
        return
    esq_topo, dir_topo, esq_fim, dir_fim, traco, barra = simbolo("╭╮╰╯─│", "++++-|")
    print()
    print(_estilo(esq_topo + traco * (largura - 2) + dir_topo, "destaque"))
    for texto, estilo in ((local, "info"), (titulo, "titulo"), (detalhe, "discreto")):
        for linha in wrap(texto, width=largura - 6):
            print(f"{_estilo(barra, 'destaque')}  {_estilo(linha.ljust(largura - 6), estilo)}  "
                  f"{_estilo(barra, 'destaque')}")
    print(_estilo(esq_fim + traco * (largura - 2) + dir_fim, "destaque"))


def secao(titulo: str) -> None:
    print(f"\n  {_estilo(simbolo('──', '--'), 'destaque')} {_estilo(titulo, 'titulo')}")


def mensagem(texto: str, tipo: str = "info") -> None:
    prefixo = f"  [{ROTULOS[tipo]}] "
    linhas = wrap(texto, width=max(1, _largura() - len(prefixo))) or [""]
    print(f"{_estilo(prefixo, tipo)}{linhas[0]}")
    for linha in linhas[1:]:
        print(f"{' ' * len(prefixo)}{linha}")


def _quebrar_celula(valor: str, largura: int) -> list[str]:
    return [parte for linha in valor.split("\n")
            for parte in (wrap(linha, width=largura, break_on_hyphens=False) or [""])]


def tabela(colunas: tuple[str, ...], linhas: list[tuple[str, ...]],
           destaques: dict[str, str] | None = None, *, espacar_linhas: bool = False) -> None:
    """Exibe uma tabela larga ou registros com campos rotulados em telas estreitas."""
    if not linhas:
        return
    destaques = destaques or {}
    largura = _largura()
    disponivel = largura - 2 - 3 * (len(colunas) - 1)
    minimos = [max(len(coluna), 9) for coluna in colunas]
    if sum(minimos) > disponivel:
        for linha in linhas:
            print(f"  {_estilo(simbolo('─', '-') * max(0, largura - 2), 'discreto')}")
            for coluna, valor in zip(colunas, linha):
                prefixo = f"  {coluna}: "
                partes = _quebrar_celula(valor, max(1, largura - len(prefixo)))
                valor_inicial = _estilo(partes[0], destaques.get(valor, "titulo"))
                print(f"{_estilo(prefixo, 'discreto')}{valor_inicial}")
                for parte in partes[1:]:
                    print(f"{' ' * len(prefixo)}{parte}")
        return

    larguras = []
    for minimo, valores in zip(minimos, zip(*linhas)):
        maior = max(len(parte) for valor in valores for parte in valor.split("\n"))
        larguras.append(max(minimo, min(disponivel, maior)))
    while sum(larguras) > disponivel:
        indice = max(range(len(colunas)), key=lambda i: larguras[i] - minimos[i])
        larguras[indice] -= 1

    divisor = _estilo(f" {simbolo('│', '|')} ", "discreto")
    print("  " + divisor.join(_estilo(c.upper().ljust(w), "destaque") for c, w in zip(colunas, larguras)))
    traco, cruzamento = simbolo("─┼", "-+")
    print("  " + _estilo((traco + cruzamento + traco).join(traco * w for w in larguras), "discreto"))
    for indice, linha in enumerate(linhas):
        if espacar_linhas and indice:
            print()
        celulas = [_quebrar_celula(valor, w) for valor, w in zip(linha, larguras)]
        for i in range(max(map(len, celulas))):
            partes = []
            for valor, celula, w in zip(linha, celulas, larguras):
                parte = (celula[i] if i < len(celula) else "").ljust(w)
                partes.append(_estilo(parte, destaques[valor]) if valor in destaques else parte)
            print("  " + divisor.join(partes))


def _perguntar(prompt: str, padrao_exibido: str | None) -> str:
    sufixo = f" [{padrao_exibido}]" if padrao_exibido not in (None, "") else ""
    seta = _estilo(simbolo("›", ">"), "destaque")
    return input(f"  {seta} {prompt}{_estilo(sufixo, 'discreto')}: ").strip()


def ler_texto(prompt: str, padrao: str | None = None) -> str:
    while True:
        valor = _perguntar(prompt, padrao)
        if valor:
            return valor
        if padrao is not None:
            return padrao
        mensagem(INVALIDO, "aviso")


def ler_float(prompt: str, padrao: float | None = None) -> float:
    while True:
        valor = _perguntar(prompt, None if padrao is None else str(padrao))
        if not valor and padrao is not None:
            return padrao
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            mensagem(INVALIDO, "aviso")


def ler_float_opcional(prompt: str) -> float | None:
    """Como ler_float, mas Enter vazio devolve None (campo pulado)."""
    while True:
        valor = _perguntar(prompt, None)
        if not valor:
            return None
        try:
            return float(valor.replace(",", "."))
        except ValueError:
            mensagem(INVALIDO, "aviso")


def ler_int(prompt: str, padrao: int | None = None) -> int:
    while True:
        valor = _perguntar(prompt, None if padrao is None else str(padrao))
        if not valor and padrao is not None:
            return padrao
        try:
            return int(valor)
        except ValueError:
            mensagem(INVALIDO, "aviso")


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
            mensagem(INVALIDO, "aviso")


def ler_data(prompt: str, padrao: date | None = None) -> date:
    exibido = padrao.strftime(FORMATO_DATA) if padrao else None
    while True:
        valor = _perguntar(f"{prompt} (dd/mm/aaaa)", exibido)
        if not valor and padrao is not None:
            return padrao
        try:
            return datetime.strptime(valor, FORMATO_DATA).date()
        except ValueError:
            mensagem(INVALIDO, "aviso")


def escolher(titulo: str, opcoes: list[str], rotulo_zero: str = "Voltar", *,
             descricoes: tuple[str, ...] = ()) -> int | None:
    """Mostra opções numeradas. Devolve o índice (a partir de 0) ou None para 0."""
    secao(titulo)
    digitos = len(str(len(opcoes)))
    largura = _largura()
    for i, opcao in enumerate(opcoes, start=1):
        numero = f"[{i:>{digitos}}]"
        recuo = " " * (len(numero) + 3)
        partes = _quebrar_celula(opcao, max(1, largura - len(recuo)))
        print(f"  {_estilo(numero, 'destaque')} {_estilo(partes[0], 'titulo')}")
        for parte in partes[1:]:
            print(f"{recuo}{parte}")
        if descricoes:
            for linha in wrap(descricoes[i - 1], width=max(1, largura - len(recuo))):
                print(f"{recuo}{_estilo(linha, 'discreto')}")
    print(f"\n  {_estilo(f'[{0:>{digitos}}]', 'discreto')} {rotulo_zero}")
    while True:
        valor = _perguntar("Opção", None)
        if valor == "0":
            return None
        try:
            numero = int(valor) if valor.isdecimal() else 0
            if 1 <= numero <= len(opcoes):
                return numero - 1
        except ValueError:
            pass
        mensagem(INVALIDO, "aviso")


def formatar_data_hora(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(FUSO).strftime(FORMATO_DATA_HORA)


def agora_local_date() -> date:
    return datetime.now(FUSO).date()
