# Monitoramento de Risco Ambiental — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menu de terminal em Python para a Defesa Civil gerenciar sensores, telemetria e alertas climáticos num MongoDB rodando em Docker, com 5 buscas.

**Architecture:** Pacote `app/` com um módulo por responsabilidade: conexão, regras puras de alerta, CRUD de cada coleção, buscas, entrada no terminal, menu e dados simulados. Os módulos de CRUD e de buscas recebem um `Database` do pymongo, então os testes rodam contra um banco de teste no mesmo container.

**Tech Stack:** Python 3.12 (`py`), pymongo 4, pytest 8, MongoDB 8.0 (imagem `mongo:8.0`) via Docker Compose.

**Spec:** `docs/design.md`

## Global Constraints

- Banco `risco_ambiental`. Os testes usam `risco_ambiental_test`. A URI vem da variável `MONGO_URI`, com padrão `mongodb://localhost:27017`.
- Nomes das coleções: `sensors`, `telemetry` (time-series: `timeField: "ts"`, `metaField: "sensor_id"`, `granularity: "minutes"`) e `alerts`.
- Nomes de campos e valores enumerados exatamente como em `docs/design.md`.
- Datas: gravadas em UTC (`MongoClient(tz_aware=True)`). Digitadas e exibidas no horário de Brasília, UTC−3 fixo, no formato `dd/mm/aaaa hh:mm`.
- Textos de interface e mensagens de erro em português.
- Dependências: só `pymongo` e `pytest`. Nada de bibliotecas de terminal (rich, tabulate etc.).
- Comandos rodam no Git Bash, a partir da raiz `C:\Users\Matheus\Desktop\Working\MongoDB`, com o Python do venv: `.venv/Scripts/python`.
- A pasta não é um repositório git, então não há passos de commit.

## Review Focus

1. **Leitura com `qualidade` "falha" ou "suspeito" não gera alerta.** Um sensor com defeito não pode disparar SMS. Teste na Task 5.
2. **Entrada inválida no menu não derruba o programa.** Texto no lugar de número, data mal escrita ou opção fora da lista: o programa pede de novo. Testes na Task 7.
3. **Código de sensor duplicado ou inexistente vira mensagem clara**, não traceback. Testes nas Tasks 3 e 5, e o menu captura `ValueError` (Task 7).
4. **Sensor removido com leituras antigas:** o resumo diário continua funcionando e mostra "(sensor removido)". Teste na Task 6.
5. **Bairro digitado com outra capitalização** (ex.: "gilson carone") encontra os alertas de "Gilson Carone". Teste na Task 6.

---

### Task 1: Ambiente e conexão

**Files:**
- Create: `docker-compose.yml`, `requirements.txt`, `app/__init__.py` (vazio), `app/db.py`
- Test: `tests/__init__.py` (vazio), `tests/conftest.py`, `tests/test_db.py`

**Interfaces:**
- Produces:
  - `DB_NAME = "risco_ambiental"`
  - `get_db(nome: str = DB_NAME, uri: str | None = None) -> pymongo.database.Database`, com `tz_aware=True` e `serverSelectionTimeoutMS=3000`.
  - `criar_colecoes(db: Database) -> None`, idempotente.
  - Fixture `db` no pytest: banco `risco_ambiental_test`, apagado antes e depois de cada teste, com `criar_colecoes` já aplicado.
  - Fixture `sensor_exemplo` no pytest: função `(**campos) -> dict` que devolve um pluviômetro `CI-PLU-03` ("Pluviômetro Gilson Carone", bairro "Gilson Carone", `area_de_risco: "encosta"`, `localizacao` `[-41.1040, -20.8350]`, município "Cachoeiro de Itapemirim"), com sobrescrita por `campos`. O fixture **não** inclui `limiares` nem `status`: esses padrões ficam por conta de `inserir_sensor`.

