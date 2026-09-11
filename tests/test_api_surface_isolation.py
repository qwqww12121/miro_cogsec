"""The maintained CogSec API must start without importing legacy services."""

from app import create_app
from app.config import Config


class CoreOnlyConfig(Config):
    DEBUG = True
    TESTING = True
    SECRET_KEY = "test-secret"
    CORS_ORIGINS = []
    ENABLE_LEGACY_MIROFISH_API = False


def test_default_api_surface_excludes_legacy_blueprints():
    app = create_app(CoreOnlyConfig)
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert any(route.startswith("/api/cogsec") for route in routes)
    assert not any(route.startswith("/api/graph") for route in routes)
    assert not any(route.startswith("/api/simulation") for route in routes)
    assert not any(route.startswith("/api/report") for route in routes)
