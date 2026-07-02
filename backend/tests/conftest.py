"""Shared pytest fixtures for Gordion backend tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.parsers.gfa import parse_gfa
from app.domain.graph import CoreGraph

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tiny_graph() -> CoreGraph:
    """Parse the small committed fixture GFA into a CoreGraph."""
    return parse_gfa(FIXTURES / "tiny.gfa")