- [ ] **Step 1: Criar `docker-compose.yml` e `requirements.txt`**

  Serviço `mongo`:
  - imagem `mongo:8.0`;
  - `container_name: risco-ambiental-mongo`;
  - porta `27017:27017`;
  - volumes `mongo-data:/data/db` e `./dump:/dump`.

  `requirements.txt` com `pymongo>=4.8,<5` e `pytest>=8,<9`.

- [ ] **Step 2: Subir o banco e o venv**

  Run:
  ```bash
  docker compose up -d && py -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
  ```
  Expected: container `risco-ambiental-mongo` em execução (`docker ps`) e pip termina sem erro.

- [ ] **Step 3: Escrever os testes que falham**

```python
# tests/test_db.py
from app.db import criar_colecoes

def test_cria_as_tres_colecoes(db):
    assert {"sensors", "telemetry", "alerts"} <= set(db.list_collection_names())

def test_telemetry_e_time_series(db):
    info = next(db.list_collections(filter={"name": "telemetry"}))
    assert info["type"] == "timeseries"
    assert info["options"]["timeseries"]["timeField"] == "ts"
    assert info["options"]["timeseries"]["metaField"] == "sensor_id"

def test_indices_de_sensors(db):
    idx = db.sensors.index_information().values()
    assert any(i.get("unique") and i["key"] == [("codigo", 1)] for i in idx)
    assert any(i["key"] == [("localizacao", "2dsphere")] for i in idx)

def test_criar_colecoes_e_idempotente(db):
    criar_colecoes(db)
```

