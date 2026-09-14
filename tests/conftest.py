import json

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.db import Base, make_engine, session_factory
from backend.schemas import Preferences, Profile
from backend.service import ROOT, bootstrap


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(engine):
    factory = session_factory(engine)
    with factory() as session:
        bootstrap(session)
    return factory


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    with TestClient(create_app(engine, seed_demo=True)) as client:
        yield client


@pytest.fixture
def profile():
    return Profile.model_validate(json.loads((ROOT / "config/candidate.json").read_text()))


@pytest.fixture
def prefs():
    return Preferences()
