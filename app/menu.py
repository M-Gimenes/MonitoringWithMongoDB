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
    escolher,
    formatar_data_hora,
    ler_data,
    ler_data_hora,
    ler_float,
    ler_float_opcional,
    ler_int,
    ler_texto,
)

TITULO = "=== Monitoramento de Risco Ambiental — Cachoeiro de Itapemirim ==="
NOME_NIVEL = {1: "ATENÇÃO", 2: "ALERTA", 3: "EMERGÊNCIA"}


# ---------- exibição ----------

def _linha_sensor(s: dict) -> str:
    local = s.get("bairro") or s.get("municipio", "")
    return f"{s['codigo']:<10} {s['tipo']:<22} {s['status']:<12} {local:<16} {s['nome']}"


def _linha_alerta(a: dict) -> str:
    texto = (f"[{NOME_NIVEL.get(a['nivel'], a['nivel'])}] {a['tipo']} — {a['status']} — "
             f"início {formatar_data_hora(a['inicio'])}")
    if a.get("fim"):
        texto += f" — fim {formatar_data_hora(a['fim'])}"
    if a.get("bairros_afetados"):
        texto += f" — bairros: {', '.join(a['bairros_afetados'])}"
    g = a.get("gatilho")
    if g:
        texto += f" — {g['variavel']}={g['valor_observado']} (limiar {g['limiar']})"
    return texto


def _linha_leitura(l: dict, codigos: dict) -> str:
    medidas = ", ".join(f"{k}={v}" for k, v in l["medidas"].items())
    codigo = codigos.get(l["sensor_id"], "?")
    return f"{formatar_data_hora(l['ts'])}  {codigo:<10} {medidas}  [{l['qualidade']}]"


def _mostrar(itens: list, formatar, vazio: str) -> None:
    if not itens:
        print(vazio)
        return
    print()
    for item in itens:
        print(formatar(item))


def _codigos(db: Database) -> dict:
    return {s["_id"]: s["codigo"] for s in db.sensors.find({}, {"codigo": 1})}


def _confirmar(pergunta: str) -> bool:
    if ler_texto(f"{pergunta} (s/n)", padrao="n").lower().startswith("s"):
        return True
    print("Operação cancelada.")
    return False


def _escolher_sensor(db: Database) -> dict | None:
    sensores = listar_sensores(db)
    if not sensores:
        print("Nenhum sensor cadastrado.")
        return None
    i = escolher("Escolha o sensor:", [_linha_sensor(s) for s in sensores])
    return None if i is None else sensores[i]


def _escolher_alerta(alertas: list[dict]) -> dict | None:
    if not alertas:
        print("Nenhum alerta.")
        return None
    i = escolher("Escolha o alerta:", [_linha_alerta(a) for a in alertas])
    return None if i is None else alertas[i]


def _lista_texto(texto: str) -> list[str]:
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


# ---------- sensores ----------

def sensores_listar(db: Database) -> None:
    _mostrar(listar_sensores(db), _linha_sensor, "Nenhum sensor cadastrado.")


def sensores_inserir(db: Database) -> None:
    i = escolher("Tipo do sensor:", list(TIPOS_SENSOR))
    if i is None:
        return
    tipo = TIPOS_SENSOR[i]
    dados = {
        "codigo": ler_texto("Código (ex.: CI-PLU-07)").upper(),
        "nome": ler_texto("Nome"),
        "tipo": tipo,
        "municipio": ler_texto("Município", padrao="Cachoeiro de Itapemirim"),
        "bairro": ler_texto("Bairro (Enter para nenhum)", padrao="") or None,
        "area_de_risco": ler_texto("Área de risco, ex.: encosta (Enter para nenhuma)", padrao="") or None,
        "bacia": ler_texto("Bacia (Enter para nenhuma)", padrao="") or None,
        "fonte": ler_texto("Fonte/operador", padrao="Defesa Civil Municipal"),
        "instalacao": datetime.combine(ler_data("Data de instalação", padrao=agora_local_date()),
                                       time.min, tzinfo=FUSO),
        "intervalo_s": ler_int("Intervalo entre leituras (segundos)", padrao=600),
    }
    longitude = ler_float("Longitude", padrao=-41.1129)
    latitude = ler_float("Latitude", padrao=-20.8489)
    dados["localizacao"] = {"type": "Point", "coordinates": [longitude, latitude]}

    limiares = {}
    for variavel, faixas in LIMIARES_PADRAO[tipo].items():
        print(f"Limiares de {variavel}:")
        limiares[variavel] = {nome: ler_float(f"  {nome}", padrao=valor) for nome, valor in faixas.items()}
    dados["limiares"] = limiares

    inserir_sensor(db, dados)
    print(f"Sensor {dados['codigo']} cadastrado.")


