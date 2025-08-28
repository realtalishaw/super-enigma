"""
Basic tests to verify the test setup is working.
"""
import pytest
import sys
import os
from pathlib import Path


def test_python_path():
    """Test that Python path is set correctly."""
    project_root = Path(__file__).parent.parent
    assert str(project_root) in sys.path


def test_imports():
    """Test that basic imports work."""
    try:
        from fastapi import FastAPI
        assert FastAPI is not None
    except ImportError:
        pytest.fail("FastAPI could not be imported")


def test_project_structure():
    """Test that project structure is correct."""
    project_root = Path(__file__).parent.parent
    
    # Check that key directories exist
    assert (project_root / "api").exists()
    assert (project_root / "core").exists()
    assert (project_root / "services").exists()
    assert (project_root / "tests").exists()


def test_test_configuration():
    """Test that test configuration is loaded."""
    # This test should always pass if pytest is working
    assert True


@pytest.mark.unit
def test_unit_test_marker():
    """Test that unit test markers work."""
    assert True


@pytest.mark.api
def test_api_test_marker():
    """Test that API test markers work."""
    assert True


@pytest.mark.services
def test_services_test_marker():
    """Test that services test markers work."""
    assert True


@pytest.mark.core
def test_core_test_marker():
    """Test that core test markers work."""
    assert True
