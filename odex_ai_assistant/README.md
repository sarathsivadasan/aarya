# ODEX AI Assistant
### Advanced AI Assistant for Odoo 18 Community Edition
**Powered by Groq API | Developed by Ampity Infotech**

---

## 📋 Overview

ODEX AI Assistant is a production-ready Odoo 18 Community addon that integrates an advanced AI chat assistant natively into your Odoo instance. It uses **Groq API** as the AI backend, providing ultra-fast inference with state-of-the-art models including **Llama 3.3 70B**, **DeepSeek R1**, and **Mixtral 8x7B**.

---

## 🖼️ Screenshots

> *(Install the module and access the AI panel by clicking the robot icon in the top navbar)*

- AI Chat Panel (Sidebar/Floating)
- Discuss Integration
- Chatter AI Button
- Settings Configuration
- Prompt Templates Library
- Usage Analytics Dashboard

---

## ✨ Key Features

### Chat Interface
- 🤖 **Global AI Panel** — accessible from every page via the navbar icon
- 💬 **Streaming Responses** — real-time token-by-token display (like ChatGPT)
- 📝 **Markdown Rendering** — code blocks, headers, lists, bold, italic
- 🗂️ **Conversation History** — multiple sessions with search
- 📌 **Pin Conversations** — keep important chats easily accessible
- 📤 **Export Chat** — download conversations as text files
- ⌨️ **Keyboard Shortcuts** — `Enter` to send, `Shift+Enter` for new line, `Escape` to close

### Discuss & Chatter Integration
- 📢 **Discuss Channel** — dedicated AI channel auto-created on install
- 💬 **Chatter AI Button** — appears on every record's chatter
- 📌 **Post to Chatter** — send AI responses directly to any record's log
- 🔄 **Real-time Bus Sync** — via Odoo's `bus.bus` service

### Context Awareness
- 🔗 **Record Context** — AI automatically understands the current record (sale order, invoice, vehicle, etc.)
- 📊 **Chatter History** — reads recent chatter messages as context
- 🏢 **Multi-company Safe** — isolates data per company

### AI Capabilities
- 📋 **Summarize Records** — one-click summaries for any model
- 🚗 **Vehicle Intelligence** — health scores, maintenance predictions, cost analysis
- 🔧 **Job Card AI** — auto-generate descriptions, suggest parts, create delivery notes
- 🔍 **Inspection AI** — analyze checklists, identify critical issues
- ⚙️ **Spare Parts AI** — consumption analysis, reorder suggestions
- 💰 **Accounting AI** — invoice analysis, payment follow-ups
- 📈 **CRM AI** — opportunity analysis, follow-up plans

---

## 🚀 Installation

### Prerequisites
- Odoo 18 Community Edition
- Python 3.10+
- PostgreSQL 14+
- `requests` Python library (usually pre-installed with Odoo)

### Step 1: Install the Module

```bash
# Copy the addon to your Odoo addons directory
cp -r odex_ai_assistant /path/to/your/odoo/addons/

# Or add the parent directory to your addons_path in odoo.conf:
# addons_path = /odoo/addons,/path/to/your/custom/addons
```

### Step 2: Update Odoo
```bash
# Update apps list
./odoo-bin -d your_database --update=base

# Or restart Odoo service
sudo systemctl restart odoo
```

### Step 3: Install from UI
1. Go to **Apps** menu
2. Search for **ODEX AI Assistant**
3. Click **Install**

### Step 4: Configure API Key (required)
1. Go to **Settings → General Settings**
2. Scroll down to **AI Assistant** section
3. Enter your **Groq API Key**
4. Select preferred AI model
5. Click **Save**

---

## 🔑 Groq API Setup

