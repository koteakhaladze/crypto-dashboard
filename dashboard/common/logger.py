import logging
from logging import Logger as LoggingLogger


class Logger:
    def __init__(self,
                 name: str,
                 log_file: str,
                 log_level: int = logging.DEBUG,
                 file_level: int = logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        self._add_console_handler(log_level)
        self._add_file_handler(log_file, file_level)

    def _add_console_handler(self, level: int):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(console_handler)

    def _add_file_handler(self, log_file: str, level: int):
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(file_handler)

    @staticmethod
    def _get_formatter() -> logging.Formatter:
        return logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    def get_logger(self) -> LoggingLogger:
        return self.logger
