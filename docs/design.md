# Monitoramento de Risco Ambiental — Design

Trabalho 6 (Tópicos Especiais em Banco de Dados): integração do MongoDB com uma aplicação simples.

## Objetivo

Sistema de terminal para a Defesa Civil de uma cidade (Cachoeiro de Itapemirim/ES) acompanhar sensores climáticos, guardar a telemetria e registrar alertas de chuva, enchente, deslizamento, calor e vento.

**Requisitos do professor:** pelo menos 3 coleções, CRUD (inserir, listar, atualizar, remover) e pelo menos 5 buscas que façam sentido no tema. Entrega: código, banco e instruções de ambiente, compactados no AVA. A apresentação fica para depois.

**Fora do escopo:** sensores reais, interface gráfica ou web, autenticação, envio real de SMS, modelagem relacional.

**Seria um fracasso se:** o projeto ficasse mais complicado do que o trabalho pede, ou se o ambiente não subisse seguindo o README.

## Abordagens consideradas

| Abordagem | Prós | Contras |
|---|---|---|
| **Menu no terminal (escolhida)** | Mínimo de código e de dependências | Visual simples na apresentação |
| Streamlit | Mais bonito, pouco código | Dependência extra, outro jeito de programar |
| Flask | Mais controle | Rotas e HTML: complexo demais para o trabalho |

O grupo escolheu o menu no terminal porque o trabalho avalia o banco e o CRUD, não a interface.

## Tecnologia

- Python 3.12 com `pymongo`.
- MongoDB 8 em Docker (`docker-compose.yml`). *Decisão minha:* o Docker roda só o banco; o Python roda direto na máquina.

## Coleções

### `sensors` — pontos de monitoramento

```js
{
  codigo: "CI-LIN-01",
  nome: "Linígrafo Rio Itapemirim – Ponte do Centro",
  tipo: "linigrafo",            // "linigrafo" | "pluviometro" | "estacao_meteorologica"
  localizacao: { type: "Point", coordinates: [-41.1129, -20.8489] },  // [long, lat]
  municipio: "Cachoeiro de Itapemirim",
  bairro: "Centro",
  bacia: "Rio Itapemirim",
  area_de_risco: "encosta",     // opcional (pluviômetros em encosta)
  fonte: "AGERH",
  instalacao: ISODate("2018-03-15"),
  status: "operacional",        // "operacional" | "manutencao" | "inativo"
  intervalo_s: 900,
  limiares: { nivel_m: { atencao: 3.0, alerta: 4.0, emergencia: 5.0 } }
}
```

Limiares de cada tipo:
- **Linígrafo:** `nivel_m`.
- **Pluviômetro:** `chuva_1h_mm` (20/30/60) e `chuva_24h_mm` (30/50/100), conforme os critérios de aviso do INMET.
- **Estação meteorológica:** `temperatura_c` (35/38/40, simplificado) e `rajada_kmh` (40/60/100, conforme o INMET).

Índice `2dsphere` em `localizacao`. As coordenadas são aproximadas e precisam ser conferidas no mapa.

### `telemetry` — leituras (coleção time-series)

```js
// db.createCollection("telemetry", { timeseries: { timeField: "ts", metaField: "sensor_id", granularity: "minutes" } })
{
  ts: ISODate("2026-11-27T14:00:00Z"),
  sensor_id: ObjectId("..."),
  medidas: { temperatura_c: 36.1, umidade_pct: 38, pressao_hpa: 1009.4,
             vento_kmh: 14.0, rajada_kmh: 52.3, direcao_vento_graus: 110, chuva_mm: 0 },
  qualidade: "ok"               // "ok" | "suspeito" | "falha"
}
// linígrafo:   medidas: { nivel_m: 3.42 }
// pluviômetro: medidas: { chuva_mm: 3.2, chuva_1h_mm: 18.4, chuva_24h_mm: 62.0 }
```

### `alerts` — alertas emitidos

```js
{
  tipo: "chuva_intensa",        // "chuva_intensa" | "enchente" | "deslizamento" | "calor_extremo" | "vendaval"
  nivel: 2,                     // 1 atenção (amarelo) | 2 alerta (laranja) | 3 emergência (vermelho)
  inicio: ISODate("2026-11-27T13:10:00Z"),
  fim: null,
  gatilho: { sensor_id: ObjectId("..."), variavel: "chuva_1h_mm", valor_observado: 34.2, limiar: 30 },
  bairros_afetados: ["Gilson Carone"],
  orientacao: "Evite áreas de encosta e não atravesse ruas alagadas.",
  canais: ["sms_40199", "site_prefeitura"],
  status: "ativo"               // "ativo" | "encerrado" | "falso_positivo"
}
```

## Regra de alerta automático

Ao inserir uma leitura, o programa compara cada medida com os `limiares` do sensor. Se uma medida passar de algum limiar, ele cria um alerta com o nível correspondente.

Decisões minhas:
- **Não duplicar alertas.** Se já houver um alerta `ativo` para o mesmo sensor e a mesma variável, o programa não cria outro. Só sobe o nível, se a nova leitura for pior.
- **Tipo do alerta pela variável:**
  - `nivel_m` → enchente
  - `chuva_1h_mm` → chuva intensa
  - `chuva_24h_mm` → deslizamento, se o sensor tiver `area_de_risco: "encosta"`; senão, chuva intensa
  - `temperatura_c` → calor extremo
  - `rajada_kmh` → vendaval
- **Valores iniciais preenchidos pelo programa:**
  - `bairros_afetados` = bairro do sensor;
  - `orientacao` = texto padrão do tipo;
  - `canais` = `["site_prefeitura"]` no nível 1, e mais `"sms_40199"` nos níveis 2 e 3.

  O operador pode editar esses campos depois pelo menu.

## CRUD

- **`sensors` e `alerts`:** CRUD completo. Encerrar um alerta é uma atualização: `status`, mais `fim` com a data e hora.
- **`telemetry`:** inserir, listar e apagar por período. Coleções time-series limitam a edição, e leitura de sensor não se edita na vida real.

## Buscas

1. Alertas ativos agora, do mais grave para o mais leve.
2. Leituras de um sensor num período (ex.: nível do rio nas últimas 24h).
3. Resumo do dia por sensor: temperatura máxima, maior rajada e chuva total (`$group`).
4. Sensores num raio de X km de um ponto (`$near`).
5. Alertas que já atingiram um bairro (consulta em `bairros_afetados`).

## Dados e entrega

- **Script de dados simulados:** cria uns 5 sensores e alguns dias de leituras, com pelo menos um episódio de chuva forte e um de calor. Os alertas saem da própria regra automática.
- **Banco construído:** o script recria o banco do zero. *Decisão minha:* incluir também um dump (`mongodump`) gerado a partir dele.
- **README:** subir o Docker, instalar as dependências, popular o banco e rodar o menu.

## Fica a cargo de quem implementar

- Organização das pastas e dos arquivos Python.
- Formato da exibição no terminal.
- Valores exatos dos dados simulados.
- Textos padrão de orientação.
