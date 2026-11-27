"""Menu de terminal do sistema de Monitoramento de Risco Ambiental."""
from datetime import datetime, time, timedelta, timezone

from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app import buscas
from app.alertas import (
    STATUS_ALERTA,
    atualizar_alerta,
    encerrar_alerta,
    inserir_alerta,
    listar_alertas,
    remover_alerta,
)
from app.db import criar_colecoes, get_db
from app.regras import FUSO, LIMIARES_PADRAO, NIVEIS, ORIENTACOES, TIPOS_SENSOR, VARIAVEIS_POR_TIPO
from app.sensores import (
    STATUS_SENSOR,
    atualizar_sensor,
    buscar_sensor,
    inserir_sensor,
    listar_sensores,
    remover_sensor,
)
from app.telemetria import QUALIDADES, listar_leituras, registrar_leitura, remover_leituras
from app.terminal import (
    agora_local_date,
    cabecalho,
    escolher,
    formatar_data_hora,
    ler_data,
    ler_data_hora,
    ler_float,
    ler_float_opcional,
    ler_int,
    ler_texto,
    limpar_tela,
    mensagem,
    secao,
    simbolo,
    tabela,
)

TITULO = "Monitoramento de Risco Ambiental"
LOCAL = "Cachoeiro de Itapemirim · ES"
NOME_NIVEL = {1: "ATENÇÃO", 2: "ALERTA", 3: "EMERGÊNCIA"}
NIVEL_VISUAL = {
    1: ("△", "^", "aviso"),
    2: ("◆", "!", "alerta"),
    3: ("■", "#", "erro"),
}
COLUNAS_ALERTA = ("Nível", "Ocorrência", "Horário local", "Detalhes")
CORES = {
    "Operacional": "ok", "Manutenção": "aviso", "Inativo": "discreto",
    "Válida": "ok", "Suspeita": "aviso", "Falha": "erro",
}
ROTULOS = {
    "linigrafo": "Linígrafo", "pluviometro": "Pluviômetro",
    "estacao_meteorologica": "Estação meteorológica", "manutencao": "Manutenção",
    "falso_positivo": "Falso positivo", "ok": "Válida", "suspeito": "Suspeita",
    "atencao": "Atenção", "emergencia": "Emergência",
}
MEDIDAS = {
    "nivel_m": ("Nível do rio", "m"),
    "chuva_mm": ("Chuva", "mm"),
    "chuva_1h_mm": ("Chuva em 1 h", "mm"),
    "chuva_24h_mm": ("Chuva em 24 h", "mm"),
    "temperatura_c": ("Temperatura", "°C"),
    "umidade_pct": ("Umidade", "%"),
    "pressao_hpa": ("Pressão", "hPa"),
    "vento_kmh": ("Vento", "km/h"),
    "rajada_kmh": ("Rajada", "km/h"),
    "direcao_vento_graus": ("Direção do vento", "°"),
}


# ---------- exibição ----------

def _rotulo(chave: str) -> str:
    return ROTULOS.get(chave, chave.replace("_", " ").capitalize())


def _valor(valor: float | None, unidade: str) -> str:
    return "—" if valor is None else f"{valor} {unidade}".replace(".", ",").strip()


def _linha_sensor(s: dict) -> tuple[str, ...]:
    local = s.get("bairro") or s.get("municipio") or "—"
    return s["codigo"], s["nome"], _rotulo(s["tipo"]), local, _rotulo(s["status"])


def _nivel_alerta(nivel: int) -> str:
    if nivel not in NIVEL_VISUAL:
        return str(nivel)
    grafico, simples, _ = NIVEL_VISUAL[nivel]
    return f"{simbolo(grafico, simples)} {NOME_NIVEL[nivel]}"


def _linha_alerta(a: dict) -> tuple[str, ...]:
    evento = f"{_rotulo(a['tipo'])}\n{_rotulo(a['status'])}"
    datas = f"Início {formatar_data_hora(a['inicio'])}"
    if a.get("fim"):
        datas += f"\nFim {formatar_data_hora(a['fim'])}"
    detalhes = []
    if a.get("bairros_afetados"):
        detalhes.append(", ".join(a["bairros_afetados"]))
    g = a.get("gatilho")
    if g:
        nome, unidade = MEDIDAS.get(g["variavel"], (_rotulo(g["variavel"]), ""))
        observado = _valor(g["valor_observado"], unidade)
        limiar = _valor(g["limiar"], unidade)
        detalhes.extend((f"{nome}: {observado}", f"Limiar: {limiar}"))
    return _nivel_alerta(a["nivel"]), evento, datas, "\n".join(detalhes) or "—"


