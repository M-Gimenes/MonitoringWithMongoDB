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
