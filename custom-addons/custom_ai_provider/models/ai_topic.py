from odoo import fields, models, api
from odoo.exceptions import UserError


# Patch to add custom provider to the PROVIDERS list and LLMApiService
def _patch_ai_providers():
    """Patch the ai.utils.llm_providers module to handle custom provider"""
    try:
        from odoo.addons.ai.utils import llm_providers
        from collections import namedtuple
        
        # Store the original get_provider function
        _original_get_provider = llm_providers.get_provider
        
        def patched_get_provider(env, llm_model):
            """Patched get_provider that handles custom_provider"""
            # Handle custom provider
            if llm_model == 'custom_provider':
                return 'custom'
            # Fall back to original for other providers
            return _original_get_provider(env, llm_model)
        
        # Replace the function in the module
        llm_providers.get_provider = patched_get_provider
        
        # Add custom provider to PROVIDERS list if not already there
        if not any(p.name == 'custom' for p in llm_providers.PROVIDERS):
            Provider = llm_providers.Provider
            custom_provider = Provider(
                name='custom',
                display_name='Custom Provider',
                embedding_model='text-embedding-3-small',  # Use OpenAI embedding as default
                llms=[('custom_provider', 'Custom Provider')]
            )
            llm_providers.PROVIDERS.append(custom_provider)
    except (ImportError, AttributeError):
        pass


def _patch_llm_api_service():
    """Patch the LLMApiService to support custom provider"""
    try:
        from odoo.addons.ai.utils import llm_api_service
        import json
        
        # Store the original methods
        _original_init = llm_api_service.LLMApiService.__init__
        _original_request_llm = llm_api_service.LLMApiService._request_llm
        _original_get_base_headers = llm_api_service.LLMApiService._get_base_headers
        _original_request_llm_openai_helper = llm_api_service.LLMApiService._request_llm_openai_helper
        
        def patched_init(self, env, provider='openai'):
            """Patched __init__ that supports custom provider"""
            self.provider = provider
            base_url = None
            
            if self.provider == 'openai':
                base_url = "https://api.openai.com/v1"
            elif self.provider == 'google':
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif self.provider == 'custom':
                # Get custom API URL from settings
                config = env['ir.config_parameter'].sudo()
                base_url = config.get_param('ai.custom_api_url', '')
                if not base_url:
                    raise UserError(env._("Custom API URL is not configured. Please configure it in Settings > AI > Providers"))
            else:
                raise NotImplementedError(f"Unsupported provider: {self.provider}")
            
            self.base_url = base_url
            self.env = env
        
        def patched_request_llm(self, *args, **kwargs):
            """Patched _request_llm that handles custom provider"""
            if self.provider == 'openai':
                return self._request_llm_openai(*args, **kwargs)
            elif self.provider == 'google':
                return self._request_llm_google(*args, **kwargs)
            elif self.provider == 'custom':
                # Treat custom provider as OpenAI-compatible
                return self._request_llm_openai(*args, **kwargs)
            else:
                raise NotImplementedError()
        
        def patched_get_base_headers(self):
            """Patched _get_base_headers that handles custom provider"""
            headers = {
                'Content-Type': 'application/json',
            }
            
            if self.provider in ('openai', 'custom'):
                # Get API key from settings
                config = self.env['ir.config_parameter'].sudo()
                api_key = config.get_param('ai.custom_api_key', '')
                if not api_key:
                    raise UserError(self.env._("Custom API key is not configured. Please configure it in Settings > AI > Providers"))
                headers['Authorization'] = f'Bearer {api_key}'
            elif self.provider == 'google':
                config = self.env['ir.config_parameter'].sudo()
                api_key = config.get_param('ai.google_key', '')
                if not api_key:
                    raise UserError(self.env._("Google API key is not configured"))
                headers['x-goog-api-key'] = api_key
            
            return headers
        
        def patched_request_llm_openai_helper(self, body, tools=None, inputs=()):
            """Patched helper that uses standard OpenAI format for custom provider"""
            # For custom provider, convert to standard OpenAI chat format
            if self.provider == 'custom':
                # Build standard OpenAI chat completion request
                messages = []
                for input_item in body.get("input", []):
                    role = input_item.get("role", "user")
                    content = input_item.get("content", [])
                    
                    if isinstance(content, list):
                        # Extract text from content list
                        text_content = ""
                        for c in content:
                            if isinstance(c, dict) and c.get('type') == 'input_text':
                                text_content += c.get('text', '')
                            elif isinstance(c, str):
                                text_content += c
                        if text_content:
                            messages.append({"role": role, "content": text_content})
                    else:
                        messages.append({"role": role, "content": content})
                
                # Build OpenAI-compatible request
                openai_body = {
                    "model": body.get("model", "gpt-3.5-turbo"),
                    "messages": messages,
                    "temperature": body.get("temperature", 0.7),
                }
                
                # Add tools if present
                if tools:
                    openai_body["tools"] = body.get("tools", [])
                
                # Make the request to /v1/chat/completions endpoint
                llm_response = self._request(
                    method="post",
                    endpoint="/v1/chat/completions",
                    headers=self._get_base_headers(),
                    body=openai_body,
                )
                
                # Convert OpenAI response format to Odoo format
                response = []
                to_call = []
                next_inputs = list(inputs or ())
                
                for choice in llm_response.get("choices", []):
                    message = choice.get("message", {})
                    content = message.get("content", "")
                    if content:
                        response.append(content)
                    
                    # Handle tool calls if present
                    if tool_calls := message.get("tool_calls"):
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("function", {}).get("name", "")
                            arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                            try:
                                arguments = json.loads(arguments_str)
                            except:
                                arguments = {}
                            to_call.append((tool_name, tool_call.get("id"), arguments))
                
                return response, to_call, next_inputs
            else:
                # Use original implementation for OpenAI and Google
                return _original_request_llm_openai_helper(self, body, tools, inputs)
        
        # Replace the methods
        llm_api_service.LLMApiService.__init__ = patched_init
        llm_api_service.LLMApiService._request_llm = patched_request_llm
        llm_api_service.LLMApiService._get_base_headers = patched_get_base_headers
        llm_api_service.LLMApiService._request_llm_openai_helper = patched_request_llm_openai_helper
    except (ImportError, AttributeError) as e:
        pass