- [ ] **Step 4: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
  Expected: ERROR, `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 5: Implementar `app/db.py` e as fixtures em `tests/conftest.py`**

  `criar_colecoes`:
  - cria `telemetry` como time-series e `alerts` só se ainda não existirem;
  - cria o índice único em `sensors.codigo` e o índice `2dsphere` em `sensors.localizacao`.

- [ ] **Step 6: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
  Expected: 4 passed.

---

### Task 2: Regras de alerta (funções puras)

**Files:**
- Create: `app/regras.py`
- Test: `tests/test_regras.py`

**Interfaces:**
- Produces:
  - `NIVEIS = {"atencao": 1, "alerta": 2, "emergencia": 3}`
  - `TIPOS_SENSOR = ("linigrafo", "pluviometro", "estacao_meteorologica")`
  - `LIMIARES_PADRAO: dict[str, dict]`, indexado por tipo de sensor:
    - linigrafo: `nivel_m` 3.0/4.0/5.0;
    - pluviometro: `chuva_1h_mm` 20/30/60 e `chuva_24h_mm` 30/50/100;
    - estacao_meteorologica: `temperatura_c` 35/38/40 e `rajada_kmh` 40/60/100.
  - `VARIAVEIS_POR_TIPO: dict[str, list[str]]`:
    - linigrafo: `["nivel_m"]`;
    - pluviometro: `["chuva_mm", "chuva_1h_mm", "chuva_24h_mm"]`;
    - estacao_meteorologica: `["temperatura_c", "umidade_pct", "pressao_hpa", "vento_kmh", "rajada_kmh", "direcao_vento_graus", "chuva_mm"]`.
  - `ORIENTACOES: dict[str, str]`, com o texto padrão por tipo de alerta (abaixo).
  - `avaliar_medidas(limiares: dict, medidas: dict) -> list[dict]`. Cada item é `{"variavel", "nivel", "valor_observado", "limiar"}`, e `limiar` é o valor do nível atingido. O nível é o maior atingido (`valor >= limiar`). Medida sem limiar, ou limiar sem medida, é ignorada.
  - `tipo_alerta(variavel: str, sensor: dict) -> str`
  - `canais_por_nivel(nivel: int) -> list[str]`

  Textos de `ORIENTACOES`:
  - `chuva_intensa`: "Evite áreas de encosta e não atravesse ruas alagadas."
  - `enchente`: "Moradores de áreas ribeirinhas: retirem pertences de locais baixos e fiquem atentos aos avisos."
  - `deslizamento`: "Moradores de encostas: observem rachaduras e estalos e procurem local seguro."
  - `calor_extremo`: "Beba água, evite sol entre 10h e 16h e atenção a idosos e crianças."
  - `vendaval`: "Evite ficar sob árvores, placas e redes elétricas."

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_regras.py
from app.regras import avaliar_medidas, tipo_alerta, canais_por_nivel, LIMIARES_PADRAO

LIM = {"chuva_1h_mm": {"atencao": 20, "alerta": 30, "emergencia": 60}}

def test_abaixo_do_limiar_nao_gera_nada():
    assert avaliar_medidas(LIM, {"chuva_1h_mm": 19.9}) == []

def test_nivel_e_o_maior_atingido():
    assert avaliar_medidas(LIM, {"chuva_1h_mm": 34.2}) == [
        {"variavel": "chuva_1h_mm", "nivel": 2, "valor_observado": 34.2, "limiar": 30}]

def test_valor_igual_ao_limiar_conta():
    assert avaliar_medidas(LIM, {"chuva_1h_mm": 60})[0]["nivel"] == 3

def test_medida_sem_limiar_e_ignorada():
    assert avaliar_medidas(LIM, {"umidade_pct": 10}) == []

def test_tipo_alerta_por_variavel():
    assert tipo_alerta("nivel_m", {}) == "enchente"
    assert tipo_alerta("chuva_1h_mm", {}) == "chuva_intensa"
    assert tipo_alerta("chuva_24h_mm", {"area_de_risco": "encosta"}) == "deslizamento"
    assert tipo_alerta("chuva_24h_mm", {}) == "chuva_intensa"
    assert tipo_alerta("temperatura_c", {}) == "calor_extremo"
    assert tipo_alerta("rajada_kmh", {}) == "vendaval"

def test_canais_por_nivel():
    assert canais_por_nivel(1) == ["site_prefeitura"]
    assert canais_por_nivel(2) == ["sms_40199", "site_prefeitura"]
    assert canais_por_nivel(3) == ["sms_40199", "site_prefeitura"]

def test_limiares_padrao_do_design():
    assert LIMIARES_PADRAO["linigrafo"]["nivel_m"] == {"atencao": 3.0, "alerta": 4.0, "emergencia": 5.0}
    assert LIMIARES_PADRAO["pluviometro"]["chuva_24h_mm"] == {"atencao": 30, "alerta": 50, "emergencia": 100}
    assert LIMIARES_PADRAO["estacao_meteorologica"]["rajada_kmh"] == {"atencao": 40, "alerta": 60, "emergencia": 100}
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_regras.py -v`
  Expected: ERROR, `No module named 'app.regras'`.

- [ ] **Step 3: Implementar `app/regras.py`** com os nomes e valores do bloco Interfaces.

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_regras.py -v`
  Expected: 7 passed.

---

### Task 3: CRUD de sensores

**Files:**
- Create: `app/sensores.py`
- Test: `tests/test_sensores.py`

**Interfaces:**
- Consumes: `TIPOS_SENSOR` e `LIMIARES_PADRAO` (Task 2); fixtures `db` e `sensor_exemplo` (Task 1).
- Produces:
  - `STATUS_SENSOR = ("operacional", "manutencao", "inativo")`
  - `inserir_sensor(db, dados: dict) -> str`: devolve o `codigo`.
    - Exige `codigo`, `nome` e `tipo` válido.
    - Padrões: `status="operacional"` e `limiares` copiados de `LIMIARES_PADRAO[tipo]`.
    - Código duplicado → `ValueError("Já existe um sensor com o código <codigo>")`.
    - Chaves com valor `None` não são gravadas (ex.: `bairro=None` para o sensor de Castelo).
  - `listar_sensores(db, tipo: str | None = None) -> list[dict]`: ordenado por `codigo`.
  - `buscar_sensor(db, codigo: str) -> dict | None`
  - `atualizar_sensor(db, codigo: str, campos: dict) -> bool`: ignora `codigo` e `_id` em `campos`; status inválido → `ValueError`.
  - `remover_sensor(db, codigo: str) -> bool`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_sensores.py
import pytest
from app.sensores import inserir_sensor, listar_sensores, buscar_sensor, atualizar_sensor, remover_sensor

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
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_sensores.py -v`
  Expected: ERROR, `No module named 'app.sensores'`.