def sensores_atualizar(db: Database) -> None:
    sensor = _escolher_sensor(db)
    if sensor is None:
        return
    campo = escolher("O que deseja alterar?", ["Status", "Nome", "Bairro"])
    if campo is None:
        return
    if campo == 0:
        i = escolher("Novo status:", list(STATUS_SENSOR))
        if i is None:
            return
        alteracao = {"status": STATUS_SENSOR[i]}
    elif campo == 1:
        alteracao = {"nome": ler_texto("Novo nome", padrao=sensor["nome"])}
    else:
        alteracao = {"bairro": ler_texto("Novo bairro", padrao=sensor.get("bairro", ""))}
    atualizar_sensor(db, sensor["codigo"], alteracao)
    print("Sensor atualizado.")


def sensores_remover(db: Database) -> None:
    sensor = _escolher_sensor(db)
    if sensor and _confirmar(f"Remover o sensor {sensor['codigo']}?"):
        remover_sensor(db, sensor["codigo"])
        print("Sensor removido. As leituras e alertas antigos continuam no histórico.")


# ---------- telemetria ----------

def telemetria_listar(db: Database) -> None:
    codigo = ler_texto("Código do sensor (Enter para todos)", padrao="").upper() or None
    leituras = listar_leituras(db, codigo, limite=20)
    codigos = _codigos(db)
    _mostrar(leituras, lambda l: _linha_leitura(l, codigos), "Nenhuma leitura encontrada.")


def telemetria_registrar(db: Database) -> None:
    codigo = ler_texto("Código do sensor").upper()
    sensor = buscar_sensor(db, codigo)
    if sensor is None:
        print(f"Sensor {codigo} não encontrado.")
        return
    print("Informe as medidas (Enter pula):")
    medidas = {}
    for variavel in VARIAVEIS_POR_TIPO[sensor["tipo"]]:
        valor = ler_float_opcional(f"  {variavel}")
        if valor is not None:
            medidas[variavel] = valor
    if not medidas:
        print("Nenhuma medida informada. Leitura não registrada.")
        return
    ts = ler_data_hora("Data/hora", padrao=datetime.now(timezone.utc).replace(second=0, microsecond=0))
    i = escolher("Qualidade da leitura:", list(QUALIDADES), rotulo_zero="Cancelar")
    if i is None:
        return
    alertas = registrar_leitura(db, codigo, medidas, ts=ts, qualidade=QUALIDADES[i])
    print("Leitura registrada.")
    for a in alertas:
        print(f"  >> Alerta: {_linha_alerta(a)}")


def telemetria_remover(db: Database) -> None:
    inicio = ler_data_hora("Início")
    fim = ler_data_hora("Fim")
    codigo = ler_texto("Código do sensor (Enter para todos)", padrao="").upper() or None
    if _confirmar("Remover as leituras desse período?"):
        print(f"{remover_leituras(db, inicio, fim, codigo)} leitura(s) removida(s).")


# ---------- alertas ----------

def alertas_listar(db: Database) -> None:
    _mostrar(listar_alertas(db), _linha_alerta, "Nenhum alerta registrado.")


def alertas_inserir(db: Database) -> None:
    tipos = list(ORIENTACOES)
    i = escolher("Tipo do alerta:", tipos)
    if i is None:
        return
    n = escolher("Nível:", [f"{v} - {NOME_NIVEL[v]}" for v in NIVEIS.values()])
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
    print("Alerta registrado.")


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
    print("Alerta atualizado.")