# Apply the patches immediately when this module is imported
_patch_ai_providers()
_patch_llm_api_service()


class ResConfigSettings(models.TransientModel):
    """Extend AI settings to add Custom Provider configuration"""
    _inherit = 'res.config.settings'
    
    custom_api_enabled = fields.Boolean(
        string="Enable custom API provider",
        compute='_compute_custom_api_enabled',
        readonly=False,
        groups='base.group_system',
    )
    custom_api_name = fields.Char(
        string="Provider Name",
        config_parameter='ai.custom_api_name',
        readonly=False,
        groups='base.group_system',
        help='Friendly name for your custom API provider (e.g., "My N8N API", "Local LLM")',
    )
    custom_api_url = fields.Char(
        string="Custom API URL",
        config_parameter='ai.custom_api_url',
        readonly=False,
        groups='base.group_system',
        help='Base URL for custom LLM provider (e.g., http://localhost:3000)',
    )
    custom_api_key = fields.Char(
        string="Custom API Key",
        config_parameter='ai.custom_api_key',
        readonly=False,
        groups='base.group_system',
        help='API key for custom provider authentication',
    )

    def _compute_custom_api_enabled(self):
        for record in self:
            record.custom_api_enabled = bool(record.custom_api_url)


class AIAgent(models.Model):
    """Extend AI Agent to include custom provider in LLM model selection"""
    _inherit = 'ai.agent'
    
    @api.model
    def _get_extended_llm_model_selection(self):
        """Get LLM models including custom provider if configured"""
        # Get the default selections from parent provider list
        selection = []
        from odoo.addons.ai.utils.llm_providers import PROVIDERS
        for provider in PROVIDERS:
            selection.extend(provider.llms)
        
        return selection
    
    # Override the parent's llm_model field to include custom provider
    llm_model = fields.Selection(
        selection='_get_extended_llm_model_selection',
        string="LLM Model",
        default='gpt-4o',
        required=True,
    )
