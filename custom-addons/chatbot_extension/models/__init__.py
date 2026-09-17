from . import chatbot
from . import ai_bot_access
from . import res_users
from .base_model_override import patch_odoo_models

# Apply AI Bot access control patches
patch_odoo_models()