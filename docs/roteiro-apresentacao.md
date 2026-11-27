# Roteiro da apresentação (10 minutos, 2 pessoas)

Sem slides. A demonstração acontece no terminal, com duas passagens rápidas pelo código no editor. **A** e **B** são os dois apresentadores.

| Tempo | Quem | Bloco |
|---|---|---|
| 0:00 – 1:00 | A | Abertura: o problema e o que o sistema faz |
| 1:00 – 3:30 | B | O banco: as 3 coleções, vistas no `mongosh` |
| 3:30 – 6:30 | A | O sistema: CRUD e alerta automático |
| 6:30 – 9:00 | B | As 5 buscas |
| 9:00 – 10:00 | A | Fechamento e perguntas |

---

## Antes de começar (preparação)

1. Abrir o Docker Desktop e subir o banco:
   ```powershell
   docker compose up -d
   ```
2. **Restaurar o dump**, para os dados ficarem iguais aos deste roteiro. Refazer isso depois de cada ensaio, porque a demonstração altera o banco:
   ```powershell
   docker compose exec mongo mongorestore --archive=/dump/risco_ambiental.archive.gz --gzip --drop
   ```
3. Deixar **dois terminais** abertos na pasta do projeto, com a fonte grande (Ctrl + roda do mouse):
   - **Terminal 1 (banco):**
     ```powershell
     docker compose exec mongo mongosh risco_ambiental --quiet
     ```
   - **Terminal 2 (sistema):**
     ```powershell
     .venv\Scripts\python main.py
     ```
4. Deixar `app/regras.py` e `app/alertas.py` abertos no editor, com a fonte grande.
5. Ensaiar uma vez cronometrando. Os passos marcados como *(opcional)* podem ser cortados se o tempo apertar.

**Os dados do dump:**
- leituras de 24/11/2026 02:00 a 27/11/2026 01:00;
- **24/11:** onda de calor;
- **26/11:** chuva forte à tarde, seguida de cheia do rio.

---

## 0:00 – 1:00 · Abertura (A)

**Mostrar:** o Terminal 2, com o menu principal aberto.

**Falar:**
- "Nosso tema é **monitoramento de risco ambiental** em Cachoeiro de Itapemirim. A cidade sofre com enchente do Rio Itapemirim, deslizamento nas encostas e, no verão, calor forte e vendaval."
- "A Defesa Civil acompanha isso com sensores:
  - **linígrafos**, que medem o nível do rio;
  - **pluviômetros**, que medem a chuva;
  - uma **estação meteorológica**, que mede temperatura, vento e umidade."
- "O sistema faz três coisas:
  - guarda os sensores;
  - recebe as leituras;
  - **gera alertas sozinho** quando uma medida passa do limite, com nível de atenção, alerta ou emergência, como faz o INMET."
- "Usamos Python com MongoDB rodando no Docker. Os dados são simulados, mas os sensores, os limites e os bairros seguem a realidade da cidade."

---

## 1:00 – 3:30 · O banco (B)

**Mostrar:** o Terminal 1 (`mongosh`).

```js
show collections
```

**Falar:** "São 3 coleções: `sensors`, `telemetry` e `alerts`. A `telemetry` é uma **coleção time-series**, um tipo próprio do MongoDB para dados de sensor."

```js
db.sensors.findOne({ codigo: "CI-PLU-03" })
```

**Falar:**
- "Este é um pluviômetro no Gilson Carone, que é área de encosta."
- "A localização está em **GeoJSON**, o que permite buscar sensores por distância."
- "Os **limiares** ficam dentro do próprio sensor, com os três níveis para cada variável. Não precisamos de outra tabela para isso."

```js
db.telemetry.findOne({ "medidas.temperatura_c": { $exists: true } })
db.telemetry.findOne({ "medidas.nivel_m": { $exists: true } })
```

**Falar:**
- "Aqui está a vantagem do modelo de documentos. A leitura da estação traz 7 medidas, e a do linígrafo traz só uma. Cada documento tem os campos de que precisa, sem colunas vazias."
- "Como é time-series, o Mongo agrupa as leituras por sensor e por período. No nosso banco, as 360 leituras ficam guardadas em só 15 blocos internos."