- [ ] **Step 3: Implementar `app/sensores.py`**

  Capturar `pymongo.errors.DuplicateKeyError` e transformá-lo no `ValueError` descrito. Usar uma cópia dos limiares padrão, nunca o dict original.

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_sensores.py -v`
  Expected: 6 passed.

---

### Task 4: Alertas (regra automática e CRUD)

**Files:**
- Create: `app/alertas.py`
- Test: `tests/test_alertas.py`

**Interfaces:**
- Consumes: `avaliar_medidas`, `tipo_alerta`, `canais_por_nivel` e `ORIENTACOES` (Task 2); `inserir_sensor` e `buscar_sensor` (Task 3).
- Produces:
  - `STATUS_ALERTA = ("ativo", "encerrado", "falso_positivo")`
  - `processar_leitura(db, sensor: dict, medidas: dict, ts: datetime) -> list[dict]`: devolve os alertas criados ou com nível elevado, como estão no banco após a operação. Regras:
    - **Novo alerta:** usa `tipo_alerta(variavel, sensor)`, `nivel`, `inicio=ts`, `fim=None`, `gatilho={sensor_id, variavel, valor_observado, limiar}`, `bairros_afetados=[sensor.get("bairro") or sensor["municipio"]]`, `orientacao=ORIENTACOES[tipo]`, `canais=canais_por_nivel(nivel)` e `status="ativo"`.
    - **Já existe alerta `ativo`** com o mesmo `gatilho.sensor_id` e a mesma `gatilho.variavel`:
      - nível novo maior → atualiza `nivel`, `gatilho.valor_observado`, `gatilho.limiar` e `canais`;
      - nível igual ou menor → não faz nada e não entra no retorno.
  - `inserir_alerta(db, dados: dict) -> ObjectId`: alerta manual. Exige `tipo` e `nivel`. Padrões: `inicio=agora (UTC)`, `fim=None`, `gatilho=None`, `bairros_afetados=[]`, `orientacao=ORIENTACOES[tipo]`, `canais=canais_por_nivel(nivel)` e `status="ativo"`.
  - `listar_alertas(db, status: str | None = None) -> list[dict]`: ordenado por `inicio` decrescente.
  - `atualizar_alerta(db, alerta_id: ObjectId, campos: dict) -> bool`
  - `encerrar_alerta(db, alerta_id: ObjectId, status: str = "encerrado", fim: datetime | None = None) -> bool`: `status` precisa ser "encerrado" ou "falso_positivo" (senão, `ValueError`). `fim` tem padrão agora (UTC).
  - `remover_alerta(db, alerta_id: ObjectId) -> bool`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_alertas.py
from datetime import datetime, timezone
import pytest
from app.alertas import (processar_leitura, inserir_alerta, listar_alertas,
                         atualizar_alerta, encerrar_alerta, remover_alerta)
from app.regras import ORIENTACOES
from app.sensores import inserir_sensor, buscar_sensor

TS = datetime(2026, 11, 27, 13, 10, tzinfo=timezone.utc)

@pytest.fixture
def pluv(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())
    return buscar_sensor(db, "CI-PLU-03")

def test_cria_alerta_completo(db, pluv):
    [a] = processar_leitura(db, pluv, {"chuva_1h_mm": 34.2}, TS)
    assert a["tipo"] == "chuva_intensa" and a["nivel"] == 2 and a["status"] == "ativo"
    assert a["inicio"] == TS and a["fim"] is None
    assert a["gatilho"] == {"sensor_id": pluv["_id"], "variavel": "chuva_1h_mm",
                            "valor_observado": 34.2, "limiar": 30}
    assert a["bairros_afetados"] == ["Gilson Carone"]
    assert a["canais"] == ["sms_40199", "site_prefeitura"]
    assert a["orientacao"] == ORIENTACOES["chuva_intensa"]

def test_duas_variaveis_dois_alertas(db, pluv):
    tipos = {a["tipo"] for a in processar_leitura(db, pluv, {"chuva_1h_mm": 34, "chuva_24h_mm": 55}, TS)}
    assert tipos == {"chuva_intensa", "deslizamento"}

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
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_alertas.py -v`
  Expected: ERROR, `No module named 'app.alertas'`.

