import json
import logging
import time
import xmlrpc.client

from odoo import http, release
from odoo.exceptions import AccessDenied
from odoo.http import request, Response

from ..models.mcp_model_access import BLOCKED_MODELS
from ..utils.auth import (
    get_client_ip, get_user_agent, check_ip_whitelist, check_rate_limit,
    check_auth_rate_limit, record_auth_failure,
)

_logger = logging.getLogger(__name__)

# Map XML-RPC method names to MCP operations
METHOD_OPERATION_MAP = {
    'search': 'read',
    'search_read': 'read',
    'search_count': 'read',
    'read': 'read',
    'read_group': 'read',
    'fields_get': 'fields',
    'name_search': 'read',
    'write': 'write',
    'create': 'create',
    'unlink': 'unlink',
    'copy': 'create',
}


def _xmlrpc_response(result):
    """Create an XML-RPC response."""
    body = xmlrpc.client.dumps((result,), methodresponse=True, allow_none=True)
    return Response(body, content_type='text/xml', status=200)


def _xmlrpc_fault(code, message):
    """Create an XML-RPC fault response."""
    body = xmlrpc.client.dumps(
        xmlrpc.client.Fault(code, message),
        allow_none=True,
    )
    return Response(body, content_type='text/xml', status=200)


def _parse_xmlrpc_request():
    """Parse an XML-RPC request body. Returns (method, params)."""
    try:
        data = request.httprequest.get_data()
        params, method = xmlrpc.client.loads(data)
        return method, params
    except Exception as e:
        _logger.error("Failed to parse XML-RPC request: %s", e)
        return None, None


