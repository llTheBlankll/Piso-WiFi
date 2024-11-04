import threading
import time
from datetime import datetime
import logging
from user_manager import UserManager
from network_controller import NetworkController

class TimeManager:
    def __init__(self, check_interval=5):
        self.user_manager = UserManager()
        self.network_controller = NetworkController()
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)
        self.last_deduction = {}
        self.last_check = 0
        
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
        """Main loop for time management"""
        while self.running:
            try:
                self._check_and_deduct_time()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Error in time manager run loop: {e}")
                time.sleep(1)  # Prevent tight loop on error

    def _check_and_deduct_time(self):
        """Check and deduct time from connected devices"""
        try:
            current_time = time.time()
            
            # Only check every 5 seconds
            if current_time - self.last_check < self.check_interval:
                return
            self.last_check = current_time
            
            connected_devices = self.network_controller.get_connected_devices()
            
            for device in connected_devices:
                mac = device['mac_address']
                try:
                    current_balance = self.user_manager.check_balance(mac)
                    self.logger.debug(f"Current balance for {mac}: {current_balance}")

                    if current_balance <= 0:
                        self.logger.info(f"Balance zero for {mac}, blocking...")
                        self.network_controller.block_mac(mac)
                        if mac in self.last_deduction:
                            del self.last_deduction[mac]
                    else:
                        last_time = self.last_deduction.get(mac, current_time - 60)
                        elapsed_minutes = (current_time - last_time) / 60.0

                        if elapsed_minutes >= 1.0:
                            minutes_to_deduct = int(elapsed_minutes)
                            if self.user_manager.deduct_time(mac, minutes_to_deduct):
                                self.last_deduction[mac] = current_time
                                new_balance = self.user_manager.check_balance(mac)
                                self.logger.info(f"Deducted {minutes_to_deduct} minute(s) from {mac}, remaining balance: {new_balance}")
                                
                                if new_balance <= 0:
                                    self.logger.info(f"Balance depleted for {mac}, blocking...")
                                    self.network_controller.block_mac(mac)

                except Exception as e:
                    self.logger.error(f"Error checking balance for {mac}: {e}")

            # Clean up disconnected devices
            disconnected = set(self.last_deduction.keys()) - {d['mac_address'] for d in connected_devices}
            for mac in disconnected:
                del self.last_deduction[mac]

        except Exception as e:
            self.logger.error(f"Error in check_and_deduct_time: {e}")