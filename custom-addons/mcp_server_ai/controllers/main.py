import json
import logging
import time

from odoo import http, fields as odoo_fields, release
from odoo.exceptions import AccessDenied, AccessError, ValidationError
from odoo.http import request, Response

from ..models.mcp_model_access import BLOCKED_MODELS
from ..utils.auth import (
    authenticate_request, check_rate_limit, check_ip_whitelist,
    get_client_ip, get_user_agent, check_auth_rate_limit, record_auth_failure,
)
from ..utils.cache import cache_get, cache_set, get_cache_key, cache_invalidate_model
from ..utils.formatter import format_for_llm, get_smart_default_fields, generate_summary

_logger = logging.getLogger(__name__)


def _json_response(data, status=200, headers=None):
    """Create a JSON response."""
    body = json.dumps(data, default=str, ensure_ascii=False)
    resp_headers = {'Content-Type': 'application/json; charset=utf-8'}
    if headers:
        resp_headers.update(headers)
    return Response(body, status=status, headers=resp_headers)


def _error_response(code, message, http_status=400, details=None):
    """Create a standard error response."""
    return _json_response({
        'success': False,
        'error': {
            'code': code,
            'message': message,
            'details': details,
        }
    }, status=http_status)


def _get_json_body():
    """Parse JSON request body."""
    try:
        data = request.httprequest.get_data(as_text=True)
        if not data:
            return {}
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