def _linha_leitura(l: dict, codigos: dict) -> tuple[str, ...]:
    medidas = []
    for chave, valor in l["medidas"].items():
        nome, unidade = MEDIDAS.get(chave, (_rotulo(chave), ""))
        medidas.append(f"{nome}: {_valor(valor, unidade)}")
    return (formatar_data_hora(l["ts"]), codigos.get(l["sensor_id"], "—"),
            " · ".join(medidas), _rotulo(l["qualidade"]))


def _resultado(colunas: tuple[str, ...], linhas: list[tuple[str, ...]], vazio: str, *,
               destaques: dict[str, str] | None = None, espacar_linhas: bool = False,
               titulo: str | None = None) -> None:
    if not linhas:
        print()
        mensagem(vazio)
        return
    quantidade = "1 resultado" if len(linhas) == 1 else f"{len(linhas)} resultados"
    secao(titulo or quantidade)
    tabela(colunas, linhas, destaques if destaques is not None else CORES, espacar_linhas=espacar_linhas)


def _mostrar_sensores(sensores: list[dict], vazio: str) -> None:
    _resultado(("Código", "Sensor", "Tipo", "Local", "Status"), [_linha_sensor(s) for s in sensores], vazio)


def _mostrar_alertas(alertas: list[dict], vazio: str, *, titulo: str | None = None) -> None:
    cores = {_nivel_alerta(nivel): cor for nivel, (_, _, cor) in NIVEL_VISUAL.items()}
    _resultado(COLUNAS_ALERTA, [_linha_alerta(a) for a in alertas], vazio,
               destaques=cores, espacar_linhas=True, titulo=titulo)


def _mostrar_leituras(db: Database, leituras: list[dict], vazio: str) -> None:
    codigos = _codigos(db) if leituras else {}
    _resultado(("Horário local", "Sensor", "Medições", "Qualidade"),
               [_linha_leitura(l, codigos) for l in leituras], vazio)


def _codigos(db: Database) -> dict:
    return {s["_id"]: s["codigo"] for s in db.sensors.find({}, {"codigo": 1})}


def _confirmar(pergunta: str) -> bool:
    if ler_texto(f"{pergunta} (s/n)", padrao="n").lower().startswith("s"):
        return True
    mensagem("Operação cancelada.")
    return False


def _escolher_sensor(db: Database) -> dict | None:
    sensores = listar_sensores(db)
    if not sensores:
        mensagem("Nenhum sensor cadastrado.")
        return None
    opcoes = []
    descricoes = []
    for sensor in sensores:
        codigo, nome, tipo, local, status = _linha_sensor(sensor)
        opcoes.append(f"{codigo} · {nome}")
        descricoes.append(f"{tipo} · {local} · {status}")
    i = escolher("Escolha o sensor", opcoes, descricoes=tuple(descricoes))
    return None if i is None else sensores[i]


def _escolher_alerta(alertas: list[dict]) -> dict | None:
    if not alertas:
        mensagem("Nenhum alerta.")
        return None
    opcoes = []
    for alerta in alertas:
        nivel, evento, datas, detalhes = _linha_alerta(alerta)
        opcoes.append(" · ".join([nivel, *evento.splitlines(), *datas.splitlines(), *detalhes.splitlines()]))
    i = escolher("Escolha o alerta", opcoes)
    return None if i is None else alertas[i]


def _lista_texto(texto: str) -> list[str]:
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


# ---------- sensores ----------

def sensores_listar(db: Database) -> None:
    _mostrar_sensores(listar_sensores(db), "Nenhum sensor cadastrado.")


