# -*- coding: utf-8 -*-
{
    'name': 'ODEX AI Assistant',
    'version': '18.0.1.0.0',
    'summary': 'Advanced AI Assistant powered by Groq API with Discuss & Chatter Integration',
    'description': """
        ODEX AI Assistant - Powered by Groq API
        =======================================
        Advanced AI Assistant for Odoo 18 Community Edition.
        
        Features:
        - AI chat panel accessible globally across all modules
        - Discuss & Chatter integration
        - Groq API backend (llama, deepseek, mixtral models)
        - Streaming responses
        - Context-aware AI (understands active model/record)
        - Vehicle management AI features
        - Job card AI features
        - Spare parts intelligence
        - Workshop operational AI
        - Accounting AI features
        - Conversation history & sessions
        - Prompt templates
        - Usage analytics
        - Multi-company support
        - Mobile responsive
    """,
    'author': 'Ampity Infotech',
    'website': 'https://ampityinfotech.com',
    'category': 'Tools/AI',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'bus',
        'discuss',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/default_data.xml',
        'data/cron_jobs.xml',
        'views/res_config_settings_views.xml',
        'views/ai_conversation_views.xml',
        'views/ai_prompt_template_views.xml',
        'views/ai_analytics_views.xml',
        'views/ai_feedback_views.xml',
        'views/menus.xml',
        'wizard/ai_chatter_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odex_ai_assistant/static/src/scss/ai_assistant.scss',
            'odex_ai_assistant/static/src/xml/ai_panel.xml',
            'odex_ai_assistant/static/src/xml/ai_message.xml',
            'odex_ai_assistant/static/src/xml/ai_chatter_button.xml',
            'odex_ai_assistant/static/src/js/services/ai_service.js',
            'odex_ai_assistant/static/src/js/services/ai_groq_service.js',
            'odex_ai_assistant/static/src/js/components/ai_panel.js',
            'odex_ai_assistant/static/src/js/components/ai_message.js',
            'odex_ai_assistant/static/src/js/components/ai_chatter_button.js',
            'odex_ai_assistant/static/src/js/components/ai_navbar_button.js',
        ],
    },
    'demo': [
        'demo/demo_data.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