- [ ] **Step 3: Implementar `app/alertas.py`**

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_alertas.py -v`
  Expected: 6 passed.

---

### Task 5: Telemetria

**Files:**
- Create: `app/telemetria.py`
- Test: `tests/test_telemetria.py`

**Interfaces:**
- Consumes: `buscar_sensor` (Task 3); `processar_leitura` (Task 4).
- Produces:
  - `registrar_leitura(db, codigo_sensor: str, medidas: dict, ts: datetime | None = None, qualidade: str = "ok") -> list[dict]`
    - Sensor inexistente → `ValueError("Sensor <codigo> não encontrado")`.
    - Insere `{ts, sensor_id, medidas, qualidade}`, com `ts` padrão agora (UTC).
    - Devolve `processar_leitura(...)` só quando `qualidade == "ok"`; senão, `[]`.
  - `listar_leituras(db, codigo_sensor: str | None = None, limite: int = 20) -> list[dict]`: mais recentes primeiro.
  - `remover_leituras(db, inicio: datetime, fim: datetime, codigo_sensor: str | None = None) -> int`: apaga com `inicio <= ts <= fim` e devolve a quantidade apagada.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_telemetria.py
from datetime import datetime, timedelta, timezone
import pytest
from app.sensores import inserir_sensor
from app.telemetria import registrar_leitura, listar_leituras, remover_leituras

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)

@pytest.fixture
def pluv(db, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo())

def test_grava_leitura(db, pluv):
    assert registrar_leitura(db, "CI-PLU-03", {"chuva_mm": 1.0}, ts=T0) == []
    doc = db.telemetry.find_one()
    assert doc["ts"] == T0 and doc["medidas"] == {"chuva_mm": 1.0} and doc["qualidade"] == "ok"

def test_leitura_acima_gera_alerta(db, pluv):
    [a] = registrar_leitura(db, "CI-PLU-03", {"chuva_1h_mm": 34.2}, ts=T0)
    assert a["tipo"] == "chuva_intensa"

@pytest.mark.parametrize("q", ["falha", "suspeito"])
def test_qualidade_ruim_nao_gera_alerta(db, pluv, q):
    assert registrar_leitura(db, "CI-PLU-03", {"chuva_1h_mm": 99}, ts=T0, qualidade=q) == []
    assert db.alerts.count_documents({}) == 0
    assert db.telemetry.count_documents({}) == 1

def test_sensor_inexistente(db):
    with pytest.raises(ValueError, match="XX-01"):
        registrar_leitura(db, "XX-01", {"chuva_mm": 1})

def test_listar_e_remover(db, pluv, sensor_exemplo):
    inserir_sensor(db, sensor_exemplo(codigo="CI-PLU-05"))
    for h in range(5):
        registrar_leitura(db, "CI-PLU-03", {"chuva_mm": h}, ts=T0 + timedelta(hours=h))
    registrar_leitura(db, "CI-PLU-05", {"chuva_mm": 0}, ts=T0)
    ultimas = listar_leituras(db, "CI-PLU-03", limite=2)
    assert [l["ts"] for l in ultimas] == [T0 + timedelta(hours=4), T0 + timedelta(hours=3)]
    assert len(listar_leituras(db)) == 6
    assert remover_leituras(db, T0 + timedelta(hours=1), T0 + timedelta(hours=3), "CI-PLU-03") == 3
    assert db.telemetry.count_documents({}) == 3
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_telemetria.py -v`
  Expected: ERROR, `No module named 'app.telemetria'`.

