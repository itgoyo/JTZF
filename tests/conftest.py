import sys
from pathlib import Path

# Add project root to sys.path so tests can import project modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure pytest-asyncio
import pytest

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope='session')
def event_loop_policy():
    """Set event loop policy for async tests"""
    import asyncio
    return asyncio.get_event_loop_policy()
