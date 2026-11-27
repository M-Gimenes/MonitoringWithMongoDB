from app.regras import LIMIARES_PADRAO, avaliar_medidas, canais_por_nivel, tipo_alerta

LIM = {"chuva_1h_mm": {"atencao": 20, "alerta": 30, "emergencia": 60}}


def test_abaixo_do_limiar_nao_gera_nada():
    assert avaliar_medidas(LIM, {"chuva_1h_mm": 19.9}) == []


def test_nivel_e_o_maior_atingido():
    assert avaliar_medidas(LIM, {"chuva_1h_mm": 34.2}) == [
        {"variavel": "chuva_1h_mm", "nivel": 2, "valor_observado": 34.2, "limiar": 30}
    ]


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