- [ ] **Step 3: Implementar `app/telemetria.py`**

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_telemetria.py -v`
  Expected: 6 passed.

  Se `remover_leituras` falhar por restrição de delete em time-series, confirme que o container é o `mongo:8.0` (`docker compose exec mongo mongod --version`).

---

### Task 6: As 5 buscas

**Files:**
- Create: `app/buscas.py`
- Test: `tests/test_buscas.py`

**Interfaces:**
- Consumes: `inserir_sensor`, `remover_sensor` e `buscar_sensor` (Task 3); `inserir_alerta` e `encerrar_alerta` (Task 4); `registrar_leitura` (Task 5).
- Produces:
  - `alertas_ativos(db) -> list[dict]`: só `status: "ativo"`, ordenado por `nivel` decrescente e depois por `inicio` decrescente.
  - `leituras_por_periodo(db, codigo_sensor: str, inicio: datetime, fim: datetime) -> list[dict]`: ordem crescente de `ts`, limites inclusivos. Sensor inexistente → `ValueError`.
  - `resumo_diario(db, dia: date) -> list[dict]`:
    - o dia é o dia local (UTC−3), filtrado com `$match` no intervalo UTC correspondente e agregado com `$group` por `sensor_id`;
    - cada item: `{"codigo", "nome", "leituras", "temperatura_max", "rajada_max", "chuva_total"}`;
    - campo sem dado no dia → `None`. Por exemplo, `chuva_total` de um linígrafo é `None`, não 0;
    - sensor removido → `codigo "?"` e `nome "(sensor removido)"`;
    - ordenado por `nome`.
  - `sensores_proximos(db, longitude: float, latitude: float, raio_km: float) -> list[dict]`: `$near` com `$maxDistance` em metros, do mais perto para o mais longe.
  - `alertas_por_bairro(db, bairro: str) -> list[dict]`: igualdade exata sem diferenciar maiúsculas (regex `^…$` com `re.escape` e opção `i`) em `bairros_afetados`, ordenado por `inicio` decrescente.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_buscas.py
from datetime import date, datetime, timedelta, timezone
import pytest
from app import buscas
from app.alertas import inserir_alerta, encerrar_alerta
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
    d = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)           # 12:00 em Brasília
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

def test_alertas_por_bairro_sem_diferenciar_maiusculas(db):
    inserir_alerta(db, {"tipo": "deslizamento", "nivel": 2, "bairros_afetados": ["Gilson Carone"]})
    inserir_alerta(db, {"tipo": "enchente", "nivel": 2, "bairros_afetados": ["Centro"]})
    res = buscas.alertas_por_bairro(db, "gilson carone")
    assert [a["tipo"] for a in res] == ["deslizamento"]
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_buscas.py -v`
  Expected: ERROR, `cannot import name 'buscas'`.