def alertas_encerrar(db: Database) -> None:
    alerta = _escolher_alerta(listar_alertas(db, status="ativo"))
    if alerta is None:
        return
    opcoes = [s for s in STATUS_ALERTA if s != "ativo"]
    i = escolher("Encerrar como:", opcoes)
    if i is None:
        return
    encerrar_alerta(db, alerta["_id"], status=opcoes[i])
    print("Alerta encerrado.")


def alertas_remover(db: Database) -> None:
    alerta = _escolher_alerta(listar_alertas(db))
    if alerta and _confirmar("Remover este alerta?"):
        remover_alerta(db, alerta["_id"])
        print("Alerta removido.")


# ---------- buscas ----------

def busca_alertas_ativos(db: Database) -> None:
    _mostrar(buscas.alertas_ativos(db), _linha_alerta, "Nenhum alerta ativo.")


def busca_leituras_periodo(db: Database) -> None:
    codigo = ler_texto("Código do sensor").upper()
    agora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    inicio = ler_data_hora("Início", padrao=agora - timedelta(hours=24))
    fim = ler_data_hora("Fim", padrao=agora)
    leituras = buscas.leituras_por_periodo(db, codigo, inicio, fim)
    codigos = _codigos(db)
    _mostrar(leituras, lambda l: _linha_leitura(l, codigos), "Nenhuma leitura no período.")


def busca_resumo_diario(db: Database) -> None:
    dia = ler_data("Dia", padrao=agora_local_date())

    def formatar(r: dict) -> str:
        def v(x):
            return "-" if x is None else x
        return (f"{r['codigo']:<10} {r['nome']:<45} leituras={r['leituras']:<3} "
                f"temp_max={v(r['temperatura_max'])} rajada_max={v(r['rajada_max'])} "
                f"chuva_total={v(r['chuva_total'])}")

    _mostrar(buscas.resumo_diario(db, dia), formatar, "Nenhuma leitura nesse dia.")


def busca_sensores_proximos(db: Database) -> None:
    longitude = ler_float("Longitude", padrao=-41.1129)
    latitude = ler_float("Latitude", padrao=-20.8489)
    raio = ler_float("Raio (km)", padrao=5.0)
    _mostrar(buscas.sensores_proximos(db, longitude, latitude, raio), _linha_sensor,
             "Nenhum sensor nesse raio.")


def busca_alertas_bairro(db: Database) -> None:
    bairro = ler_texto("Bairro")
    _mostrar(buscas.alertas_por_bairro(db, bairro), _linha_alerta, "Nenhum alerta para esse bairro.")


# ---------- navegação ----------

SUBMENUS = {
    "Sensores": [
        ("Listar", sensores_listar),
        ("Inserir", sensores_inserir),
        ("Atualizar", sensores_atualizar),
        ("Remover", sensores_remover),
    ],
    "Telemetria": [
        ("Últimas leituras", telemetria_listar),
        ("Registrar leitura", telemetria_registrar),
        ("Remover leituras por período", telemetria_remover),
    ],
    "Alertas": [
        ("Listar", alertas_listar),
        ("Inserir manualmente", alertas_inserir),
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


def _submenu(db: Database, titulo: str, acoes: list) -> None:
    while True:
        i = escolher(f"--- {titulo} ---", [nome for nome, _ in acoes])
        if i is None:
            return
        try:
            acoes[i][1](db)
        except ValueError as erro:
            print(f"Erro: {erro}")
        except PyMongoError as erro:
            detalhe = str(erro).splitlines()[0][:150]
            print(f"Erro no banco de dados: {detalhe}")
            print("Verifique se o MongoDB está rodando (docker compose up -d).")


def main(db: Database | None = None) -> None:
    if db is None:
        db = get_db()
    try:
        db.client.admin.command("ping")
    except ServerSelectionTimeoutError:
        print("Não foi possível conectar ao MongoDB. Rode: docker compose up -d")
        return
    criar_colecoes(db)

    titulos = list(SUBMENUS)
    while True:
        i = escolher(TITULO, titulos, rotulo_zero="Sair")
        if i is None:
            print("Até logo!")
            return
        _submenu(db, titulos[i], SUBMENUS[titulos[i]])