```js
db.alerts.findOne({ tipo: "deslizamento" })
```

**Falar:**
- "Um alerta guarda o **gatilho**: qual sensor, qual variável, o valor medido e o limite que foi ultrapassado. Isso fica registrado mesmo se o limite do sensor mudar depois."
- "Também guarda a lista de **bairros afetados**, a orientação para a população e os canais de aviso, como o SMS 40199 da Defesa Civil."
- "Não usamos chave estrangeira. Quem garante a consistência entre as coleções é o código Python."

---

## 3:30 – 6:30 · O sistema: CRUD e alerta automático (A)

**Mostrar:** o Terminal 2. Menu principal: `1` Sensores, `2` Telemetria, `3` Alertas, `4` Buscas.

**1. Listar sensores**
- **Digitar:** `1` → `1`
- **Falar:** "Os 5 sensores: dois linígrafos, dois pluviômetros e a estação. Um dos linígrafos fica em Castelo, rio acima, e serve para antecipar a cheia."

**2. Atualizar um sensor**
- **Digitar:** `3` → `4` (CI-PLU-05) → `1` (Status) → `2` (manutencao) → `1` (Listar) → `0`
- **Falar:** "O sensor do Village da Luz entrou em manutenção."

**Código após o passo 2 · `regras.py` (15 s)**

- **Mostrar** `LIMIARES_PADRAO`, na linha de `chuva_1h_mm` do pluviômetro.
- **Falar** “O pluviômetro do Gilson Carone usa estes limites. Em uma hora, 20 mm dão atenção, 30 mm dão alerta e 60 mm dão emergência. Vamos testar com 65 mm.” Voltar ao Terminal 2.

**3. Registrar uma leitura que gera alerta** (o momento principal da demonstração)
- **Digitar:** `2` → `2` → `CI-PLU-03` → chuva_mm `20` → chuva_1h_mm `65` → Enter (pula chuva_24h_mm) → Enter (data/hora atual) → `1` (ok)
- **Aparece** a tabela “Alertas gerados ou elevados pela leitura”, com **EMERGÊNCIA**, chuva intensa, 65 mm medidos e limiar de 60 mm.
- **Falar** “Os 65 mm em uma hora no Gilson Carone elevaram o alerta ativo de nível 2 para emergência.”

**Código após o passo 3 · `alertas.py` (25 s)**

- **Mostrar** `processar_leitura`, primeiro a chamada a `avaliar_medidas` de `regras.py`, depois o `find_one` e o `elif` com `find_one_and_update`.
- **Falar** “`avaliar_medidas` compara a leitura com os limites salvos no sensor. Com 65 mm, devolve o nível 3. `processar_leitura` encontrou um alerta ativo do mesmo sensor para chuva em uma hora e atualizou o próprio documento no MongoDB com o novo nível, o valor de 65 mm e o limiar de 60 mm.”
- Voltar ao Terminal 2. Se for pular o passo 4, digitar `0` para voltar ao menu principal.

**4. Leitura com falha não dispara alerta** *(opcional)*
- **Digitar:** `2` → `CI-PLU-05` → Enter → `99` → Enter → Enter → `3` (falha) → `0`
- **Falar:** "O sensor em manutenção mandou 99 mm marcados como falha. A leitura é guardada, mas **não gera alerta**. Um sensor com defeito não pode disparar SMS para a cidade."

**5. CRUD de alertas**
- **Inserir:** `3` → `2` → `5` (vendaval) → `1` (atenção) → bairros `Aquidabã` → Enter (orientação padrão)
  - **Falar:** "O operador também pode registrar um alerta manualmente."
- **Encerrar** (atualização): `4` → `8` (o vendaval de 26/11, último da lista) → `1` (encerrado)
  - **Falar:** "Encerrar muda o status e grava o horário de fim."
- **Remover:** `5` → `1` (o alerta recém-criado, primeiro da lista) → `s` → `0`
- **Falar:** "Com isso temos inserir, listar, atualizar e remover nas coleções."

---

## 6:30 – 9:00 · As 5 buscas (B)

**Mostrar:** o Terminal 2 → `4` (Buscas).