- [ ] **Step 3: Implementar `app/buscas.py`** conforme o bloco Interfaces.

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_buscas.py -v`
  Expected: 5 passed.

---

### Task 7: Entrada no terminal e menu

**Files:**
- Create: `app/terminal.py`, `app/menu.py`, `main.py`
- Test: `tests/test_terminal.py`, `tests/test_menu.py`

**Interfaces:**
- Consumes: todas as funções públicas das Tasks 3 a 6; `TIPOS_SENSOR`, `LIMIARES_PADRAO` e `VARIAVEIS_POR_TIPO` (Task 2); `get_db` (Task 1).
- Produces, em `app/terminal.py` (entrada inválida → imprime "Valor inválido, tente de novo." e pergunta de novo; Enter vazio com `padrao` → devolve `padrao`):
  - `FUSO = timezone(timedelta(hours=-3))`
  - `ler_texto(prompt: str, padrao: str | None = None) -> str`: vazio sem padrão é inválido.
  - `ler_float(prompt: str, padrao: float | None = None) -> float`: aceita vírgula decimal.
  - `ler_int(prompt: str, padrao: int | None = None) -> int`
  - `ler_data_hora(prompt: str, padrao: datetime | None = None) -> datetime`: formato `dd/mm/aaaa hh:mm` em UTC−3; devolve datetime aware em UTC.
  - `ler_data(prompt: str, padrao: date | None = None) -> date`: formato `dd/mm/aaaa`.
  - `escolher(titulo: str, opcoes: list[str]) -> int | None`: mostra `1..n` e `0. Voltar`; devolve o índice começando em 0, ou `None` para 0.
  - `formatar_data_hora(dt: datetime) -> str`: em UTC−3, `dd/mm/aaaa hh:mm`.
- Produces, em `app/menu.py`:
  - `main(db: Database | None = None) -> None`. Sem `db`, chama `get_db()`. Se a conexão falhar (`ServerSelectionTimeoutError`), imprime "Não foi possível conectar ao MongoDB. Rode: docker compose up -d" e retorna.

  Estrutura do menu:
  - **Menu principal:** título "=== Monitoramento de Risco Ambiental — Cachoeiro de Itapemirim ===" e opções `1 Sensores`, `2 Telemetria`, `3 Alertas`, `4 Buscas`, `0 Sair`.
  - **Sensores:** listar, inserir (limiares padrão do tipo oferecidos como padrão), atualizar status/nome/bairro, remover.
  - **Telemetria:** últimas leituras, registrar leitura (pergunta as variáveis de `VARIAVEIS_POR_TIPO[tipo]`, Enter pula uma variável, e imprime os alertas gerados), remover por período.
  - **Alertas:** listar, inserir manual, atualizar (bairros, orientação, canais), encerrar (encerrado/falso positivo), remover. O alerta é escolhido numa lista numerada com `escolher`, nunca digitando ObjectId.
  - **Buscas:** as 5 buscas da Task 6.
  - Todo `ValueError` levantado pelas funções vira uma mensagem impressa, e o menu continua.
- `main.py` (raiz): `from app.menu import main` e `main()` dentro de `if __name__ == "__main__":`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_terminal.py
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
```

```python
# tests/test_menu.py
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
```

  No menu, "Registrar leitura" pede primeiro o código do sensor e chama `buscar_sensor`. Se o sensor não existir, imprime "Sensor XX-01 não encontrado" e volta ao submenu.

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_terminal.py tests/test_menu.py -v`
  Expected: ERROR, `cannot import name 'terminal'`.

- [ ] **Step 3: Implementar `app/terminal.py`, `app/menu.py` e `main.py`**

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_terminal.py tests/test_menu.py -v`
  Expected: 9 passed.

---

### Task 8: Dados simulados, dump e README

**Files:**
- Create: `app/seed.py`, `README.md`, `dump/risco_ambiental.archive.gz` (gerado)
- Test: `tests/test_seed.py`

**Interfaces:**
- Consumes: `get_db` e `criar_colecoes` (Task 1); `inserir_sensor` (Task 3); `encerrar_alerta` (Task 4); `registrar_leitura` (Task 5).
- Produces: `popular(db, dias: int = 3, agora: datetime | None = None) -> dict[str, int]`, que devolve `{"sensors": n, "telemetry": n, "alerts": n}`. Também `python -m app.seed`, que popula o banco `risco_ambiental` e imprime as contagens.

  Comportamento de `popular`:
  - Apaga as 3 coleções e chama `criar_colecoes`.
  - Insere 5 sensores:
    - `CI-LIN-01`: linígrafo, Centro, `[-41.1129, -20.8489]`, fonte AGERH, `intervalo_s` 900.
    - `CI-PLU-03`: pluviômetro, Gilson Carone, encosta, Cemaden, 600.
    - `CI-PLU-05`: pluviômetro, Village da Luz, Cemaden, 600.
    - `CI-EST-01`: estação meteorológica, Centro, Defesa Civil Municipal, 3600.
    - `CS-LIN-01`: linígrafo, município Castelo, sem bairro, `[-41.1847, -20.6033]`, rio "Rio Castelo", bacia "Rio Itapemirim", limiares `nivel_m` 2.5/3.5/4.5.
  - Gera leituras **de hora em hora** para cada sensor (simplificação do script), com `random.Random(42)`, sempre via `registrar_leitura`, para que os alertas saiam da regra.
  - Os pluviômetros calculam `chuva_1h_mm` e o acumulado móvel `chuva_24h_mm`.
  - Episódios obrigatórios:
    - **calor:** no 1º dia, à tarde, `temperatura_c` ≥ 38 na estação;
    - **chuva forte:** no último dia, à tarde, `chuva_1h_mm` ≥ 30 e `chuva_24h_mm` ≥ 50 em Gilson Carone;
    - **cheia:** depois da chuva, `nivel_m` ≥ 4.0 em `CI-LIN-01`.
  - No fim, encerra o alerta de calor (`fim` = fim do episódio), para haver alertas ativos e encerrados.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_seed.py
