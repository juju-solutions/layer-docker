import sys
from unittest.mock import MagicMock

# mock dependencies which we don't care about covering in our tests
sys.modules['charms.docker'] = MagicMock()
sys.modules['charms.reactive'] = MagicMock()