class MCPXmlRpcController(http.Controller):
    """XML-RPC proxy endpoints for MCP Server."""

    def _check_mcp_enabled(self):
        """Check if MCP is enabled. Returns fault response or None."""
        ICP = request.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('mcp_server_ai.enabled', 'False')
        if enabled.lower() not in ('true', '1'):
            return _xmlrpc_fault(1, 'MCP Server is disabled.')
        return None

    def _log_activity(self, uid, model_name, operation, response_status,
                      method_name=None, record_ids=None, record_count=0,
                      request_data=None, error_message=None, duration_ms=0):
        """Log audit entry for XML-RPC requests."""
        try:
            ICP = request.env['ir.config_parameter'].sudo()
            logging_enabled = ICP.get_param('mcp_server_ai.logging_enabled', 'True')
            if logging_enabled.lower() not in ('true', '1'):
                return

            vals = {
                'user_id': uid or request.env.uid,
                'model_name': model_name or '',
                'operation': operation,
                'method_name': method_name,
                'record_ids': json.dumps(record_ids) if record_ids else None,
                'record_count': record_count,
                'request_data': request_data,
                'response_status': response_status,
                'error_message': error_message,
                'ip_address': get_client_ip(request),
                'user_agent': get_user_agent(request),
                'duration_ms': duration_ms,
                'endpoint_type': 'xmlrpc',
            }
            request.env['mcp.audit.log'].log_request(vals)
        except Exception as e:
            _logger.error("Failed to log MCP XML-RPC activity: %s", e)

    @http.route('/mcp/xmlrpc/2/common', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def xmlrpc_common(self, **kwargs):
        """XML-RPC common endpoint: version + authenticate."""
        err = self._check_mcp_enabled()
        if err:
            return err

        method, params = _parse_xmlrpc_request()
        if method is None:
            return _xmlrpc_fault(1, 'Invalid XML-RPC request.')

        if method == 'version':
            result = {
                'server_version': release.version,
                'server_version_info': release.version_info,
                'server_serie': release.serie,
                'protocol_version': 1,
                'mcp_version': '19.0.1.0.0',
            }
            return _xmlrpc_response(result)

        elif method == 'authenticate':
            if len(params) < 3:
                return _xmlrpc_fault(1, 'authenticate requires (db, login, password[, user_agent_env])')

            db = params[0]
            login = params[1]
            password = params[2]

            # Check IP whitelist
            ICP = request.env['ir.config_parameter'].sudo()
            allowed_ips = ICP.get_param('mcp_server_ai.allowed_ips', '')
            if not check_ip_whitelist(request, allowed_ips):
                return _xmlrpc_fault(2, f"IP {get_client_ip(request)} not whitelisted.")

            # Pre-auth brute force protection
            client_ip = get_client_ip(request)
            allowed, retry_after = check_auth_rate_limit(client_ip)
            if not allowed:
                return _xmlrpc_fault(429, f'Too many failed authentication attempts. Retry after {retry_after}s.')

            try:
                # Odoo 19 authenticate() API: (credential_dict, user_agent_env) -> auth_info dict
                auth_info = request.env['res.users'].authenticate(
                    {'type': 'password', 'login': login, 'password': password},
                    {'interactive': False},
                )
                uid = auth_info.get('uid') if isinstance(auth_info, dict) else auth_info
                if not uid:
                    raise AccessDenied("Authentication failed.")
                self._log_activity(uid, '', 'auth', 'success', method_name='authenticate')
                return _xmlrpc_response(uid)
            except AccessDenied:
                record_auth_failure(client_ip)
                self._log_activity(None, '', 'auth', 'denied', method_name='authenticate',
                                   error_message='Invalid credentials')
                return _xmlrpc_response(False)
            except Exception as e:
                return _xmlrpc_fault(1, str(e))

        else:
            return _xmlrpc_fault(1, f"Unknown method '{method}'.")

    @http.route('/mcp/xmlrpc/2/object', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def xmlrpc_object(self, **kwargs):
        """XML-RPC object endpoint: execute_kw with MCP permission checks."""
        start = time.time()

        err = self._check_mcp_enabled()
        if err:
            return err

        method, params = _parse_xmlrpc_request()
        if method is None:
            return _xmlrpc_fault(1, 'Invalid XML-RPC request.')

        if method != 'execute_kw':
            return _xmlrpc_fault(1, f"Only 'execute_kw' is supported. Got '{method}'.")

        # execute_kw params: (db, uid, password, model, method, args, kwargs)
        if len(params) < 6:
            return _xmlrpc_fault(1, 'execute_kw requires at least 6 parameters: db, uid, password, model, method, args')

        db = params[0]
        uid = params[1]
        password = params[2]
        model_name = params[3]
        rpc_method = params[4]
        rpc_args = params[5] if len(params) > 5 else []
        rpc_kwargs = params[6] if len(params) > 6 else {}

        # Pre-auth brute force protection
        client_ip = get_client_ip(request)
        allowed, retry_after = check_auth_rate_limit(client_ip)
        if not allowed:
            return _xmlrpc_fault(429, f'Too many failed authentication attempts. Retry after {retry_after}s.')

        # Authenticate: try API key first, then password
        try:
            auth_uid = request.env['res.users.apikeys']._check_credentials(
                scope='rpc', key=password
            )
            if not auth_uid:
                # API key failed, try password auth via Odoo 19 API
                user_record = request.env['res.users'].sudo().browse(uid)
                if not user_record.exists():
                    raise AccessDenied("User not found.")
                auth_info = request.env['res.users'].authenticate(
                    {'type': 'password', 'login': user_record.login, 'password': password},
                    {'interactive': False},
                )
                auth_uid = auth_info.get('uid') if isinstance(auth_info, dict) else auth_info

            if not auth_uid or auth_uid != uid:
                raise AccessDenied('UID mismatch or authentication failed.')

        except AccessDenied:
            record_auth_failure(client_ip)
            self._log_activity(uid, model_name, 'auth', 'denied',
                               method_name=rpc_method, error_message='Authentication failed')
            return _xmlrpc_fault(2, 'Authentication failed.')
        except Exception as e:
            return _xmlrpc_fault(1, f'Authentication error: {e}')

        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists() or not user.active:
            return _xmlrpc_fault(2, 'User account is disabled.')

        # Check IP whitelist
        ICP = request.env['ir.config_parameter'].sudo()
        allowed_ips = ICP.get_param('mcp_server_ai.allowed_ips', '')
        if not check_ip_whitelist(request, allowed_ips):
            return _xmlrpc_fault(2, f"IP {get_client_ip(request)} not whitelisted.")

        # Check rate limit
        rate_limit = int(ICP.get_param('mcp_server_ai.rate_limit', '10'))
        allowed, retry_after = check_rate_limit(uid, rate_limit)
        if not allowed:
            return _xmlrpc_fault(429, f'Rate limit exceeded. Retry after {retry_after}s.')

        # Check if model is blocked
        if model_name in BLOCKED_MODELS:
            self._log_activity(uid, model_name, 'call', 'denied',
                               method_name=rpc_method, error_message='Blocked model')
            return _xmlrpc_fault(3, f"Model '{model_name}' is blocked for security.")

        # Check YOLO mode
        yolo_mode = ICP.get_param('mcp_server_ai.yolo_mode', 'disabled')
        operation = METHOD_OPERATION_MAP.get(rpc_method, 'call')

        if yolo_mode == 'disabled':
            # Check MCP model access
            access = request.env['mcp.model.access'].get_access_for_model(model_name, user)
            if not access:
                self._log_activity(uid, model_name, operation, 'denied',
                                   method_name=rpc_method,
                                   error_message='Model not exposed via MCP')
                return _xmlrpc_fault(3, f"Model '{model_name}' is not exposed via MCP.")

            if not access.check_operation(operation):
                self._log_activity(uid, model_name, operation, 'denied',
                                   method_name=rpc_method,
                                   error_message=f'Operation {operation} denied')
                return _xmlrpc_fault(3, f"Operation '{rpc_method}' not allowed on '{model_name}'.")

        elif yolo_mode == 'read_only' and operation not in ('read', 'fields'):
            self._log_activity(uid, model_name, operation, 'denied',
                               method_name=rpc_method,
                               error_message='YOLO read_only: writes blocked')
            return _xmlrpc_fault(3, 'YOLO read_only mode: write operations blocked.')

        # Block dangerous methods
        blocked_rpc_methods = {
            'sudo', 'with_user', 'with_context', 'with_env', 'with_company',
            'copy', 'toggle_active', 'export_data', 'load', 'message_post',
            'mapped', 'filtered', 'sorted', 'action_archive', 'action_unarchive',
            'action_reset_password', 'flush_model', 'flush_recordset', 'browse',
            'search_fetch', 'fetch',
        }
        if rpc_method.startswith('_') or rpc_method in blocked_rpc_methods:
            self._log_activity(uid, model_name, 'call', 'denied',
                               method_name=rpc_method,
                               error_message=f'Blocked method: {rpc_method}')
            return _xmlrpc_fault(3, f"Method '{rpc_method}' is not allowed via MCP XML-RPC.")

        # Execute the actual RPC call
        try:
            model_obj = request.env[model_name].with_user(uid)
            method_func = getattr(model_obj, rpc_method, None)
            if method_func is None or not callable(method_func):
                return _xmlrpc_fault(1, f"Method '{rpc_method}' not found on model '{model_name}'.")
            result = method_func(*rpc_args, **rpc_kwargs)

            # Convert recordsets to serializable format
            if hasattr(result, 'ids'):
                result = result.ids

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, operation, 'success',
                method_name=rpc_method, duration_ms=duration,
            )
            return _xmlrpc_response(result)

        except Exception as e:
            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, operation, 'error',
                method_name=rpc_method, error_message=str(e),
                duration_ms=duration,
            )
            return _xmlrpc_fault(1, str(e))