**1. Alertas ativos agora**
- **Digitar:** `1`
- **Falar:** "A lista vai do mais grave para o mais leve. No topo está a emergência que acabamos de gerar. Isso é um `find` com filtro de status e ordenação por nível."

**2. Leituras de um sensor num período**
- **Digitar:** `2` → `CI-LIN-01` → início `26/11/2026 12:00` → fim `27/11/2026 01:00`
- **Falar:** "Este é o nível do rio no Centro. Ele estava em 1,8 m, a chuva começa às 13h, o rio passa da cota de alerta de 4 m às 18h e depois baixa devagar."

**3. Resumo do dia por sensor**
- **Digitar:** `3` → `26/11/2026`
- **Falar:**
  - "Esta é uma **agregação** com `$group`: para cada sensor, a temperatura máxima, a maior rajada e a chuva total do dia. O Gilson Carone acumulou cerca de 100 mm."
  - "Leituras marcadas como falha ficam de fora do resumo."

**4. Sensores num raio de X km**
- **Digitar:** `4` → Enter → Enter (centro da cidade) → `5`
- **Falar:** "Busca geográfica com `$near` e índice `2dsphere`. Num raio de 5 km aparecem os 4 sensores da cidade. O de Castelo fica de fora, porque está a uns 28 km."
- *(opcional)* Repetir com raio `50`: o sensor de Castelo aparece.

**5. Alertas que atingiram um bairro**
- **Digitar:** `5` → `gilson carone`
- **Falar:** "Esta é uma busca dentro do array `bairros_afetados`, sem diferenciar maiúsculas de minúsculas. Ela mostra o histórico de risco do bairro."

---

## 9:00 – 10:00 · Fechamento (A)

**Mostrar:** o menu principal → `0` (Sair).

**Falar:**
- "Resumindo, temos:
  - 3 coleções, uma delas time-series;
  - CRUD completo;
  - alerta automático por limiar, que não duplica e só sobe de nível;
  - 5 buscas, com agregação e busca geográfica."
- "Na entrega vão o código, um **dump** do banco, um script que gera os dados de novo e o README com a montagem do ambiente em três comandos. Também fizemos 56 testes automatizados."
- "Limitações: os dados são simulados, e a consistência entre as coleções fica por conta do código, porque o Mongo não tem chave estrangeira."
- "Obrigado. Ficamos à disposição para perguntas."

---

## Perguntas prováveis (respostas curtas)

- **Por que MongoDB e não um banco relacional?**
  - Cada tipo de sensor manda campos diferentes, e o documento acomoda isso.
  - A coleção time-series foi feita para leituras de sensor.
  - Os limiares e o gatilho do alerta ficam embutidos no documento.
  - **Contra:** não há chave estrangeira, então a consistência fica no código.
- **O que é uma coleção time-series?**
  - É uma coleção otimizada para medições ao longo do tempo.
  - O Mongo agrupa as leituras por sensor (`metaField`) e por tempo (`timeField`) em blocos compactos.
- **Por que não dá para editar uma leitura?**
  - Coleções time-series limitam edições.
  - Na vida real, leitura de sensor não se edita: se estiver errada, é marcada como falha ou apagada.
- **Como vocês evitam alertas duplicados?**
  - Antes de criar, o sistema procura um alerta ativo do mesmo sensor e da mesma variável.
  - Se existir, só sobe o nível quando a leitura piora.
- **Por que o alerta guarda o valor e o limite?**
  - É um registro histórico: mostra o que disparou o alerta naquele momento, mesmo que alguém mude o limite do sensor depois.
- **Como funciona o fuso horário?**
  - O banco guarda tudo em UTC.
  - A tela mostra e recebe as datas no horário de Brasília.
- **Como o professor monta o ambiente?**
  - Seguindo o README: `docker compose up -d`, instalar as dependências e restaurar o dump (ou rodar o seed).

## Se algo der errado

- **Erro de conexão no menu:** o Docker caiu. Rode `docker compose up -d` e continue. O menu mostra a mensagem e não fecha.
- **Dados diferentes do roteiro:** restaure o dump (passo 2 da preparação).
- **Digitou errado:** o sistema pede de novo. Para voltar, use `0`.
