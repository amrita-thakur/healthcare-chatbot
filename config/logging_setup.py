import configparser
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import os


class LoggingConfig:
    def __init__(self, config_file="config/logging_config.ini"):
        """
        Initializes the LoggingConfig class and sets up the logging configuration.

        Args:
            config_file (str): Path to the .ini configuration file for logging.
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(self.config_file)

    def ensure_directories(self, folder_name: str):
        """
        Ensures that the log directories exist, creating them if necessary.

        Args:
            folder_name (str): The name of the folder to create under the logs directory.
        """
        # log_directory = os.path.join(os.path.dirname(__file__), 'logs', folder_name)
        log_directory = os.path.join("logs", folder_name)
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)

    def setup_logging(self, logger_name: str, folder_name: str, deploy_env: str):
        """
        Sets up a logger that stores the application logs into a file.

        Args:
            logger_name (str): The name of the logger.
            folder_name (str): The folder name to use for the logs.
            deploy_env (str): The deployment environment ('dev' or 'prod').

        Returns:
            logger (logging.Logger): A configured logging object.
        """
        self.ensure_directories(folder_name)

        # Get the log file path template from the config
        log_file_path_template = self.config.get("log_config", "log_file_path")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{folder_name}_{timestamp}"
        log_file_path = log_file_path_template.format(
            folder_name=folder_name, file_name=file_name
        )

        # Determine log level based on the deployment environment
        log_level = "DEBUG" if deploy_env == "dev" else "INFO"
        log_format = self.config.get("log_config", "log_format")

        # Retrieve time rotation settings
        interval = int(self.config.get("time_rotation", "interval"))
        backup_count = int(self.config.get("time_rotation", "backup_count"))

        # Create and configure the logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)

        # Set up the file handler with timed rotation
        file_handler = TimedRotatingFileHandler(
            log_file_path, when="midnight", interval=interval, backupCount=backup_count
        )
        formatter = logging.Formatter(log_format)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger


# Example usage
# if __name__ == "__main__":
#     log_config = LoggingConfig()
#     logger = log_config.setup_logging(
#         logger_name="my_logger", folder_name="mongodb_client", deploy_env="dev"
#     )
#     logger.info("Logging setup complete.")