def sensores_inserir(db: Database) -> None:
    i = escolher("1 de 3 · Identificação do sensor", [_rotulo(tipo) for tipo in TIPOS_SENSOR], "Cancelar")
    if i is None:
        return
    tipo = TIPOS_SENSOR[i]
    dados = {
        "codigo": ler_texto("Código (ex.: CI-PLU-07)").upper(),
        "nome": ler_texto("Nome"),
        "tipo": tipo,
    }
    secao("2 de 3 · Localização e operação")
    dados["municipio"] = ler_texto("Município", padrao="Cachoeiro de Itapemirim")
    dados["bairro"] = ler_texto("Bairro (opcional)", padrao="") or None
    dados["area_de_risco"] = ler_texto("Área de risco, ex. encosta (opcional)", padrao="") or None
    dados["bacia"] = ler_texto("Bacia (opcional)", padrao="") or None
    dados["fonte"] = ler_texto("Fonte/operador", padrao="Defesa Civil Municipal")
    dados["instalacao"] = datetime.combine(ler_data("Data de instalação", padrao=agora_local_date()),
                                           time.min, tzinfo=FUSO)
    dados["intervalo_s"] = ler_int("Intervalo entre leituras (segundos)", padrao=600)
    longitude = ler_float("Longitude", padrao=-41.1129)
    latitude = ler_float("Latitude", padrao=-20.8489)
    dados["localizacao"] = {"type": "Point", "coordinates": [longitude, latitude]}

    secao("3 de 3 · Limiares de alerta")
    limiares = {}
    for variavel, faixas in LIMIARES_PADRAO[tipo].items():
        nome, unidade = MEDIDAS[variavel]
        print(f"  {nome} ({unidade})")
        limiares[variavel] = {nivel: ler_float(_rotulo(nivel), padrao=valor) for nivel, valor in faixas.items()}
    dados["limiares"] = limiares

    inserir_sensor(db, dados)
    mensagem(f"Sensor {dados['codigo']} cadastrado.", "ok")


def sensores_atualizar(db: Database) -> None:
    sensor = _escolher_sensor(db)
    if sensor is None:
        return
    campo = escolher("O que deseja alterar?", ["Status", "Nome", "Bairro"])
    if campo is None:
        return
    if campo == 0:
        i = escolher("Novo status", [_rotulo(status) for status in STATUS_SENSOR])
        if i is None:
            return
        alteracao = {"status": STATUS_SENSOR[i]}
    elif campo == 1:
        alteracao = {"nome": ler_texto("Novo nome", padrao=sensor["nome"])}
    else:
        alteracao = {"bairro": ler_texto("Novo bairro", padrao=sensor.get("bairro", ""))}
    atualizar_sensor(db, sensor["codigo"], alteracao)
    mensagem("Sensor atualizado.", "ok")


def sensores_remover(db: Database) -> None:
    sensor = _escolher_sensor(db)
    if sensor and _confirmar(f"Remover o sensor {sensor['codigo']}?"):
        remover_sensor(db, sensor["codigo"])
        mensagem("Sensor removido. As leituras e alertas antigos continuam no histórico.", "ok")


# ---------- telemetria ----------

def telemetria_listar(db: Database) -> None:
    codigo = ler_texto("Código do sensor (Enter para todos)", padrao="").upper() or None
    leituras = listar_leituras(db, codigo, limite=20)
    _mostrar_leituras(db, leituras, "Nenhuma leitura encontrada.")


def telemetria_registrar(db: Database) -> None:
    secao("1 de 2 · Sensor e medições")
    codigo = ler_texto("Código do sensor").upper()
    sensor = buscar_sensor(db, codigo)
    if sensor is None:
        mensagem(f"Sensor {codigo} não encontrado.", "aviso")
        return
    mensagem(f"{sensor['nome']} · Enter pula um campo de medição.")
    medidas = {}
    for variavel in VARIAVEIS_POR_TIPO[sensor["tipo"]]:
        nome, unidade = MEDIDAS[variavel]
        valor = ler_float_opcional(f"{nome} ({unidade})")
        if valor is not None:
            medidas[variavel] = valor
    if not medidas:
        mensagem("Nenhuma medida informada. Leitura não registrada.", "aviso")
        return
    secao("2 de 2 · Data e qualidade")
    ts = ler_data_hora("Data/hora", padrao=datetime.now(timezone.utc).replace(second=0, microsecond=0))
    i = escolher("Qualidade da leitura", [_rotulo(qualidade) for qualidade in QUALIDADES], "Cancelar")
    if i is None:
        return
    alertas = registrar_leitura(db, codigo, medidas, ts=ts, qualidade=QUALIDADES[i])
    mensagem("Leitura registrada.", "ok")
    if alertas:
        _mostrar_alertas(alertas, "", titulo="Alertas gerados ou elevados pela leitura")


