"""Popula o banco com sensores e leituras simuladas.

Uso: python -m app.seed

As leituras são geradas de hora em hora (simplificação: ignora o intervalo_s
de cada sensor) e passam por registrar_leitura, então os alertas saem da
própria regra automática. Episódios simulados:
  - calor: na primeira tarde completa da janela, a estação passa de 38 °C;
  - chuva forte: na última tarde completa, chuva intensa nos pluviômetros;
  - cheia: logo depois da chuva, o Rio Itapemirim passa de 4,0 m no Centro.
"""
import math
import random
from datetime import datetime, timedelta, timezone

from pymongo.database import Database

from app.alertas import encerrar_alerta
from app.db import criar_colecoes, get_db
from app.regras import FUSO
from app.sensores import inserir_sensor
from app.telemetria import registrar_leitura

UTC = timezone.utc
CACHOEIRO = "Cachoeiro de Itapemirim"

SENSORES = [
    {
        "codigo": "CI-LIN-01",
        "nome": "Linígrafo Rio Itapemirim – Ponte do Centro",
        "tipo": "linigrafo",
        "localizacao": {"type": "Point", "coordinates": [-41.1129, -20.8489]},
        "municipio": CACHOEIRO,
        "bairro": "Centro",
        "bacia": "Rio Itapemirim",
        "fonte": "AGERH",
        "instalacao": datetime(2018, 3, 15, tzinfo=UTC),
        "intervalo_s": 900,
    },
    {
        "codigo": "CI-PLU-03",
        "nome": "Pluviômetro Gilson Carone",
        "tipo": "pluviometro",
        "localizacao": {"type": "Point", "coordinates": [-41.1040, -20.8350]},
        "municipio": CACHOEIRO,
        "bairro": "Gilson Carone",
        "area_de_risco": "encosta",
        "bacia": "Rio Itapemirim",
        "fonte": "Cemaden",
        "instalacao": datetime(2019, 8, 2, tzinfo=UTC),
        "intervalo_s": 600,
    },
    {
        "codigo": "CI-PLU-05",
        "nome": "Pluviômetro Village da Luz",
        "tipo": "pluviometro",
        "localizacao": {"type": "Point", "coordinates": [-41.1250, -20.8600]},
        "municipio": CACHOEIRO,
        "bairro": "Village da Luz",
        "bacia": "Rio Itapemirim",
        "fonte": "Cemaden",
        "instalacao": datetime(2020, 1, 20, tzinfo=UTC),
        "intervalo_s": 600,
    },
    {
        "codigo": "CI-EST-01",
        "nome": "Estação Meteorológica Centro",
        "tipo": "estacao_meteorologica",
        "localizacao": {"type": "Point", "coordinates": [-41.1110, -20.8470]},
        "municipio": CACHOEIRO,
        "bairro": "Centro",
        "fonte": "Defesa Civil Municipal",
        "instalacao": datetime(2021, 6, 10, tzinfo=UTC),
        "intervalo_s": 3600,
    },
    {
        "codigo": "CS-LIN-01",
        "nome": "Estação Hidrológica Castelo – Rio Castelo",
        "tipo": "linigrafo",
        "localizacao": {"type": "Point", "coordinates": [-41.1847, -20.6033]},
        "municipio": "Castelo",
        "rio": "Rio Castelo",
        "bacia": "Rio Itapemirim",
        "fonte": "AGERH/Cemaden",
        "instalacao": datetime(2017, 11, 5, tzinfo=UTC),
        "intervalo_s": 3600,
        "limiares": {"nivel_m": {"atencao": 2.5, "alerta": 3.5, "emergencia": 4.5}},
    },
]

# Chuva por hora (mm) a partir das 13h do dia da chuva forte.
CHUVA_FORTE = {"CI-PLU-03": [8, 18, 34, 26, 12], "CI-PLU-05": [5, 12, 22, 15, 6]}
HORA_CHUVA = 13


def _curva_dia(hora_local: int) -> float:
    """0 de madrugada (3h), 1 no meio da tarde (15h)."""
    return (1 + math.cos(2 * math.pi * (hora_local - 15) / 24)) / 2


def _tardes_completas(horas: list[datetime]) -> list:
    """Datas locais cujas horas de 12h a 19h estão todas dentro da janela."""
    presentes = {(t.astimezone(FUSO).date(), t.astimezone(FUSO).hour) for t in horas}
    return sorted({d for d, _ in presentes if all((d, h) in presentes for h in range(12, 20))})


