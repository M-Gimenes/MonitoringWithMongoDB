"""Regras de alerta: limiares, tipos e canais. Funções puras, sem banco."""
from datetime import timedelta, timezone

# Horário de Brasília (sem horário de verão desde 2019).
FUSO = timezone(timedelta(hours=-3))

NIVEIS = {"atencao": 1, "alerta": 2, "emergencia": 3}

TIPOS_SENSOR = ("linigrafo", "pluviometro", "estacao_meteorologica")

# Chuva e vento seguem os critérios de aviso do INMET; calor é simplificado.
LIMIARES_PADRAO = {
    "linigrafo": {
        "nivel_m": {"atencao": 3.0, "alerta": 4.0, "emergencia": 5.0},
    },
    "pluviometro": {
        "chuva_1h_mm": {"atencao": 20, "alerta": 30, "emergencia": 60},
        "chuva_24h_mm": {"atencao": 30, "alerta": 50, "emergencia": 100},
    },
    "estacao_meteorologica": {
        "temperatura_c": {"atencao": 35, "alerta": 38, "emergencia": 40},
        "rajada_kmh": {"atencao": 40, "alerta": 60, "emergencia": 100},
    },
}

VARIAVEIS_POR_TIPO = {
    "linigrafo": ["nivel_m"],
    "pluviometro": ["chuva_mm", "chuva_1h_mm", "chuva_24h_mm"],
    "estacao_meteorologica": [
        "temperatura_c", "umidade_pct", "pressao_hpa", "vento_kmh",
        "rajada_kmh", "direcao_vento_graus", "chuva_mm",
    ],
}

ORIENTACOES = {
    "chuva_intensa": "Evite áreas de encosta e não atravesse ruas alagadas.",
    "enchente": "Moradores de áreas ribeirinhas: retirem pertences de locais baixos e fiquem atentos aos avisos.",
    "deslizamento": "Moradores de encostas: observem rachaduras e estalos e procurem local seguro.",
    "calor_extremo": "Beba água, evite sol entre 10h e 16h e atenção a idosos e crianças.",
    "vendaval": "Evite ficar sob árvores, placas e redes elétricas.",
}

TIPO_POR_VARIAVEL = {
    "nivel_m": "enchente",
    "chuva_1h_mm": "chuva_intensa",
    "chuva_24h_mm": "chuva_intensa",
    "temperatura_c": "calor_extremo",
    "rajada_kmh": "vendaval",
}


def avaliar_medidas(limiares: dict, medidas: dict) -> list[dict]:
    """Devolve as variáveis que atingiram algum limiar, com o maior nível atingido."""
    resultado = []
    for variavel, faixas in limiares.items():
        if variavel not in medidas:
            continue
        valor = medidas[variavel]
        atingido = None
        for nome, nivel in NIVEIS.items():
            if valor >= faixas[nome]:
                atingido = (nivel, faixas[nome])
        if atingido:
            nivel, limiar = atingido
            resultado.append(
                {"variavel": variavel, "nivel": nivel, "valor_observado": valor, "limiar": limiar}
            )
    return resultado


def tipo_alerta(variavel: str, sensor: dict) -> str:
    if variavel == "chuva_24h_mm" and sensor.get("area_de_risco") == "encosta":
        return "deslizamento"
    return TIPO_POR_VARIAVEL[variavel]


def canais_por_nivel(nivel: int) -> list[str]:
    if nivel >= 2:
        return ["sms_40199", "site_prefeitura"]
    return ["site_prefeitura"]
