{
    'name': "AI Integration Base",
    'summary': """
Core module enables businesses to build and customize AI Assistants using diverse data sources and customizable contexts.
Can use other AI models like ChatGPT, Gemini, Claude, etc through connector modules.
Works with OpenAI ChatGPT, Anthropic Claude, and Google Gemini. ChatGPT AI, AI ChatGPT, Claude AI, AI Claude, Gemini AI, AI Gemini, Google AI. ChatGPT integration, OpenAI integration, Claude integration, Anthropic integration, Gemini integration, Google integration.
LLM, chatbot, virtual assistant, AI agent, generative AI, knowledge base, prompt template.
""",
    'sequence': 150,
    'description': """
Core module enables businesses to build and customize AI Assistants using diverse data sources and customizable contexts.
Can use other AI models like ChatGPT, Gemini, Claude, etc through connector modules.
Works with OpenAI ChatGPT, Anthropic Claude, and Google Gemini. ChatGPT AI, AI ChatGPT, Claude AI, AI Claude, Gemini AI, AI Gemini, Google AI. ChatGPT integration, OpenAI integration, Claude integration, Anthropic integration, Gemini integration, Google integration.
LLM, chatbot, virtual assistant, AI agent, generative AI, knowledge base, prompt template.
""",
    'author': "GT Apps",
    'support': 'gt.apps.odoo@gmail.com',
    'live_test_url': 'https://ai-demo.gt-apps.top',
    'category': 'Productivity/AI',
    'version': '0.2.2',
    'depends': ['base_setup'],
    'external_dependencies': {
        'python': [
            'mistune>=3.0.0',
            'markdownify>=0.11.0',
            'pyyaml>=6.0',
            'pydantic>=2.0.0,<2.11.0',
            'docstring_parser>=0.15',
            'fastembed>=0.5.0,<=0.5.1',
        ],
    },
    'data': [
        'data/data.xml',
        'data/ai_prompt_template_data.xml',
        'security/ai_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/ai_config_views.xml',
        'views/ai_data_source_views.xml',
        'views/ai_data_item_views.xml',
        'views/ai_assistant_views.xml',
        'views/ai_context_views.xml',
        'views/ai_prompt_template_views.xml',
        'views/ai_thread_views.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 9.9,
    'currency': 'USD',
}
