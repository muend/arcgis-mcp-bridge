"""Tests/conftest.py - Global pytest configuration and heavy dependency mocking."""

import sys
from unittest.mock import MagicMock

import pytest


# ArcPy Paradoksunu Çözme: Testler tetiklendiği an, gerçek arcpy yerine
# sistem hafızasına (sys.modules) sahte bir MagicMock nesnesi enjekte edilir.
# Böylece Layer A ve Layer B test edilirken ArcGIS lisans hatası alınmaz.
@pytest.fixture(scope="session", autouse=True)
def mock_arcpy_environment() -> None:
    """Creates a fake arcpy module in sys.modules to isolate tests from ArcGIS Pro."""
    mock_arcpy = MagicMock()
    mock_arcpy.__name__ = "arcpy"

    # Alt modülleri ve CBS uzantı yönetimini simüle edelim
    mock_sa = MagicMock()
    mock_arcpy.sa = mock_sa
    mock_arcpy.CheckExtension.return_value = "Available"

    # Python yol haritasına sahte modülleri mühürle
    sys.modules["arcpy"] = mock_arcpy
    sys.modules["arcpy.sa"] = mock_sa
    sys.modules["sa"] = mock_sa