### Getting Your Free API Key
1. Visit [console.groq.com](https://console.groq.com)
2. Create a free account
3. Navigate to **API Keys** section
4. Click **Create API Key**
5. Copy the key (starts with `gsk_...`)
6. Paste in Odoo Settings → AI Assistant

### Free Tier Limits (as of 2025)
- **Llama 3.3 70B**: 14,400 requests/day, 500k tokens/minute
- **DeepSeek R1**: 100 requests/day, 6k tokens/minute  
- **Mixtral 8x7B**: 14,400 requests/day, 500k tokens/minute

---

## 🤖 AI Models

| Model | Best For | Context Window | Speed |
|-------|----------|----------------|-------|
| `llama-3.3-70b-versatile` | General use, recommended | 128K | Fast |
| `deepseek-r1-distill-llama-70b` | Complex reasoning, analysis | 128K | Medium |
| `mixtral-8x7b-32768` | Long documents, detailed work | 32K | Fast |
| `llama-3.1-8b-instant` | Quick simple queries | 128K | Ultra-fast |
| `gemma2-9b-it` | Instruction following | 8K | Fast |

---

## 📖 Usage Guide

### Opening the AI Panel
- Click the **🤖 robot icon** in the top navigation bar
- Or press `Alt+A` (keyboard shortcut)

### Chat Modes
1. **General Chat** — Ask anything about Odoo or your business
2. **Record Context** — Open any form view → the AI understands the current record
3. **Chatter Mode** — Click the AI button in any record's chatter

### Using the Chatter Button
1. Open any Odoo record (Sale Order, Invoice, Vehicle, etc.)
2. In the chatter section, click **AI** button
3. Choose an action:
   - **Open AI Chat** — opens the main panel with record context
   - **AI Generate & Post** — opens wizard to generate & post to chatter
   - **Quick AI Summary** — instantly generates and posts summary to chatter

### Using Prompt Templates
1. Click **Templates** tab in the AI panel
2. Browse templates by category
3. Click any template to use it as your message
4. Or go to **AI Assistant → Prompt Templates** to create your own

### Smart Actions
- Smart action buttons appear contextually based on the current model/record
- Configured in **AI Assistant → Smart Actions** (admin only)

---

## ⚙️ Configuration

### Settings Overview

| Setting | Description | Default |
|---------|-------------|---------|
| Groq API Key | Your Groq API key | (required) |
| AI Model | Model to use for responses | llama-3.3-70b-versatile |
| Temperature | Response creativity (0.0-2.0) | 0.7 |
| Max Tokens | Maximum response length | 2048 |
| Streaming | Enable real-time streaming | Enabled |
| Enable Chatter | Show AI buttons in chatters | Enabled |
| Context Window | Previous messages to include | 20 |
| System Prompt | AI personality/instructions | Default |
| Log Retention | Days to keep usage logs | 90 |
| AI Icon | Navbar icon | fa-robot |
| Panel Position | right/left/floating | right |

### Custom System Prompt
Customize the AI's personality in Settings:
```
You are ODEX AI, an expert in [your business type]. 
You specialize in [specific areas]. 
Always respond in [language].
Keep responses concise and actionable.
```

---

## 🔒 Security

### Access Groups
- **AI User** — Can use the AI chat panel (default for all users)
- **AI Manager** — Can manage settings, templates, view all analytics

### Granting Access
1. Go to **Settings → Users**
2. Edit a user
3. Under **Permissions**, set **ODEX AI Assistant** group

### API Key Security
- API key stored in `ir.config_parameter` (server-side only)
- Never exposed to frontend JavaScript
- Only visible to users with admin/manager access in Settings

### Data Security
- Users can only see their own conversations (record rules)
- Managers can see all conversations (for support/audit)
- All data partitioned by company (multi-company)

---

## 📊 Analytics & Monitoring

### Usage Analytics Dashboard
Navigate to **AI Assistant → Analytics → Usage Logs**:
- Total requests and tokens consumed
- Success/error rates
- Average response times
- Usage by user
- Usage by AI model
- Graph and pivot views for trend analysis

### Feedback System
Users can rate AI responses with thumbs up/down.
View feedback at **AI Assistant → Analytics → Feedback**.

---

## 🛠️ Troubleshooting

### "API key not configured" error
→ Go to Settings → General Settings → AI Assistant → Enter your Groq API key

### "Invalid API key" error
→ Verify the key starts with `gsk_` and was copied completely from Groq console
→ Check the key hasn't been revoked in Groq console

### "Rate limit exceeded" error
→ You've hit Groq's free tier limits
→ Wait a minute and retry
→ Consider switching to a model with higher limits

### Streaming not working
→ Check if your reverse proxy (nginx) supports SSE (Server-Sent Events)
→ Add to nginx config: `proxy_buffering off;` and `proxy_read_timeout 300s;`

### AI panel not appearing in navbar
→ Clear browser cache and reload
→ Check browser console for JavaScript errors
→ Verify the module is properly installed (no failed assets)

### Chatter button not visible
→ Verify user has **AI User** security group
→ Check if "Enable Chatter Integration" is enabled in Settings

### Module won't install
→ Ensure Odoo 18 Community (not 17 or Enterprise)
→ Check `odoo.log` for specific error messages
→ Verify `requests` library: `pip install requests`

---

## 🌐 Nginx Configuration for Streaming

Add to your nginx server block for SSE support:

```nginx
location /odex_ai/stream {
    proxy_pass http://127.0.0.1:8069;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_connect_timeout 10s;
    add_header Cache-Control no-cache;
    add_header X-Accel-Buffering no;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
}
```

---

## 🏗️ Module Architecture

```
odex_ai_assistant/
├── __manifest__.py          # Module definition
├── __init__.py              # Package init
├── hooks.py                 # Install/uninstall hooks
├── models/
│   ├── ai_conversation.py   # Conversation sessions
│   ├── ai_message.py        # Individual messages
│   ├── ai_prompt_template.py # Reusable prompts
│   ├── ai_usage_log.py      # API usage tracking
│   ├── ai_feedback.py       # Response ratings
│   ├── ai_smart_action.py   # Context actions
│   └── res_config_settings.py # Settings extension
├── controllers/
│   └── ai_controller.py     # HTTP routes & Groq API
├── wizard/
│   └── ai_chatter_wizard.py # Chatter integration wizard
├── security/
│   ├── security_groups.xml  # User groups
│   ├── ir.model.access.csv  # ACL rules
│   └── record_rules.xml     # Row-level security
├── views/                   # Odoo XML views
├── data/                    # Default data & cron jobs
├── static/src/
│   ├── js/
│   │   ├── services/
│   │   │   ├── ai_service.js       # Core service
│   │   │   └── ai_groq_service.js  # Groq utilities
│   │   └── components/
│   │       ├── ai_panel.js         # Main panel
│   │       ├── ai_message.js       # Message component
│   │       ├── ai_chatter_button.js # Chatter button
│   │       └── ai_navbar_button.js  # Navbar button
│   ├── xml/
│   │   ├── ai_panel.xml            # Panel templates
│   │   ├── ai_message.xml          # Message template
│   │   └── ai_chatter_button.xml   # Button templates
│   └── scss/
│       └── ai_assistant.scss       # All styles
└── demo/
    └── demo_data.xml               # Demo templates
```

### API Route Reference

| Route | Method | Description |
|-------|--------|-------------|
| `/odex_ai/get_config` | POST/JSON | Get AI config for frontend |
| `/odex_ai/chat` | POST/JSON | Send message, get response |
| `/odex_ai/stream` | POST/HTTP | SSE streaming chat |
| `/odex_ai/get_conversations` | POST/JSON | List conversations |
| `/odex_ai/get_messages` | POST/JSON | Get conversation messages |
| `/odex_ai/new_conversation` | POST/JSON | Create new conversation |
| `/odex_ai/delete_conversation` | POST/JSON | Delete conversation |
| `/odex_ai/get_templates` | POST/JSON | List prompt templates |
| `/odex_ai/get_smart_actions` | POST/JSON | List smart actions |
| `/odex_ai/summarize_record` | POST/JSON | Summarize a record |
| `/odex_ai/post_to_chatter` | POST/JSON | Post to record chatter |
| `/odex_ai/message_feedback` | POST/JSON | Submit message feedback |
| `/odex_ai/get_analytics` | POST/JSON | Usage statistics |
| `/odex_ai/export_conversation` | POST/JSON | Export as text |
| `/odex_ai/pin_conversation` | POST/JSON | Pin/unpin conversation |

---

## 🔮 Future Enhancements

- [ ] **Multi-Provider Support** — OpenAI, Claude (Anthropic), Gemini, Ollama
- [ ] **Voice Input** — Browser Web Speech API integration
- [ ] **Image Analysis** — Multimodal support for vehicle inspection photos
- [ ] **Document Upload** — PDF/DOC analysis in chat
- [ ] **AI Automation** — Create records directly from AI responses
- [ ] **Vector Memory** — Long-term memory with embedding search
- [ ] **Team AI Channels** — Multi-user AI conversations in Discuss
- [ ] **AI Notifications** — Proactive AI alerts and reminders
- [ ] **Mobile App** — Enhanced mobile AI experience
- [ ] **Webhook Integration** — Connect AI to external systems

---

## 📈 Performance Recommendations

1. **Context Window** — Set to 10-15 for faster responses; 20+ for better context
2. **Model Selection** — Use `llama-3.1-8b-instant` for high-volume simple tasks
3. **Temperature** — 0.3-0.5 for factual tasks; 0.7-0.9 for creative writing
4. **Max Tokens** — Set lower (512-1024) for quick answers, higher (2048+) for detailed analysis
5. **Streaming** — Keep enabled for better user experience
6. **Log Cleanup** — Cron job runs monthly; reduce to 30 days for busy systems

---

## 🔄 Upgrade Instructions

```bash
# 1. Backup your database first!
pg_dump your_database > backup.sql

# 2. Update module files
cp -r new_odex_ai_assistant /path/to/addons/

# 3. Update in Odoo
./odoo-bin -d your_database --update=odex_ai_assistant

# 4. Or via UI: Apps → ODEX AI Assistant → Upgrade
```

---

## 👥 Support & Contributing

- **Developer**: Ampity Infotech
- **Website**: https://ampityinfotech.com
- **License**: LGPL-3

For bug reports and feature requests, please contact Ampity Infotech.

---

## 📄 License

This module is licensed under the **LGPL-3** (Lesser General Public License v3).
You are free to use, modify, and distribute it under the terms of the LGPL-3 license.

---

*ODEX AI Assistant — Making Odoo Smarter, One Query at a Time* 🤖