def telemetria_remover(db: Database) -> None:
    inicio = ler_data_hora("Início")
    fim = ler_data_hora("Fim")
    codigo = ler_texto("Código do sensor (Enter para todos)", padrao="").upper() or None
    if _confirmar("Remover as leituras desse período?"):
        quantidade = remover_leituras(db, inicio, fim, codigo)
        texto = "1 leitura removida." if quantidade == 1 else f"{quantidade} leituras removidas."
        mensagem(texto, "ok")


# ---------- alertas ----------

def alertas_listar(db: Database) -> None:
    _mostrar_alertas(listar_alertas(db), "Nenhum alerta registrado.")


def alertas_inserir(db: Database) -> None:
    tipos = list(ORIENTACOES)
    i = escolher("1 de 2 · Tipo de ocorrência", [_rotulo(tipo) for tipo in tipos], "Cancelar")
    if i is None:
        return
    n = escolher("2 de 2 · Gravidade e orientação", [NOME_NIVEL[v] for v in NIVEIS.values()], "Cancelar")
    if n is None:
        return
    tipo, nivel = tipos[i], n + 1
    dados = {
        "tipo": tipo,
        "nivel": nivel,
        "bairros_afetados": _lista_texto(ler_texto("Bairros afetados (separados por vírgula)")),
        "orientacao": ler_texto("Orientação à população", padrao=ORIENTACOES[tipo]),
    }
    inserir_alerta(db, dados)
    mensagem("Alerta registrado.", "ok")


def alertas_atualizar(db: Database) -> None:
    alerta = _escolher_alerta(listar_alertas(db))
    if alerta is None:
        return
    campo = escolher("O que deseja alterar?", ["Bairros afetados", "Orientação", "Canais"])
    if campo is None:
        return
    if campo == 0:
        alteracao = {"bairros_afetados": _lista_texto(
            ler_texto("Bairros (separados por vírgula)", padrao=", ".join(alerta["bairros_afetados"])))}
    elif campo == 1:
        alteracao = {"orientacao": ler_texto("Orientação", padrao=alerta["orientacao"])}
    else:
        alteracao = {"canais": _lista_texto(
            ler_texto("Canais (separados por vírgula)", padrao=", ".join(alerta["canais"])))}
    atualizar_alerta(db, alerta["_id"], alteracao)
    mensagem("Alerta atualizado.", "ok")


def alertas_encerrar(db: Database) -> None:
    alerta = _escolher_alerta(listar_alertas(db, status="ativo"))
    if alerta is None:
        return
    opcoes = [s for s in STATUS_ALERTA if s != "ativo"]
    i = escolher("Encerrar como", [_rotulo(status) for status in opcoes])
    if i is None:
        return
    encerrar_alerta(db, alerta["_id"], status=opcoes[i])
    mensagem("Alerta encerrado.", "ok")


def alertas_remover(db: Database) -> None:
    alerta = _escolher_alerta(listar_alertas(db))
    if alerta and _confirmar("Remover este alerta?"):
        remover_alerta(db, alerta["_id"])
        mensagem("Alerta removido.", "ok")


# ---------- buscas ----------

def busca_alertas_ativos(db: Database) -> None:
    _mostrar_alertas(buscas.alertas_ativos(db), "Nenhum alerta ativo.")


def busca_leituras_periodo(db: Database) -> None:
    codigo = ler_texto("Código do sensor").upper()
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    inicio = ler_data_hora("Início", padrao=agora - timedelta(hours=24))
    fim = ler_data_hora("Fim", padrao=agora)
    leituras = buscas.leituras_por_periodo(db, codigo, inicio, fim)
    _mostrar_leituras(db, leituras, "Nenhuma leitura no período.")


def busca_resumo_diario(db: Database) -> None:
    dia = ler_data("Dia", padrao=agora_local_date())
    linhas = [
        (f"{r['codigo']} · {r['nome']}", str(r["leituras"]), _valor(r["temperatura_max"], "°C"),
         _valor(r["rajada_max"], "km/h"), _valor(r["chuva_total"], "mm"))
        for r in buscas.resumo_diario(db, dia)
    ]
    _resultado(("Sensor", "Leituras", "Temp. máxima", "Maior rajada", "Chuva total"),
               linhas, "Nenhuma leitura nesse dia.")