from datetime import datetime, timezone
from app.seed import popular

AGORA = datetime(2026, 11, 27, 21, 0, tzinfo=timezone.utc)

def test_popular(db):
    cont = popular(db, dias=3, agora=AGORA)
    assert cont["sensors"] == 5 == db.sensors.count_documents({})
    assert cont["telemetry"] == db.telemetry.count_documents({}) > 0
    tipos = set(db.alerts.distinct("tipo"))
    assert {"chuva_intensa", "deslizamento", "enchente", "calor_extremo"} <= tipos
    assert db.alerts.count_documents({"status": "ativo"}) >= 1
    assert db.alerts.count_documents({"status": "encerrado"}) >= 1

def test_popular_duas_vezes_da_o_mesmo_resultado(db):
    assert popular(db, dias=3, agora=AGORA) == popular(db, dias=3, agora=AGORA)
```

- [ ] **Step 2: Rodar e ver falhar**

  Run: `.venv/Scripts/python -m pytest tests/test_seed.py -v`
  Expected: ERROR, `No module named 'app.seed'`.

- [ ] **Step 3: Implementar `app/seed.py`**

- [ ] **Step 4: Rodar e ver passar**

  Run: `.venv/Scripts/python -m pytest tests/test_seed.py -v`
  Expected: 2 passed.

- [ ] **Step 5: Popular o banco real e gerar o dump**

  Run:
  ```bash
  .venv/Scripts/python -m app.seed && docker compose exec mongo mongodump --db risco_ambiental --archive=/dump/risco_ambiental.archive.gz --gzip
  ```
  Expected: contagens impressas (5 sensores) e `dump/risco_ambiental.archive.gz` com mais de 0 bytes.

- [ ] **Step 6: Escrever o `README.md`**

  Seções, em português:
  1. **Requisitos:** Docker e Python 3.12.
  2. **Subir o banco:** `docker compose up -d`.
  3. **Instalar:** `python -m venv .venv`, ativar e `pip install -r requirements.txt` (no Windows, `py` no lugar de `python`).
  4. **Popular o banco:** `python -m app.seed`, **ou** restaurar o dump com `docker compose exec mongo mongorestore --archive=/dump/risco_ambiental.archive.gz --gzip --drop`.
  5. **Rodar:** `python main.py`.
  6. **Testes:** `python -m pytest`.
  7. **Coleções e buscas:** resumo de uma linha por coleção e por busca, com link para `docs/design.md`.
  8. **Ao compactar para o AVA:** não incluir `.venv/`.

- [ ] **Step 7: Verificação final**

  Run:
  ```bash
  .venv/Scripts/python -m pytest -v
  ```
  Expected: 45 passed (4 + 7 + 6 + 6 + 6 + 5 + 9 + 2).

  Depois, rodar à mão `.venv/Scripts/python main.py` e percorrer as 5 buscas e um ciclo de CRUD de alerta. Conferir que:
  - os alertas de chuva, deslizamento e enchente do seed aparecem como ativos;
  - o de calor aparece como encerrado.