class MCPController(http.Controller):
    """REST API controller for MCP Server."""

    # ------------------------------------------------------------------
    # Middleware helpers
    # ------------------------------------------------------------------

    def _check_mcp_enabled(self):
        """Check if MCP server is enabled. Returns error response or None."""
        ICP = request.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('mcp_server_ai.enabled', 'False')
        if enabled.lower() not in ('true', '1'):
            return _error_response('MCP_DISABLED', 'MCP Server is disabled.', 503)
        return None

    def _authenticate(self):
        """Authenticate request. Returns (uid, user, db) or raises."""
        return authenticate_request(request)

    def _check_ip(self):
        """Check IP whitelist. Returns error response or None."""
        ICP = request.env['ir.config_parameter'].sudo()
        allowed_ips = ICP.get_param('mcp_server_ai.allowed_ips', '')
        if not check_ip_whitelist(request, allowed_ips):
            return _error_response(
                'IP_BLOCKED',
                f"IP address {get_client_ip(request)} is not whitelisted.",
                403,
            )
        return None

    def _check_rate(self, uid):
        """Check rate limit. Returns error response or None."""
        ICP = request.env['ir.config_parameter'].sudo()
        rate_limit = int(ICP.get_param('mcp_server_ai.rate_limit', '10'))
        allowed, retry_after = check_rate_limit(uid, rate_limit)
        if not allowed:
            return _error_response(
                'RATE_LIMITED',
                f'Rate limit exceeded. Retry after {retry_after} seconds.',
                429,
                details={'retry_after': retry_after},
            )
        return None

    def _get_model_access(self, model_name, user):
        """Get MCP model access. Returns (access, error_response)."""
        ICP = request.env['ir.config_parameter'].sudo()
        yolo_mode = ICP.get_param('mcp_server_ai.yolo_mode', 'disabled')

        if model_name in BLOCKED_MODELS:
            return None, _error_response(
                'BLOCKED_MODEL',
                f"Model '{model_name}' is blocked for security reasons.",
                403,
            )

        if yolo_mode in ('read_only', 'full'):
            return None, None  # YOLO mode bypasses access checks

        access = request.env['mcp.model.access'].get_access_for_model(model_name, user)
        if not access:
            return None, _error_response(
                'MODEL_NOT_FOUND',
                f"Model '{model_name}' is not exposed via MCP.",
                404,
            )
        return access, None

    def _check_operation(self, access, operation, model_name):
        """Check if operation is allowed. Returns error response or None."""
        ICP = request.env['ir.config_parameter'].sudo()
        yolo_mode = ICP.get_param('mcp_server_ai.yolo_mode', 'disabled')

        if yolo_mode == 'full':
            return None
        if yolo_mode == 'read_only' and operation in ('read', 'search', 'browse', 'count', 'fields'):
            return None
        if yolo_mode == 'read_only':
            return _error_response(
                'OPERATION_DENIED',
                f"YOLO read_only mode: write operations are blocked.",
                403,
            )

        if access and not access.check_operation(operation):
            return _error_response(
                'OPERATION_DENIED',
                f"Operation '{operation}' is not allowed on model '{model_name}'.",
                403,
            )
        return None

    def _run_with_guard(self, callback, auth_required=True):
        """Run endpoint callback with all middleware checks."""
        start_time = time.time()
        uid = None
        user = None

        try:
            # Check MCP enabled
            err = self._check_mcp_enabled()
            if err:
                return err

            if auth_required:
                # Check IP
                err = self._check_ip()
                if err:
                    return err

                # Pre-auth brute force protection
                client_ip = get_client_ip(request)
                allowed, retry_after = check_auth_rate_limit(client_ip)
                if not allowed:
                    return _error_response(
                        'RATE_LIMITED',
                        f'Too many failed authentication attempts. Retry after {retry_after} seconds.',
                        429,
                        details={'retry_after': retry_after},
                    )

                # Authenticate
                uid, user, db_name = self._authenticate()

                # Check MCP group membership
                if not (user.has_group('mcp_server_ai.group_mcp_user') or user.has_group('mcp_server_ai.group_mcp_admin')):
                    return _error_response(
                        'ACCESS_DENIED',
                        'User is not a member of MCP User or MCP Administrator group.',
                        403,
                    )

                # Check rate limit
                err = self._check_rate(uid)
                if err:
                    return err

            return callback(uid, user)

        except AccessDenied as e:
            record_auth_failure(get_client_ip(request))
            return _error_response('AUTH_INVALID', str(e) or 'Invalid credentials.', 401)
        except (AccessError, ValidationError) as e:
            return _error_response('VALIDATION_ERROR', str(e), 400)
        except Exception as e:
            _logger.exception("MCP internal error")
            return _error_response('INTERNAL_ERROR', 'An internal error occurred.', 500)

    def _log_activity(self, uid, model_name, operation, response_status,
                      record_ids=None, record_count=0, request_data=None,
                      error_message=None, method_name=None, duration_ms=0,
                      endpoint_type='rest'):
        """Log an audit entry if logging is enabled."""
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
                'endpoint_type': endpoint_type,
            }
            request.env['mcp.audit.log'].log_request(vals)
        except Exception as e:
            _logger.error("Failed to log MCP activity: %s", e)

    def _get_max_records(self):
        """Get max records per request from settings."""
        ICP = request.env['ir.config_parameter'].sudo()
        return int(ICP.get_param('mcp_server_ai.max_records_per_request', '1000'))

    def _validate_domain(self, domain):
        """Validate domain filter structure. Returns error response or None."""
        if not isinstance(domain, list):
            return _error_response('VALIDATION_ERROR', 'Domain must be a list.', 400)

        MAX_DOMAIN_CLAUSES = 50
        clause_count = 0

        for item in domain:
            if isinstance(item, str):
                # Operators: '&', '|', '!'
                if item not in ('&', '|', '!'):
                    return _error_response(
                        'VALIDATION_ERROR',
                        f"Invalid domain operator: '{item}'. Allowed: '&', '|', '!'",
                        400,
                    )
            elif isinstance(item, (list, tuple)):
                if len(item) != 3:
                    return _error_response(
                        'VALIDATION_ERROR',
                        f'Domain clause must have exactly 3 elements [field, operator, value], got {len(item)}.',
                        400,
                    )
                field_name, operator, value = item
                if not isinstance(field_name, str):
                    return _error_response('VALIDATION_ERROR', 'Domain field name must be a string.', 400)
                valid_operators = ['=', '!=', '>', '>=', '<', '<=', 'like', 'ilike', 'not like',
                                 'not ilike', '=like', '=ilike', 'in', 'not in', 'child_of',
                                 'parent_of', '=?', 'any', 'not any']
                if operator not in valid_operators:
                    return _error_response(
                        'VALIDATION_ERROR',
                        f"Invalid domain operator: '{operator}'.",
                        400,
                    )
                clause_count += 1
            else:
                return _error_response('VALIDATION_ERROR', 'Invalid domain element type.', 400)

        if clause_count > MAX_DOMAIN_CLAUSES:
            return _error_response(
                'VALIDATION_ERROR',
                f'Domain exceeds maximum of {MAX_DOMAIN_CLAUSES} clauses.',
                400,
            )
        return None

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @http.route('/mcp/api/v1/health', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def health(self, **kwargs):
        """Health check endpoint - no auth required."""
        ICP = request.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('mcp_server_ai.enabled', 'False')
        return _json_response({
            'status': 'ok',
            'timestamp': odoo_fields.Datetime.now().isoformat() + 'Z',
            'module_version': '19.0.1.0.0',
            'mcp_enabled': enabled.lower() in ('true', '1'),
        })

    @http.route('/mcp/api/v1/system/info', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def system_info(self, **kwargs):
        """System information endpoint."""
        def _handler(uid, user):
            start = time.time()
            ICP = request.env['ir.config_parameter'].sudo()
            db_name = request.env.cr.dbname

            access_count = request.env['mcp.model.access'].sudo().search_count(
                [('active', '=', True)]
            )

            data = {
                'odoo_version': release.version,
                'server_version_info': release.version_info,
                'database': db_name,
                'module_version': '19.0.1.0.0',
                'exposed_models_count': access_count,
                'server_time': odoo_fields.Datetime.now().isoformat() + 'Z',
            }
            duration = (time.time() - start) * 1000
            self._log_activity(uid, '', 'system', 'success', duration_ms=duration)
            return _json_response({'success': True, 'data': data})

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/auth/validate', type='http', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def auth_validate(self, **kwargs):
        """Validate API key and return user info."""
        def _handler(uid, user):
            start = time.time()
            data = {
                'user_id': user.id,
                'login': user.login,
                'name': user.name,
                'email': user.email,
                'company': {
                    'id': user.company_id.id,
                    'name': user.company_id.name,
                } if user.company_id else None,
                'groups': [
                    {'id': g.id, 'name': g.full_name}
                    for g in user.group_ids[:20]
                ],
                'is_mcp_admin': user.has_group('mcp_server_ai.group_mcp_admin'),
                'is_mcp_user': user.has_group('mcp_server_ai.group_mcp_user'),
            }
            duration = (time.time() - start) * 1000
            self._log_activity(uid, '', 'auth', 'success', duration_ms=duration)
            return _json_response({'success': True, 'data': data})

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def list_models(self, **kwargs):
        """List all MCP-exposed models."""
        def _handler(uid, user):
            start = time.time()
            ICP = request.env['ir.config_parameter'].sudo()
            yolo_mode = ICP.get_param('mcp_server_ai.yolo_mode', 'disabled')

            if yolo_mode in ('read_only', 'full'):
                # In YOLO mode, list all accessible models
                models = request.env['ir.model'].sudo().search([
                    ('model', 'not in', BLOCKED_MODELS),
                    ('transient', '=', False),
                ])
                data = [{
                    'model': m.model,
                    'name': m.name,
                    'read': True,
                    'write': yolo_mode == 'full',
                    'create': yolo_mode == 'full',
                    'delete': yolo_mode == 'full',
                    'yolo_mode': True,
                } for m in models[:100]]
            else:
                access_records = request.env['mcp.model.access'].sudo().search([
                    ('active', '=', True),
                ])
                data = []
                for acc in access_records:
                    if acc.group_ids and not acc.check_user_groups(user):
                        continue
                    data.append({
                        'model': acc.model_name,
                        'name': acc.model_id.name,
                        'read': acc.read_access,
                        'write': acc.write_access,
                        'create': acc.create_access,
                        'delete': acc.delete_access,
                        'cache_ttl': acc.cache_ttl,
                    })

            duration = (time.time() - start) * 1000
            self._log_activity(uid, '', 'read', 'success', duration_ms=duration)
            return _json_response({'success': True, 'data': data, 'count': len(data)})

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/fields', type='http',
                auth='none', methods=['GET'], csrf=False, cors='*')
    def model_fields(self, model, **kwargs):
        """Get field metadata for a model."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'fields', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'fields', model_name)
            if err:
                return err

            try:
                model_obj = request.env[model_name].sudo()
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            fields_data = model_obj.fields_get(attributes=[
                'string', 'type', 'required', 'readonly', 'selection',
                'relation', 'help', 'store',
            ])

            # Filter by allowed fields if configured
            if access:
                allowed = access.get_allowed_fields_list()
                if allowed:
                    fields_data = {k: v for k, v in fields_data.items() if k in allowed or k == 'id'}

            duration = (time.time() - start) * 1000
            self._log_activity(uid, model_name, 'fields', 'success', duration_ms=duration)
            return _json_response({'success': True, 'data': fields_data})

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/search', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def search_records(self, model, **kwargs):
        """Search records with domain filters."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'search', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'search', model_name)
            if err:
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            domain = body.get('domain', [])
            err = self._validate_domain(domain)
            if err:
                return err
            fields_list = body.get('fields')
            limit = min(body.get('limit', 80), self._get_max_records())
            offset = body.get('offset', 0)
            order = body.get('order', '')
            raw_html = body.get('raw_html', False)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            # Smart field defaults
            if not fields_list:
                fields_list = get_smart_default_fields(model_obj)
            elif fields_list == ['__all__']:
                fields_list = None  # Odoo returns all if None

            # Filter by allowed fields
            if access and fields_list:
                fields_list = access.check_field_access(fields_list)

            # Check cache
            ICP = request.env['ir.config_parameter'].sudo()
            cache_enabled = ICP.get_param('mcp_server_ai.cache_enabled', 'False').lower() in ('true', '1')
            cache_ttl = 0
            if cache_enabled and access and access.cache_ttl > 0:
                cache_ttl = access.cache_ttl
            elif cache_enabled:
                cache_ttl = int(ICP.get_param('mcp_server_ai.default_cache_ttl', '300'))

            cache_key = None
            cache_hit = False
            if cache_ttl > 0:
                cache_key = get_cache_key(uid, model_name, 'search', {
                    'domain': domain, 'fields': fields_list,
                    'limit': limit, 'offset': offset, 'order': order,
                })
                cache_hit, cached_data = cache_get(cache_key)
                if cache_hit:
                    duration = (time.time() - start) * 1000
                    self._log_activity(uid, model_name, 'search', 'success', duration_ms=duration)
                    return _json_response(cached_data, headers={'X-MCP-Cache': 'HIT', 'X-MCP-Cache-TTL': str(cache_ttl)})

            total = model_obj.search_count(domain)
            records = model_obj.search_read(domain, fields=fields_list, limit=limit, offset=offset, order=order)

            formatted = format_for_llm(records, model_obj, fields_list, raw_html)

            result = {
                'success': True,
                'data': formatted,
                'count': len(formatted),
                'total': total,
            }

            if cache_ttl > 0 and cache_key:
                cache_set(cache_key, result, cache_ttl)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'search', 'success',
                record_count=len(formatted), request_data=body, duration_ms=duration,
            )
            headers = {'X-MCP-Cache': 'MISS'} if cache_ttl > 0 else {}
            if cache_ttl > 0:
                headers['X-MCP-Cache-TTL'] = str(cache_ttl)
            return _json_response(result, headers=headers)

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/read', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def read_records(self, model, **kwargs):
        """Read specific records by IDs."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'read', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'read', model_name)
            if err:
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            record_ids = body.get('ids', [])
            if not record_ids or not isinstance(record_ids, list):
                return _error_response('VALIDATION_ERROR', '"ids" must be a non-empty list of integers.', 400)

            fields_list = body.get('fields')
            raw_html = body.get('raw_html', False)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            if not fields_list:
                fields_list = get_smart_default_fields(model_obj)
            elif fields_list == ['__all__']:
                fields_list = None

            if access and fields_list:
                fields_list = access.check_field_access(fields_list)

            records = model_obj.browse(record_ids).read(fields_list)
            formatted = format_for_llm(records, model_obj, fields_list, raw_html)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'read', 'success',
                record_ids=record_ids, record_count=len(formatted),
                request_data=body, duration_ms=duration,
            )
            return _json_response({
                'success': True,
                'data': formatted,
                'count': len(formatted),
            })

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/browse', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def browse_records(self, model, **kwargs):
        """Browse records with pagination and optional summary."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'browse', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'browse', model_name)
            if err:
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            domain = body.get('domain', [])
            err = self._validate_domain(domain)
            if err:
                return err
            fields_list = body.get('fields')
            limit = min(body.get('limit', 20), self._get_max_records())
            offset = body.get('offset', 0)
            order = body.get('order', '')
            include_summary = body.get('summary', False)
            raw_html = body.get('raw_html', False)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            if not fields_list:
                fields_list = get_smart_default_fields(model_obj)
            elif fields_list == ['__all__']:
                fields_list = None

            if access and fields_list:
                fields_list = access.check_field_access(fields_list)

            total = model_obj.search_count(domain)
            records = model_obj.search_read(domain, fields=fields_list, limit=limit, offset=offset, order=order)
            formatted = format_for_llm(records, model_obj, fields_list, raw_html)

            result = {
                'success': True,
                'data': formatted,
                'pagination': {
                    'offset': offset,
                    'limit': limit,
                    'count': len(formatted),
                    'total': total,
                    'has_more': (offset + len(formatted)) < total,
                },
            }

            if include_summary:
                result['summary'] = generate_summary(formatted, total, offset, limit, model_name)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'browse', 'success',
                record_count=len(formatted), request_data=body, duration_ms=duration,
            )
            return _json_response(result)

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/count', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def count_records(self, model, **kwargs):
        """Count records matching a domain."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'count', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'count', model_name)
            if err:
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            domain = body.get('domain', [])
            err = self._validate_domain(domain)
            if err:
                return err

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            count = model_obj.search_count(domain)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'count', 'success',
                record_count=count, request_data=body, duration_ms=duration,
            )
            return _json_response({'success': True, 'data': {'count': count}})

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/create', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def create_record(self, model, **kwargs):
        """Create record(s)."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'create', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'create', model_name)
            if err:
                self._log_activity(uid, model_name, 'create', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            values = body.get('values', {})
            if not values:
                return _error_response('VALIDATION_ERROR', '"values" is required.', 400)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            if isinstance(values, list):
                records = model_obj.create(values)
                created_ids = records.ids
            else:
                record = model_obj.create(values)
                created_ids = [record.id]

            # Invalidate cache for this model
            cache_invalidate_model(model_name)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'create', 'success',
                record_ids=created_ids, record_count=len(created_ids),
                request_data=body, duration_ms=duration,
            )
            return _json_response({
                'success': True,
                'data': {'ids': created_ids},
                'count': len(created_ids),
            })

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/write', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def write_records(self, model, **kwargs):
        """Update record(s)."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'write', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'write', model_name)
            if err:
                self._log_activity(uid, model_name, 'write', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            record_ids = body.get('ids', [])
            values = body.get('values', {})

            if not record_ids or not isinstance(record_ids, list):
                return _error_response('VALIDATION_ERROR', '"ids" must be a non-empty list.', 400)
            if not values or not isinstance(values, dict):
                return _error_response('VALIDATION_ERROR', '"values" must be a non-empty dict.', 400)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            records = model_obj.browse(record_ids)
            if not records.exists():
                return _error_response('RECORD_NOT_FOUND', 'No records found with the given IDs.', 404)

            records.write(values)
            cache_invalidate_model(model_name)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'write', 'success',
                record_ids=record_ids, record_count=len(record_ids),
                request_data=body, duration_ms=duration,
            )
            return _json_response({
                'success': True,
                'data': {'updated': True, 'ids': record_ids},
            })

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/unlink', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def unlink_records(self, model, **kwargs):
        """Delete record(s)."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'unlink', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            err = self._check_operation(access, 'unlink', model_name)
            if err:
                self._log_activity(uid, model_name, 'unlink', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            record_ids = body.get('ids', [])
            if not record_ids or not isinstance(record_ids, list):
                return _error_response('VALIDATION_ERROR', '"ids" must be a non-empty list.', 400)

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            records = model_obj.browse(record_ids)
            if not records.exists():
                return _error_response('RECORD_NOT_FOUND', 'No records found with the given IDs.', 404)

            deleted_count = len(records)
            records.unlink()
            cache_invalidate_model(model_name)

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'unlink', 'success',
                record_ids=record_ids, record_count=deleted_count,
                request_data=body, duration_ms=duration,
            )
            return _json_response({
                'success': True,
                'data': {'deleted': True, 'count': deleted_count},
            })

        return self._run_with_guard(_handler)

    @http.route('/mcp/api/v1/models/<string:model>/call', type='http',
                auth='none', methods=['POST'], csrf=False, cors='*')
    def call_method(self, model, **kwargs):
        """Call a model method."""
        def _handler(uid, user):
            start = time.time()
            model_name = model.replace('-', '.')

            access, err = self._get_model_access(model_name, user)
            if err:
                self._log_activity(uid, model_name, 'call', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            # Check that model has at least read_access for call endpoint
            err = self._check_operation(access, 'read', model_name)
            if err:
                self._log_activity(uid, model_name, 'call', 'denied', duration_ms=(time.time() - start) * 1000)
                return err

            body = _get_json_body()
            if body is None:
                return _error_response('VALIDATION_ERROR', 'Invalid JSON body.', 400)

            method_name = body.get('method', '')
            args = body.get('args', [])
            kw = body.get('kwargs', {})
            record_ids = body.get('ids', [])

            if not method_name:
                return _error_response('VALIDATION_ERROR', '"method" is required.', 400)

            # Block dangerous methods
            blocked_methods = [
                # ORM write operations
                'unlink', 'write', 'create', 'copy', 'toggle_active',
                'action_archive', 'action_unarchive',
                # Privilege escalation
                'sudo', 'with_user', 'with_context', 'with_env', 'with_company',
                # Data export/import
                'export_data', 'load', 'import_data',
                # Email/messaging
                'message_post', 'message_subscribe', 'message_unsubscribe',
                # Recordset traversal (can access blocked models)
                'mapped', 'filtered', 'sorted', 'filtered_domain',
                # ORM internals
                'flush_model', 'flush_recordset', 'invalidate_model',
                'invalidate_recordset', 'browse',
                # User management
                'action_reset_password', 'action_deactivate',
                # New Odoo 17+ methods
                'search_fetch', 'fetch', 'web_read', 'web_search_read',
                # Aggregation that may leak restricted fields
                'read_group',
            ]
            if method_name.startswith('_') or method_name in blocked_methods:
                return _error_response(
                    'OPERATION_DENIED',
                    f"Method '{method_name}' is not allowed via MCP call endpoint.",
                    403,
                )

            try:
                model_obj = request.env[model_name].with_user(uid)
            except KeyError:
                return _error_response('MODEL_NOT_FOUND', f"Model '{model_name}' does not exist.", 404)

            if record_ids:
                target = model_obj.browse(record_ids)
            else:
                target = model_obj

            method = getattr(target, method_name, None)
            if method is None or not callable(method):
                return _error_response(
                    'VALIDATION_ERROR',
                    f"Method '{method_name}' does not exist on model '{model_name}'.",
                    400,
                )

            result = method(*args, **kw)

            # Try to serialize the result
            if hasattr(result, 'ids'):
                result = result.ids
            elif hasattr(result, 'read'):
                result = result.read()

            duration = (time.time() - start) * 1000
            self._log_activity(
                uid, model_name, 'call', 'success',
                method_name=method_name, record_ids=record_ids,
                request_data=body, duration_ms=duration,
            )
            return _json_response({'success': True, 'data': result})

        return self._run_with_guard(_handler)
