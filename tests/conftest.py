import pytest

from app.db import criar_colecoes, get_db

TEST_DB = "risco_ambiental_test"


@pytest.fixture
def db():
    banco = get_db(TEST_DB)
    banco.client.drop_database(TEST_DB)
    criar_colecoes(banco)
    yield banco
    banco.client.drop_database(TEST_DB)


@pytest.fixture
def sensor_exemplo():
    def _criar(**campos):
        base = {
            "codigo": "CI-PLU-03",
            "nome": "Pluviômetro Gilson Carone",
            "tipo": "pluviometro",
            "localizacao": {"type": "Point", "coordinates": [-41.1040, -20.8350]},
            "municipio": "Cachoeiro de Itapemirim",
            "bairro": "Gilson Carone",
            "area_de_risco": "encosta",
            "fonte": "Cemaden",
            "intervalo_s": 600,
        }
        base.update(campos)
        return base

    return _criar
