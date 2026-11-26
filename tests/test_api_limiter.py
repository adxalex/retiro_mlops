
import pytest

from security import RateLimiter


class FakeClock:
    """Reloj controlable para no esperar minutos reales en los tests."""

    def __init__(self, initial_time=0):
        self.current_time = initial_time

    def __call__(self):
        return self.current_time

    def advance(self, seconds):
        self.current_time += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def limiter(clock):
    return RateLimiter(limit=30, clock=clock)


def test_permite_hasta_30_peticiones(limiter):
    for _ in range(30):
        assert limiter.allow("clave-a") is True


def test_rechaza_la_peticion_31(limiter):
    for _ in range(30):
        limiter.allow("clave-a")

    assert limiter.allow("clave-a") is False


def test_reinicia_el_contador_al_cambiar_de_minuto(limiter, clock):
    for _ in range(30):
        limiter.allow("clave-a")

    assert limiter.allow("clave-a") is False

    clock.advance(60)

    assert limiter.allow("clave-a") is True


def test_cada_api_key_tiene_su_propio_contador(limiter):
    for _ in range(30):
        limiter.allow("clave-a")

    assert limiter.allow("clave-a") is False

    # La clave B debe tener su propio contador.
    assert limiter.allow("clave-b") is True
