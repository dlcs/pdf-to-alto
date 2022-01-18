import signal

from logzero import logger


class SignalHandler:
    """Handles sigterm and sigint events"""

    def __init__(self):
        self._cancellation_requested = False
        self._setup_signal_handling()

    def cancellation_requested(self):
        """
        Verify if lifecycle is to continue
        :return: True if cancellation requested, else False
        """
        return self._cancellation_requested

    def _signal_handler(self, signum, frame):
        logger.info(f"Caught signal {signum}. Cancellation requested")
        self._cancellation_requested = True

    def _setup_signal_handling(self):
        logger.info("setting up signal handling")
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
