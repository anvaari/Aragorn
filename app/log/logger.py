import logging
from rich.console import Console
from core.config import app_settings
import sys

log_level = app_settings.log_level.upper()

rprint = Console(soft_wrap=True).print
class MyRichLogHandler(logging.StreamHandler):
    LEVEL_MAPPING = {
        logging.DEBUG: "[blue]DEBUG[/blue]",
        logging.INFO: "[green]INFO[/green]",
        logging.WARNING: "[yellow]WARNING[/yellow]",
        logging.ERROR: "[red]ERROR[/red]",
        logging.CRITICAL: "[bold red]CRITICAL[/bold red]",
    }
    def emit(self, record):
        """
        Outputs a formatted log record to the console using rich formatting.
        
        Overrides the base handler to print log messages with enhanced styling and clickable file links.
        """
        msg = self.format(record)
        rprint(msg)

    def format(self, record):
        """
        Formats a log record with colored level names and clickable file links.
        
        Replaces the log level name with a colored label and formats the filename and line number as a clickable link using rich markup before delegating to the base formatter.
        """
        levelname = self.LEVEL_MAPPING.get(record.levelno, str(record.levelno))
        
        file_name_line = (
            f"[link file://{record.filename}#{record.lineno}]"
            f"{record.filename}:{record.lineno}"
            f"[/link file://{record.filename}#{record.lineno}]")
        
        record.levelname = levelname
        record.filename = file_name_line
        return super().format(record)

_my_log_format = ("%(asctime)s - %(levelname)s "
                   "in %(filename)s "
                   "at Line %(lineno)d: "
                   "%(message)s")

def get_app_logger(logger_name:str) -> logging.Logger :
    """
    Creates and configures a logger with rich-formatted console output.
    
    The returned logger uses a custom handler that displays log messages with colored levels,
    timestamps, and clickable file links in the console. The logger level is set to DEBUG.
    
    Args:
        logger_name: The name of the logger to create or retrieve.
    
    Returns:
        A logger instance configured with rich formatting for enhanced console output.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    rich_log_handler = MyRichLogHandler(sys.stdout)
    log_formatter = logging.Formatter(_my_log_format)
    rich_log_handler.setFormatter(log_formatter)
    logger.addHandler(rich_log_handler)
    return logger
