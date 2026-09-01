import logging

logger = logging.getLogger(__name__)


def log_request(method: str, path: str) -> None:
    """Log a request when used by an integration or middleware adapter."""
    logger.info("%s %s", method, path)


def log_error(error: str, method: str, path: str) -> None:
    """Log a request-scoped error when used by an integration or middleware adapter."""
    logger.error("Error in %s %s: %s", method, path, error)
