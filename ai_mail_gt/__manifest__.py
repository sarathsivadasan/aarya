{
    'name': "AI Assistant for Discuss",
    'summary': """
Smart AI assistants for Odoo Discuss, combining AI capabilities with data sources and customizable context.
Can use other AI models like ChatGPT, Gemini, Claude, etc through connector modules.
Works with OpenAI ChatGPT, Anthropic Claude, and Google Gemini. ChatGPT AI, AI ChatGPT, Claude AI, AI Claude, Gemini AI, AI Gemini, Google AI. ChatGPT integration, OpenAI integration, Claude integration, Anthropic integration, Gemini integration, Google integration.
LLM, chatbot, virtual assistant, generative AI.
""",
    'sequence': 150,
    'description': """
Smart AI assistants for Odoo Discuss, combining AI capabilities with data sources and customizable context.
Can use other AI models like ChatGPT, Gemini, Claude, etc through connector modules.
Works with OpenAI ChatGPT, Anthropic Claude, and Google Gemini. ChatGPT AI, AI ChatGPT, Claude AI, AI Claude, Gemini AI, AI Gemini, Google AI. ChatGPT integration, OpenAI integration, Claude integration, Anthropic integration, Gemini integration, Google integration.
LLM, chatbot, virtual assistant, generative AI.
""",
    'author': "GT Apps",
    'support': 'gt.apps.odoo@gmail.com',
    'live_test_url': 'https://ai-demo.gt-apps.top',
    'category': 'Productivity/AI',
    'version': '0.1.1',
    'depends': ['mail', 'ai_base_gt'],
    'external_dependencies': {
        'python': ['markdownify>=0.11.0'],
    },
    'data': [],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'ai_mail_gt/static/src/**/*',
        ],
        'mail.assets_public': [
            'ai_mail_gt/static/src/core/common/**/*',
            'ai_mail_gt/static/src/core/public_web/**/*',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'application': False,
    'auto_install': True,
    'license': 'OPL-1',
    'price': 119.9,
    'currency': 'USD',
}
