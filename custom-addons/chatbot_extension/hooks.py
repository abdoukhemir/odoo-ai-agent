import logging

_logger = logging.getLogger(__name__)

BOT_EMAIL = "ai.bot@yourdomain.com"
BOT_NAME = "AI Bot"


def create_ai_bot(env):
    """Create AI Bot partner and user if they don't exist"""
    try:
        # Get or create partner
        partner = env['res.partner'].sudo().search([
            ('email', '=', BOT_EMAIL)
        ], limit=1)

        if not partner:
            _logger.info(f"Creating AI Bot partner with email {BOT_EMAIL}")
            partner = env['res.partner'].sudo().create({
                'name': BOT_NAME,
                'email': BOT_EMAIL,
            })
            _logger.info(f"AI Bot partner created: {partner.id}")

        # Get or create user
        bot_user = env['res.users'].sudo().search([
            ('login', '=', BOT_EMAIL)
        ], limit=1)

        if not bot_user:
            _logger.info(f"Creating AI Bot user with login {BOT_EMAIL}")
            bot_user = env['res.users'].sudo().create({
                'name': BOT_NAME,
                'login': BOT_EMAIL,
                'partner_id': partner.id,
                'active': True,
            })
            _logger.info(f"AI Bot user created: {bot_user.id}")

        # Store bot partner ID in config for quick access
        env['ir.config_parameter'].sudo().set_param(
            'chatbot.ai_bot_partner_id',
            partner.id
        )
        
        _logger.info("AI Bot initialization completed successfully")
        
    except Exception as e:
        _logger.error(f"Error creating AI Bot: {e}", exc_info=True)
        raise