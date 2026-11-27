# Monitoramento de Risco Ambiental

Trabalho 6 de Tópicos Especiais em Banco de Dados: integração do MongoDB com uma aplicação simples.

É um sistema de terminal para a Defesa Civil de Cachoeiro de Itapemirim/ES. Ele acompanha sensores climáticos (nível do rio, chuva, temperatura e vento), guarda as leituras e gera alertas automaticamente quando uma medida passa do limite.

## Requisitos

- [Docker](https://www.docker.com/) (com Docker Compose)
- Python 3.12

## Como montar o ambiente

Todos os comandos são executados na pasta do projeto.

**1. Subir o MongoDB**

```bash
docker compose up -d
```

**2. Criar o ambiente Python e instalar as dependências**

Windows (PowerShell ou cmd):

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> Nos passos seguintes, `python` significa o Python do venv: `.venv\Scripts\python` no Windows ou `.venv/bin/python` no Linux/macOS.
>
> Também dá para ativar o venv:
> - **PowerShell:** `.venv\Scripts\activate`. Se aparecer "a execução de scripts foi desabilitada", rode antes `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
> - **Git Bash:** `source .venv/Scripts/activate`.
> - **Linux/macOS:** `source .venv/bin/activate`.

**3. Popular o banco** (escolha uma das opções)

- **Opção A, gerar dados simulados:**

  ```bash
  python -m app.seed
  ```

  O script cria 5 sensores, 3 dias de leituras de hora em hora e os alertas resultantes.
- **Opção B, restaurar o banco entregue** (`dump/risco_ambiental.archive.gz`):

  ```bash
  docker compose exec mongo mongorestore --archive=/dump/risco_ambiental.archive.gz --gzip --drop
  ```

  > No Git Bash, coloque `MSYS_NO_PATHCONV=1` antes do comando.

  O banco entregue tem leituras de **24/11/2026 02:00 a 27/11/2026 01:00** (horário de Brasília):
  - **24/11:** onda de calor;
  - **26/11:** chuva forte, seguida de cheia do rio.

  Nas buscas 2 e 3, use datas desse período (ex.: resumo do dia **26/11/2026**). Na Opção A, os dados terminam na hora em que o script for rodado.

**4. Rodar o sistema**

```bash
python main.py
```

**5. Rodar os testes (opcional)**

```bash
python -m pytest
```

Os testes usam um banco separado (`risco_ambiental_test`) e não alteram os dados do sistema.

## Banco de dados

Banco `risco_ambiental`, com 3 coleções. O modelo completo, com exemplos de documentos, está em [docs/design.md](docs/design.md).

| Coleção     | O que guarda                                                                                                                                                                                                                                       |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sensors`   | Pontos de monitoramento. Tipos: linígrafo (nível do rio), pluviômetro e estação meteorológica. Cada sensor guarda localização GeoJSON, bairro, fonte, status e os **limiares** de atenção, alerta e emergência de cada variável. |
| `telemetry` | Leituras dos sensores, numa **coleção time-series** (`timeField: ts`, `metaField: sensor_id`). O campo `medidas` varia conforme o tipo de sensor.                                                                                    |
| `alerts`    | Alertas emitidos: tipo, nível (1 atenção, 2 alerta, 3 emergência), gatilho (sensor, variável, valor e limiar), bairros afetados, orientação à população, canais de aviso e status.                                                       |

**Alerta automático:** ao registrar uma leitura, o sistema compara cada medida com os limiares do sensor. Se uma medida passar de algum limiar, ele cria o alerta. Se já houver um alerta ativo para o mesmo sensor e a mesma variável, o sistema não duplica: só sobe o nível quando a leitura piora. Leituras com qualidade `falha` ou `suspeito` não geram alerta.

## CRUD

- **Sensores:** listar, inserir, atualizar e remover.
- **Alertas:** listar, inserir manualmente, atualizar, encerrar e remover.
- **Telemetria:** listar, registrar leitura e remover por período. Coleções time-series limitam a edição de documentos, e leitura de sensor não se edita na vida real.

## Buscas

1. **Alertas ativos agora**, do mais grave para o mais leve.
2. **Leituras de um sensor num período.**
3. **Resumo do dia por sensor:** temperatura máxima, maior rajada e chuva total (agregação com `$group`).
4. **Sensores num raio de X km** de um ponto (`$near` com índice `2dsphere`).
5. **Alertas que já atingiram um bairro** (consulta no array `bairros_afetados`).

## Estrutura

```
app/
  db.py          conexão e criação das coleções e índices
  regras.py      limiares padrão e regras de alerta
  sensores.py    CRUD de sensores
  alertas.py     alerta automático e CRUD de alertas
  telemetria.py  leituras
  buscas.py      as 5 buscas
  terminal.py    leitura de dados digitados
  menu.py        menu do terminal
  seed.py        dados simulados
tests/           testes automatizados (pytest)
dump/            cópia do banco (mongodump)
docs/            enunciado, design e plano
main.py          ponto de entrada
```

## Ao compactar para entrega

Não inclua a pasta `.venv/`.
