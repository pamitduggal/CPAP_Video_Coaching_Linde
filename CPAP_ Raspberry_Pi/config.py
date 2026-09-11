import os
import ipaddress
import logging

logging.basicConfig(level=logging.INFO)

def get_env_var(name: str, default: str | None = None) -> str:
    value = os.getenv(name)
    if value is None:
        if default is not None:
            logging.info(f"Environment variable {name} not set, using default.")
            return default
        raise EnvironmentError(f"Required environment variable {name} not set.")
    return value

def validate_ip_or_hostname(url: str) -> str:
    if "://" in url:
        protocol, rest = url.split("://", 1)
    else:
        protocol = "http"
        rest = url
    host = rest.split("/", 1)[0]
    try:
        host_only = host.split(":")[0]
        ipaddress.ip_address(host_only)
        logging.info(f"Validated IP address {host_only} for URL.")
    except ValueError:
        if not host:
            raise ValueError(f"Invalid URL: {url}")
        logging.info(f"Using hostname {host} for URL.")
    return f"{protocol}://{rest}"

def get_backend_url() -> str:
    raw = get_env_var("BACKEND_API_URL", "http://127.0.0.1/api/data")
    return validate_ip_or_hostname(raw)

def get_dashboard_url() -> str:
    raw = get_env_var("DASHBOARD_URL", "http://127.0.0.1:80")
    return validate_ip_or_hostname(raw)

def get_backend_api_key() -> str:
    return get_env_var("BACKEND_API_KEY", "")

def get_server_host() -> str:
    return get_env_var("SERVER_HOST", "0.0.0.0")

def get_server_port() -> int:
    return int(get_env_var("SERVER_PORT", "8000"))

def get_sync_interval_minutes() -> int:
    return int(get_env_var("SYNC_INTERVAL_MINUTES", "30"))
