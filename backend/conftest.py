import pytest
import redis


@pytest.fixture(autouse=True)
def redis_de_pruebas(settings):
    """
    El estado vivo (presencia, turno, borrador) usa la base 15 de Redis durante
    las pruebas y se vacía antes y después de cada una, para no mezclarse con
    los datos de desarrollo (base 0) ni entre pruebas.
    """
    base, _, _ = settings.REDIS_URL.rpartition("/")
    settings.REDIS_URL = f"{base}/15"
    cliente = redis.Redis.from_url(settings.REDIS_URL)
    cliente.flushdb()
    yield
    cliente.flushdb()
    cliente.close()
