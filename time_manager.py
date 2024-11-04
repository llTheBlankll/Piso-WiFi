import threading
import time
from datetime import datetime
import logging
from user_manager import UserManager
from network_controller import NetworkController

class TimeManager:
    def __init__(self, check_interval=30):  # Check every 30 seconds
        self.user_manager = UserManager()
        self.network_controller = NetworkController()
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _run(self):
        while self.running:
            try:
                self._check_and_deduct_time()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in time deduction: {e}")
                time.sleep(1)

    def _check_and_deduct_time(self):
        connected_devices = self.network_controller.get_connected_devices()
        for mac in connected_devices:
            current_balance = self.user_manager.check_balance(mac)
            if current_balance <= 0:
                self.network_controller.block_mac(mac)
                self.logger.info(f"Blocked {mac} due to zero balance")
            else:
                # Deduct 0.5 minutes (30 seconds)
                self.user_manager.deduct_time(mac, 0.5)