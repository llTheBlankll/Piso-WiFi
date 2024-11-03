import pytest
from network_controller import NetworkController
from unittest.mock import patch

@pytest.fixture
def network_controller():
    return NetworkController()

def test_block_mac(network_controller):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        assert network_controller.block_mac("00:11:22:33:44:55") == True
        mock_run.assert_called_once()

def test_unblock_mac(network_controller):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        assert network_controller.unblock_mac("00:11:22:33:44:55") == True
        mock_run.assert_called_once()

def test_get_connected_devices(network_controller):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = "? (192.168.1.1) at 00:11:22:33:44:55 [ether]"
        mock_run.return_value.returncode = 0
        devices = network_controller.get_connected_devices()
        assert len(devices) == 1
        assert "00:11:22:33:44:55" in devices[0] 