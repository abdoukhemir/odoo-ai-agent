import base64
import ipaddress
import logging
import re
import time
import threading

from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

# Thread-safe rate limiter storage: {user_id: [(timestamp, ...),]}
_rate_limit_store = {}
_rate_limit_lock = threading.Lock()

# Thread-safe auth failure tracking for brute force protection
_auth_fail_store = {}
_auth_fail_lock = threading.Lock()


def authenticate_request(request):
    """
    Authenticate an MCP API request using Bearer token or Basic auth.
    Returns (uid, user_record, db_name) or raises AccessDenied.
    """
    auth_header = request.httprequest.headers.get('Authorization', '')

    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:].strip()
        return _authenticate_api_key(request, api_key)
    elif auth_header.startswith('Basic '):
        return _authenticate_basic(request, auth_header[6:].strip())
    else:
        raise AccessDenied("Missing or invalid Authorization header.")


def _authenticate_api_key(request, api_key):
    """Authenticate using Odoo API key."""
    if not api_key:
        raise AccessDenied("Empty API key.")
    try:
        uid = request.env['res.users.apikeys']._check_credentials(
            scope='rpc', key=api_key
        )
        if not uid:
            raise AccessDenied("Invalid API key.")
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or not user.active:
            raise AccessDenied("User account is disabled.")
        db_name = request.env.cr.dbname
        return uid, user, db_name
    except AccessDenied:
        raise
    except Exception as e:
        _logger.warning("MCP API key auth failed: %s", e)
        raise AccessDenied("Invalid API key.")


def _authenticate_basic(request, encoded):
    """Authenticate using HTTP Basic auth (login:password) - Odoo 19 API."""
    try:
        decoded = base64.b64decode(encoded).decode('utf-8')
        login, password = decoded.split(':', 1)
    except Exception:
        raise AccessDenied("Invalid Basic auth encoding.")

    try:
        db_name = request.env.cr.dbname
        # Odoo 19 authenticate() takes (credential_dict, user_agent_env)
        # Returns auth_info dict with 'uid' key
        auth_info = request.env['res.users'].authenticate(
            {'type': 'password', 'login': login, 'password': password},
            {'interactive': False},
        )
        uid = auth_info.get('uid') if isinstance(auth_info, dict) else auth_info
        if not uid:
            raise AccessDenied("Invalid credentials.")
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or not user.active:
            raise AccessDenied("User account is disabled.")
        return uid, user, db_name
    except AccessDenied:
        raise
    except Exception as e:
        _logger.warning("MCP Basic auth failed: %s", e)
        raise AccessDenied("Invalid credentials.")


def check_rate_limit(user_id, max_requests_per_minute):
    """
    Check if user has exceeded rate limit.
    Returns (allowed: bool, retry_after_seconds: int).
    Thread-safe implementation.
    """
    if max_requests_per_minute <= 0:
        return True, 0

    now = time.time()
    window_start = now - 60

    with _rate_limit_lock:
        if user_id not in _rate_limit_store:
            _rate_limit_store[user_id] = []

        # Clean old entries outside the window
        _rate_limit_store[user_id] = [
            t for t in _rate_limit_store[user_id] if t > window_start
        ]

        if len(_rate_limit_store[user_id]) >= max_requests_per_minute:
            oldest = _rate_limit_store[user_id][0]
            retry_after = int(oldest + 60 - now) + 1
            return False, max(retry_after, 1)

        _rate_limit_store[user_id].append(now)
        return True, 0


def check_auth_rate_limit(client_ip, max_attempts=20, window=300):
    """Rate limit authentication attempts by IP. Returns (allowed, retry_after)."""
    if not client_ip:
        return True, 0
    now = time.time()
    window_start = now - window
    with _auth_fail_lock:
        if client_ip not in _auth_fail_store:
            _auth_fail_store[client_ip] = []
        _auth_fail_store[client_ip] = [t for t in _auth_fail_store[client_ip] if t > window_start]
        if len(_auth_fail_store[client_ip]) >= max_attempts:
            oldest = _auth_fail_store[client_ip][0]
            retry_after = int(oldest + window - now) + 1
            return False, max(retry_after, 1)
        return True, 0


def record_auth_failure(client_ip):
    """Record a failed authentication attempt."""
    if not client_ip:
        return
    with _auth_fail_lock:
        if client_ip not in _auth_fail_store:
            _auth_fail_store[client_ip] = []
        _auth_fail_store[client_ip].append(time.time())


def check_ip_whitelist(request, allowed_ips_str):
    """
    Check if client IP is in the whitelist.
    Returns True if whitelist is empty or IP is whitelisted.
    """
    if not allowed_ips_str or not allowed_ips_str.strip():
        return True

    client_ip = get_client_ip(request)
    allowed_ips = [
        ip.strip() for ip in re.split(r'[,\n]+', allowed_ips_str.strip()) if ip.strip()
    ]

    if not allowed_ips:
        return True

    return client_ip in allowed_ips


def _is_trusted_proxy(ip_str):
    """Check if IP is a known trusted proxy (loopback or private network)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_loopback or ip.is_private
    except (ValueError, TypeError):
        return False


def get_client_ip(request):
    """Get client IP address from request, with proxy trust validation."""
    remote_addr = request.httprequest.remote_addr or '0.0.0.0'
    # Only trust forwarded headers if request comes from a trusted proxy
    if _is_trusted_proxy(remote_addr):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        real_ip = request.httprequest.headers.get('X-Real-IP', '')
        if real_ip:
            return real_ip.strip()
    return remote_addr


def get_user_agent(request):
    """Get user agent string from request."""
    return request.httprequest.headers.get('User-Agent', '')[:500]
