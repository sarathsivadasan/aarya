# -*- coding: utf-8 -*-
import logging
import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class AiChatterWizard(models.TransientModel):
    """
    Wizard to use AI assistant directly from any chatter/form view.
    Allows generating content and posting it to the record chatter.
    """
    _name = 'odex.ai.chatter.wizard'
    _description = 'AI Chatter Assistant'

    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    res_name = fields.Char(string='Record Name', compute='_compute_res_name')
    action_type = fields.Selection([
        ('summarize', 'Summarize Record'),
        ('generate_email', 'Generate Email Response'),
        ('generate_note', 'Generate Internal Note'),
        ('analyze', 'Analyze & Suggest'),
        ('custom', 'Custom Prompt'),
    ], string='Action', required=True, default='summarize')
    custom_prompt = fields.Text(string='Custom Prompt')
    ai_response = fields.Html(string='AI Response', readonly=True, sanitize=True)
    post_type = fields.Selection([
        ('note', 'Internal Note'),
        ('message', 'Post as Message'),
    ], string='Post As', default='note')
    template_id = fields.Many2one(
        'odex.ai.prompt.template',
        string='Use Template',
    )
    is_generating = fields.Boolean(default=False)

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for rec in self:
            try:
                if rec.res_model and rec.res_id:
                    record = self.env[rec.res_model].browse(rec.res_id)
                    rec.res_name = record.display_name if record.exists() else ''
                else:
                    rec.res_name = ''
            except Exception:
                rec.res_name = ''

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            self.custom_prompt = self.template_id.prompt_text
            self.action_type = 'custom'

    def _get_api_config(self):
        """Use the multi-provider service layer."""
        svc = self.env['odex.ai.provider.service'].sudo()
        config = svc.get_provider_config()
        # Validate key exists (raises UserError if missing)
        svc.get_active_api_key(config)
        return config

    def _build_record_context(self):
        """Build context from the current record."""
        try:
            record = self.env[self.res_model].browse(self.res_id)
            if not record.exists():
                return ""
            context = {
                'model': self.res_model,
                'name': record.display_name,
            }
            for field in ['name', 'state', 'date', 'partner_id', 'amount_total', 'stage_id']:
                if hasattr(record, field):
                    val = getattr(record, field)
                    try:
                        context[field] = val.display_name if hasattr(val, 'display_name') else str(val)
                    except Exception:
                        pass

            # Get chatter messages
            if hasattr(record, 'message_ids'):
                msgs = self.env['mail.message'].search([
                    ('res_id', '=', self.res_id),
                    ('model', '=', self.res_model),
                ], order='date desc', limit=10)
                import re
                chatter = []
                for m in msgs:
                    clean = re.sub('<[^<]+?>', '', m.body or '').strip()
                    if clean:
                        chatter.append(f"- {m.author_id.name}: {clean[:300]}")
                if chatter:
                    context['chatter_history'] = '\n'.join(chatter)
            return json.dumps(context, default=str, indent=2)
        except Exception as e:
            _logger.warning("Wizard context build error: %s", str(e))
            return ""

    def action_generate(self):
        """Generate AI response based on selected action."""
        self.ensure_one()
        config = self._get_api_config()
        record_context = self._build_record_context()
        model_name = self.env[self.res_model]._description or self.res_model

        # Build prompt based on action type
        prompts = {
            'summarize': (
                f"Provide a comprehensive professional summary of this {model_name} record. "
                f"Include key details, status, important dates, and notable discussion points."
            ),
            'generate_email': (
                f"Draft a professional email response for this {model_name}. "
                f"The email should be clear, professional, and address the key points."
            ),
            'generate_note': (
                f"Generate a detailed internal note for this {model_name}. "
                f"Include current status analysis, action items, and recommendations."
            ),
            'analyze': (
                f"Analyze this {model_name} record and provide intelligent suggestions. "
                f"Identify issues, opportunities, and recommend next steps."
            ),
            'custom': self.custom_prompt or '',
        }

        user_prompt = prompts.get(self.action_type, self.custom_prompt or '')
        if not user_prompt:
            raise UserError(_("Please enter a prompt or select an action type."))

        full_prompt = f"{user_prompt}\n\n[Record Data]:\n{record_context}"

        messages = [
            {'role': 'system', 'content': config['system_prompt']},
            {'role': 'user', 'content': full_prompt},
        ]

        try:
            svc = self.env['odex.ai.provider.service'].sudo()
            resp = svc.call_provider(messages, config, stream=False)
            ai_content, _ = svc.extract_content_from_response(resp, config['provider'])
            content = ai_content

            # Format as HTML for display
            html_content = content.replace('\n\n', '</p><p>').replace('\n', '<br/>')
            self.write({'ai_response': f'<p>{html_content}</p>'})

            # Increment template use count
            if self.template_id:
                self.template_id.sudo().action_increment_use_count()

            # Return view to show response
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'odex.ai.chatter.wizard',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': self.env.context,
            }
        except requests.exceptions.RequestException as e:
            raise UserError(_(f"API request failed: {str(e)}"))
        except Exception as e:
            _logger.error("Wizard generation error: %s", str(e))
            raise UserError(_(f"AI generation failed: {str(e)}"))

    def action_post_to_chatter(self):
        """Post the generated AI response to the record chatter."""
        self.ensure_one()
        if not self.ai_response:
            raise UserError(_("No AI response to post. Please generate first."))

        try:
            record = self.env[self.res_model].browse(self.res_id)
            if not record.exists() or not hasattr(record, 'message_post'):
                raise UserError(_("Record does not support chatter integration."))

            action_labels = {
                'summarize': '🤖 AI Summary',
                'generate_email': '🤖 AI Email Draft',
                'generate_note': '🤖 AI Internal Note',
                'analyze': '🤖 AI Analysis',
                'custom': '🤖 AI Response',
            }
            label = action_labels.get(self.action_type, '🤖 AI Response')
            body = f"<p><strong>{label}</strong></p>{self.ai_response}"
            subtype = 'mail.mt_note' if self.post_type == 'note' else 'mail.mt_comment'

            record.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid=subtype,
                author_id=self.env.ref('base.partner_root').id,
            )
            return {'type': 'ir.actions.act_window_close'}
        except UserError:
            raise
        except Exception as e:
            _logger.error("Post to chatter error: %s", str(e))
            raise UserError(_(f"Failed to post to chatter: {str(e)}"))