def busca_sensores_proximos(db: Database) -> None:
    longitude = ler_float("Longitude", padrao=-41.1129)
    latitude = ler_float("Latitude", padrao=-20.8489)
    raio = ler_float("Raio (km)", padrao=5.0)
    _mostrar_sensores(buscas.sensores_proximos(db, longitude, latitude, raio), "Nenhum sensor nesse raio.")


def busca_alertas_bairro(db: Database) -> None:
    bairro = ler_texto("Bairro")
    _mostrar_alertas(buscas.alertas_por_bairro(db, bairro), "Nenhum alerta para esse bairro.")


# ---------- navegação ----------

SUBMENUS = {
    "Sensores": [
        ("Listar sensores", sensores_listar),
        ("Cadastrar sensor", sensores_inserir),
        ("Atualizar", sensores_atualizar),
        ("Remover", sensores_remover),
    ],
    "Telemetria": [
        ("Últimas leituras", telemetria_listar),
        ("Registrar leitura", telemetria_registrar),
        ("Remover leituras por período", telemetria_remover),
    ],
    "Alertas": [
        ("Listar alertas", alertas_listar),
        ("Registrar alerta manual", alertas_inserir),
        ("Atualizar", alertas_atualizar),
        ("Encerrar", alertas_encerrar),
        ("Remover", alertas_remover),
    ],
    "Buscas": [
        ("Alertas ativos agora", busca_alertas_ativos),
        ("Leituras de um sensor num período", busca_leituras_periodo),
        ("Resumo do dia por sensor", busca_resumo_diario),
        ("Sensores num raio de X km", busca_sensores_proximos),
        ("Alertas que atingiram um bairro", busca_alertas_bairro),
    ],
}
APRESENTACAO_MENU = {
    "Sensores": ("⌖", "+", "Cadastro, localização e status dos pontos de medição"),
    "Telemetria": ("∿", "~", "Histórico e registro de medições"),
    "Alertas": ("△", "!", "Registro e acompanhamento de ocorrências"),
    "Buscas": ("⌕", "/", "Consultas por período, localização, bairro e gravidade"),
}


def _erro_banco(erro: PyMongoError) -> None:
    detalhe = str(erro).partition("\n")[0][:150]
    mensagem(f"Erro no banco de dados. {detalhe}", "erro")
    mensagem("Para iniciar o MongoDB local, use docker compose up -d.")


def _submenu(db: Database, titulo: str, acoes: list) -> None:
    limpar_tela()
    cabecalho(titulo, "Menu principal")
    nomes = [nome for nome, _ in acoes]
    pergunta = "Escolha uma ação"
    while True:
        i = escolher(pergunta, nomes)
        if i is None:
            return
        nome, acao = acoes[i]
        limpar_tela()
        cabecalho(nome, f"Menu principal / {titulo}")
        try:
            acao(db)
        except ValueError as erro:
            mensagem(str(erro), "erro")
        except PyMongoError as erro:
            _erro_banco(erro)
        pergunta = f"{titulo} · Próxima ação"


def main(db: Database | None = None) -> None:
    if db is None:
        db = get_db()
    try:
        db.client.admin.command("ping")
        criar_colecoes(db)
    except ServerSelectionTimeoutError:
        cabecalho(TITULO, LOCAL)
        mensagem("Não foi possível conectar ao MongoDB.", "erro")
        mensagem("Para iniciar o MongoDB local, use docker compose up -d.")
        return
    except PyMongoError as erro:
        cabecalho(TITULO, LOCAL)
        _erro_banco(erro)
        return

    titulos = list(SUBMENUS)
    opcoes = []
    descricoes = []
    for titulo in titulos:
        grafico, simples, descricao = APRESENTACAO_MENU[titulo]
        opcoes.append(f"{simbolo(grafico, simples)} {titulo}")
        descricoes.append(descricao)
    try:
        while True:
            limpar_tela()
            cabecalho(TITULO, LOCAL, "Rio, chuva, temperatura e vento")
            i = escolher("Menu principal", opcoes, rotulo_zero="Sair", descricoes=tuple(descricoes))
            if i is None:
                break
            _submenu(db, titulos[i], SUBMENUS[titulos[i]])
    except (EOFError, KeyboardInterrupt):
        print()
    mensagem("Até logo!")