def popular(db: Database, dias: int = 3, agora: datetime | None = None) -> dict[str, int]:
    rng = random.Random(42)
    agora = agora or datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    inicio = agora - timedelta(hours=dias * 24 - 1)
    horas = [inicio + timedelta(hours=i) for i in range(dias * 24)]
    tardes = _tardes_completas(horas)
    dia_calor, dia_chuva = tardes[0], tardes[-1]

    for nome in ("sensors", "telemetry", "alerts"):
        db.drop_collection(nome)
    criar_colecoes(db)
    for sensor in SENSORES:
        inserir_sensor(db, dict(sensor))

    inicio_chuva = datetime(dia_chuva.year, dia_chuva.month, dia_chuva.day, HORA_CHUVA, tzinfo=FUSO)
    historico_chuva = {codigo: [] for codigo in CHUVA_FORTE}
    for ts in horas:
        local = ts.astimezone(FUSO)
        curva = _curva_dia(local.hour)
        # Horas desde o início da chuva forte (negativo = antes). Continua contando
        # depois da meia-noite, para o rio baixar aos poucos.
        k = int((ts - inicio_chuva).total_seconds() // 3600)
        chovendo = 0 <= k < 5

        # Estação meteorológica
        calor = 8.5 * curva if local.date() == dia_calor else 0
        temperatura = 21 + 10 * curva + calor + rng.uniform(-0.3, 0.3)
        vento = 8 + 10 * curva + rng.uniform(-1, 1)
        rajada = vento * 1.6 + rng.uniform(0, 2) + (18 if chovendo else 0)
        registrar_leitura(db, "CI-EST-01", {
            "temperatura_c": round(temperatura, 1),
            "umidade_pct": round(max(15, min(100, 88 - 40 * curva - (15 if calor else 0) + (10 if chovendo else 0)))),
            "pressao_hpa": round(1012 + rng.uniform(-1.5, 1.5) - (4 if chovendo else 0), 1),
            "vento_kmh": round(vento, 1),
            "rajada_kmh": round(rajada, 1),
            "direcao_vento_graus": rng.randint(60, 160),
            "chuva_mm": round(CHUVA_FORTE["CI-PLU-05"][k] * 0.8, 1) if chovendo else 0.0,
        }, ts=ts)

        # Pluviômetros: chuva da hora, da última hora e acumulado de 24h
        for codigo, serie in CHUVA_FORTE.items():
            chuva = serie[k] if chovendo else (round(rng.uniform(0.2, 2.0), 1) if rng.random() < 0.08 else 0.0)
            historico_chuva[codigo].append(chuva)
            registrar_leitura(db, codigo, {
                "chuva_mm": chuva,
                "chuva_1h_mm": chuva,
                "chuva_24h_mm": round(sum(historico_chuva[codigo][-24:]), 1),
            }, ts=ts)

        # Linígrafos: o rio sobe depois da chuva e baixa devagar
        if k < 0:
            subida_centro = subida_castelo = 0.0
        else:
            subida_centro = 2.4 * min(1, k / 5) if k <= 6 else max(0, 2.4 - 0.15 * (k - 6))
            subida_castelo = 1.5 * min(1, k / 3) if k <= 4 else max(0, 1.5 - 0.15 * (k - 4))
        registrar_leitura(db, "CI-LIN-01", {"nivel_m": round(1.8 + subida_centro + rng.uniform(-0.03, 0.03), 2)}, ts=ts)
        registrar_leitura(db, "CS-LIN-01", {"nivel_m": round(1.2 + subida_castelo + rng.uniform(-0.03, 0.03), 2)}, ts=ts)

    # O episódio de calor já passou: encerra o alerta no fim daquela tarde.
    fim_calor = datetime(dia_calor.year, dia_calor.month, dia_calor.day, 19, tzinfo=FUSO).astimezone(UTC)
    for alerta in db.alerts.find({"tipo": "calor_extremo", "status": "ativo"}):
        encerrar_alerta(db, alerta["_id"], status="encerrado", fim=fim_calor)

    return {
        "sensors": db.sensors.count_documents({}),
        "telemetry": db.telemetry.count_documents({}),
        "alerts": db.alerts.count_documents({}),
    }


if __name__ == "__main__":
    contagem = popular(get_db())
    print(f"Banco populado: {contagem['sensors']} sensores, "
          f"{contagem['telemetry']} leituras, {contagem['alerts']} alertas.")
