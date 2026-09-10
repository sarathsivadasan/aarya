# -*- coding: utf-8 -*-
import json
import logging
import time
from odoo import http, fields, _
from odoo.http import request, Response
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class AiAssistantController(http.Controller):
    """
    Main HTTP controller for ODEX AI Assistant.
    Delegates all AI calls to the AiProviderService abstraction layer,
    so every route works identically regardless of the active provider
    (Groq, Claude, OpenAI, Gemini, Ollama …).
    """

    # ────────────────────────────────────────────────────────────────
    # Internal helpers
    # ────────────────────────────────────────────────────────────────

    def _check_access(self):
        if not request.env.user.has_group('odex_ai_assistant.group_ai_user'):
            raise AccessError(_('You do not have access to the AI Assistant.'))

    def _provider_svc(self):
        """Shortcut to the provider service."""
        return request.env['odex.ai.provider.service'].sudo()

    def _get_config(self):
        return self._provider_svc().get_provider_config()

    def _build_record_context(self, res_model, res_id):
        """Build a JSON context string from the current Odoo record + chatter."""
        if not res_model or not res_id:
            return ''
        try:
            record = request.env[res_model].browse(int(res_id))
            if not record.exists():
                return ''
            ctx = {'model': res_model, 'id': res_id, 'name': record.display_name}
            for f in ['name', 'state', 'date', 'partner_id', 'user_id', 'company_id',
                      'amount_total', 'currency_id', 'stage_id']:
                if hasattr(record, f):
                    val = getattr(record, f)
                    try:
                        ctx[f] = val.display_name if hasattr(val, 'display_name') else (val.name if hasattr(val, 'name') else str(val))
                    except Exception:
                        pass
            # Recent chatter
            if hasattr(record, 'message_ids'):
                import re
                msgs = request.env['mail.message'].search([
                    ('res_id', '=', res_id), ('model', '=', res_model),
                    ('message_type', 'in', ['comment', 'email']),
                ], order='date desc', limit=5)
                chatter = []
                for m in msgs:
                    clean = re.sub('<[^<]+?>', '', m.body or '').strip()
                    if clean:
                        chatter.append({'author': m.author_id.name or 'Unknown',
                                        'date': str(m.date),
                                        'message': clean[:400]})
                if chatter:
                    ctx['recent_chatter'] = chatter
            return f'\n\n[Current Record Context]\n{json.dumps(ctx, indent=2, default=str)}'
        except Exception as e:
            _logger.warning('ODEX AI: could not build record context: %s', e)
            return ''

    def _build_api_messages(self, config, record_context, history, user_message):
        """Assemble the messages list to send to the API."""
        system_content = config['system_prompt']
        if record_context:
            system_content += record_context
        messages = [{'role': 'system', 'content': system_content}]
        messages.extend(history)
        messages.append({'role': 'user', 'content': user_message})
        return messages

    def _save_user_message(self, conversation, content):
        return request.env['odex.ai.message'].create({
            'conversation_id': conversation.id,
            'role': 'user',
            'content': content,
        })

    def _save_ai_message(self, conversation, content, config, tokens, processing_time):
        return request.env['odex.ai.message'].create({
            'conversation_id': conversation.id,
            'role': 'assistant',
            'content': content,
            'tokens_used': tokens,
            'model_used': config['model'],
            'processing_time': processing_time,
        })

    def _log_usage(self, config, conversation, res_model, res_id,
                   prompt_tokens, completion_tokens, processing_time,
                   status='success', error_msg='', request_type='chat'):
        try:
            request.env['odex.ai.usage.log'].create({
                'user_id':            request.env.user.id,
                'company_id':         request.env.company.id,
                'conversation_id':    conversation.id if conversation else False,
                'model_used':         config.get('model', ''),
                'prompt_tokens':      prompt_tokens,
                'completion_tokens':  completion_tokens,
                'processing_time':    processing_time,
                'status':             status,
                'error_message':      error_msg,
                'res_model':          res_model,
                'res_id':             res_id,
                'request_type':       request_type,
            })
        except Exception as e:
            _logger.warning('ODEX AI: usage log failed: %s', e)

    def _auto_title(self, conversation, user_message):
        if conversation.name == _('New Conversation') and len(conversation.message_ids) <= 3:
            title = user_message[:60] + ('…' if len(user_message) > 60 else '')
            conversation.write({'name': title})

    def _notify_bus(self, conversation, ai_msg, content):
        try:
            request.env['bus.bus']._sendone(
                request.env.user.partner_id,
                'odex_ai_message',
                {'conversation_id': conversation.id,
                 'message_id': ai_msg.id,
                 'content': content},
            )
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────
    # Routes
    # ────────────────────────────────────────────────────────────────

    @http.route('/odex_ai/get_config', type='json', auth='user', methods=['POST'])
    def get_config(self):
        try:
            self._check_access()
            return request.env['res.config.settings'].get_ai_config()
        except AccessError:
            return {'error': 'access_denied', 'has_api_key': False}

    # ── Non-streaming chat ───────────────────────────────────────────
    @http.route('/odex_ai/chat', type='json', auth='user', methods=['POST'])
    def chat(self, **kw):
        self._check_access()
        start = time.time()

        user_message   = (kw.get('message') or '').strip()
        conversation_id = kw.get('conversation_id')
        res_model       = kw.get('res_model')
        res_id          = kw.get('res_id')
        post_to_chatter = kw.get('post_to_chatter', False)

        if not user_message:
            return {'error': _('Message cannot be empty')}

        config = self._get_config()
        svc    = self._provider_svc()
        env    = request.env

        # Validate key
        try:
            svc.get_active_api_key(config)
        except UserError as e:
            return {'error': str(e)}

        # Get / create conversation
        conv = self._get_conversation(conversation_id, res_model, res_id)

        # Build API messages
        record_ctx  = self._build_record_context(res_model, res_id)
        history     = conv.get_conversation_context(limit=config['context_window'])
        api_messages = self._build_api_messages(config, record_ctx, history, user_message)

        self._save_user_message(conv, user_message)

        # Call provider
        try:
            resp = svc.call_provider(api_messages, config, stream=False)
            ai_content, usage = svc.extract_content_from_response(resp, config['provider'])

            prompt_tokens     = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens      = usage.get('total_tokens', prompt_tokens + completion_tokens)
            processing_time   = round(time.time() - start, 3)

            ai_msg = self._save_ai_message(conv, ai_content, config, total_tokens, processing_time)
            conv.write({'last_message_date': fields.Datetime.now(),
                        'total_tokens': conv.total_tokens + total_tokens})
            self._auto_title(conv, user_message)
            self._log_usage(config, conv, res_model, res_id,
                            prompt_tokens, completion_tokens, processing_time)

            if post_to_chatter and res_model and res_id:
                try:
                    record = env[res_model].browse(int(res_id))
                    ai_msg.post_to_chatter(record)
                except Exception as e:
                    _logger.warning('ODEX AI: post to chatter failed: %s', e)

            self._notify_bus(conv, ai_msg, ai_content)

            return {
                'success': True,
                'message_id': ai_msg.id,
                'content': ai_content,
                'conversation_id': conv.id,
                'conversation_name': conv.name,
                'tokens_used': total_tokens,
                'processing_time': processing_time,
                'model': config['model'],
                'provider': config['provider'],
            }

        except UserError as e:
            self._log_usage(config, conv, res_model, res_id,
                            0, 0, round(time.time() - start, 3),
                            status='error', error_msg=str(e))
            return {'error': str(e)}
        except Exception as e:
            _logger.error('ODEX AI: unexpected chat error: %s', e, exc_info=True)
            return {'error': _('An unexpected error occurred. Please try again.')}

    # ── Streaming chat (SSE) ─────────────────────────────────────────
    @http.route('/odex_ai/stream', type='http', auth='user', methods=['POST'], csrf=False)
    def stream_chat(self, **kw):
        self._check_access()

        try:
            body = json.loads(request.httprequest.data)
        except Exception:
            return Response('{"error":"Invalid JSON"}', content_type='application/json', status=400)

        user_message    = (body.get('message') or '').strip()
        conversation_id = body.get('conversation_id')
        res_model       = body.get('res_model')
        res_id          = body.get('res_id')

        if not user_message:
            return Response('data: {"error":"Empty message"}\n\n',
                            content_type='text/event-stream', status=400)

        config = self._get_config()
        svc    = self._provider_svc()
        env    = request.env

        try:
            svc.get_active_api_key(config)
        except UserError as e:
            return Response(f'data: {json.dumps({"error": str(e)})}\n\n',
                            content_type='text/event-stream', status=200)

        conv = self._get_conversation(conversation_id, res_model, res_id)
        record_ctx   = self._build_record_context(res_model, res_id)
        history      = conv.get_conversation_context(limit=config['context_window'])
        api_messages = self._build_api_messages(config, record_ctx, history, user_message)

        self._save_user_message(conv, user_message)

        def generate():
            full_content = []
            start = time.time()
            try:
                resp = svc.call_provider(api_messages, config, stream=True)
                for token, is_done in svc.iter_stream_tokens(resp, config['provider']):
                    if is_done:
                        complete = ''.join(full_content)
                        processing_time = round(time.time() - start, 3)
                        try:
                            ai_msg = self._save_ai_message(
                                conv, complete, config, 0, processing_time)
                            conv.write({'last_message_date': fields.Datetime.now()})
                            self._auto_title(conv, user_message)
                            self._log_usage(config, conv, res_model, res_id,
                                            0, 0, processing_time)
                        except Exception as ex:
                            _logger.error('ODEX AI stream save error: %s', ex)
                        _done_payload = json.dumps({
                            "done": True,
                            "conversation_id": conv.id,
                            "provider": config["provider"],
                        })
                        yield f"data: {_done_payload}\n\n"
                        break
                    elif token:
                        full_content.append(token)
                        yield f'data: {json.dumps({"token": token})}\n\n'
            except Exception as ex:
                _logger.error('ODEX AI stream error: %s', ex)
                yield f'data: {json.dumps({"error": str(ex)})}\n\n'

        return Response(
            generate(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            },
        )

    # ── Summarize record ─────────────────────────────────────────────
    @http.route('/odex_ai/summarize_record', type='json', auth='user', methods=['POST'])
    def summarize_record(self, res_model, res_id, post_to_chatter=False, **kw):
        self._check_access()
        start  = time.time()
        config = self._get_config()
        svc    = self._provider_svc()
        env    = request.env

        try:
            svc.get_active_api_key(config)
        except UserError as e:
            return {'error': str(e)}

        try:
            record = env[res_model].browse(int(res_id))
            if not record.exists():
                return {'error': _('Record not found')}

            model_label  = env[res_model]._description or res_model
            record_ctx   = self._build_record_context(res_model, res_id)
            prompt = (
                f'Provide a comprehensive, professional summary of this {model_label} record. '
                f'Include key information, current status, important dates, financial details '
                f'if applicable, and notable discussion points from chatter history. '
                f'Use clear sections and bullet points where helpful.\n{record_ctx}'
            )
            api_messages = [
                {'role': 'system', 'content': config['system_prompt']},
                {'role': 'user',   'content': prompt},
            ]

            resp = svc.call_provider(api_messages, config, stream=False)
            summary, usage = svc.extract_content_from_response(resp, config['provider'])
            processing_time = round(time.time() - start, 3)

            self._log_usage(config, None, res_model, res_id,
                            usage.get('prompt_tokens', 0),
                            usage.get('completion_tokens', 0),
                            processing_time, request_type='summary')

            if post_to_chatter and hasattr(record, 'message_post'):
                try:
                    body = (f'<p><strong>🤖 ODEX AI Summary</strong> '
                            f'<em>({config["provider"].title()} · {config["model"]})</em></p>'
                            f'<p>{summary.replace(chr(10), "<br/>")}</p>')
                    record.message_post(
                        body=body,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                        author_id=env.ref('base.partner_root').id,
                    )
                except Exception as ex:
                    _logger.warning('ODEX AI: post summary to chatter failed: %s', ex)

            return {'success': True, 'summary': summary,
                    'processing_time': processing_time, 'provider': config['provider']}

        except UserError as e:
            return {'error': str(e)}
        except Exception as e:
            _logger.error('ODEX AI summarize error: %s', e)
            return {'error': _('Failed to generate summary. Please try again.')}

    # ── Conversation management ──────────────────────────────────────
    @http.route('/odex_ai/get_conversations', type='json', auth='user', methods=['POST'])
    def get_conversations(self, **kw):
        self._check_access()
        env    = request.env
        limit  = kw.get('limit', 50)
        offset = kw.get('offset', 0)
        search = kw.get('search', '')
        domain = [('user_id', '=', env.user.id), ('company_id', '=', env.company.id)]
        if search:
            domain.append(('name', 'ilike', search))
        convs = env['odex.ai.conversation'].search(
            domain, order='is_pinned desc, write_date desc', limit=limit, offset=offset)
        result = []
        for c in convs:
            last = env['odex.ai.message'].search(
                [('conversation_id', '=', c.id), ('role', '=', 'assistant')],
                order='create_date desc', limit=1)
            result.append({
                'id': c.id, 'name': c.name,
                'message_count': c.message_count,
                'last_message': last.content[:100] if last else '',
                'last_message_date': str(c.last_message_date) if c.last_message_date else '',
                'is_pinned': c.is_pinned, 'state': c.state,
                'res_model': c.res_model, 'res_name': c.res_name,
            })
        return {'conversations': result,
                'total': env['odex.ai.conversation'].search_count(domain)}

    @http.route('/odex_ai/get_messages', type='json', auth='user', methods=['POST'])
    def get_messages(self, conversation_id, **kw):
        self._check_access()
        env  = request.env
        conv = env['odex.ai.conversation'].browse(int(conversation_id))
        if not conv.exists() or conv.user_id.id != env.user.id:
            return {'error': _('Conversation not found')}
        msgs = env['odex.ai.message'].search(
            [('conversation_id', '=', conv.id)], order='create_date asc')
        return {
            'messages': [{
                'id': m.id, 'role': m.role, 'content': m.content,
                'tokens_used': m.tokens_used, 'model_used': m.model_used,
                'create_date': str(m.create_date),
                'processing_time': m.processing_time, 'feedback': m.feedback,
            } for m in msgs],
            'conversation': {
                'id': conv.id, 'name': conv.name, 'total_tokens': conv.total_tokens,
            },
        }

    @http.route('/odex_ai/new_conversation', type='json', auth='user', methods=['POST'])
    def new_conversation(self, **kw):
        self._check_access()
        env      = request.env
        res_model = kw.get('res_model')
        res_id    = kw.get('res_id')
        vals = {'name': _('New Conversation'),
                'user_id': env.user.id, 'company_id': env.company.id}
        if res_model and res_id:
            vals['res_model'] = res_model
            vals['res_id']    = int(res_id)
            try:
                vals['res_name'] = env[res_model].browse(int(res_id)).display_name
            except Exception:
                pass
        conv = env['odex.ai.conversation'].create(vals)
        return {'conversation_id': conv.id, 'name': conv.name}

    @http.route('/odex_ai/delete_conversation', type='json', auth='user', methods=['POST'])
    def delete_conversation(self, conversation_id, **kw):
        self._check_access()
        env  = request.env
        conv = env['odex.ai.conversation'].browse(int(conversation_id))
        if conv.exists() and conv.user_id.id == env.user.id:
            conv.unlink()
            return {'success': True}
        return {'error': _('Conversation not found')}

    @http.route('/odex_ai/pin_conversation', type='json', auth='user', methods=['POST'])
    def pin_conversation(self, conversation_id, pinned=True, **kw):
        self._check_access()
        env  = request.env
        conv = env['odex.ai.conversation'].browse(int(conversation_id))
        if conv.exists() and conv.user_id.id == env.user.id:
            conv.action_pin() if pinned else conv.action_unpin()
            return {'success': True}
        return {'error': _('Conversation not found')}

    @http.route('/odex_ai/export_conversation', type='json', auth='user', methods=['POST'])
    def export_conversation(self, conversation_id, **kw):
        self._check_access()
        env  = request.env
        conv = env['odex.ai.conversation'].browse(int(conversation_id))
        if not conv.exists() or conv.user_id.id != env.user.id:
            return {'error': _('Conversation not found')}
        lines = [f'# {conv.name}', f'# {conv.write_date}', '---\n']
        for m in conv.message_ids:
            label = 'You' if m.role == 'user' else 'AI Assistant'
            lines.append(f'**{label}** ({m.create_date}):\n{m.content}\n')
        return {'content': '\n'.join(lines), 'name': conv.name}

    # ── Templates & Smart Actions ────────────────────────────────────
    @http.route('/odex_ai/get_templates', type='json', auth='user', methods=['POST'])
    def get_templates(self, **kw):
        self._check_access()
        return {'templates': request.env['odex.ai.prompt.template'].get_templates_for_model(
            kw.get('res_model'))}

    @http.route('/odex_ai/get_smart_actions', type='json', auth='user', methods=['POST'])
    def get_smart_actions(self, **kw):
        self._check_access()
        return {'actions': request.env['odex.ai.smart.action'].get_actions_for_model(
            kw.get('res_model', ''), kw.get('view_type', 'form'))}

    # ── Chatter ──────────────────────────────────────────────────────
    @http.route('/odex_ai/post_to_chatter', type='json', auth='user', methods=['POST'])
    def post_to_chatter(self, res_model, res_id, content, message_type='note', **kw):
        self._check_access()
        env = request.env
        try:
            record = env[res_model].browse(int(res_id))
            if not record.exists() or not hasattr(record, 'message_post'):
                return {'error': _('Record does not support chatter')}
            subtype = 'mail.mt_note' if message_type == 'note' else 'mail.mt_comment'
            config  = self._get_config()
            body = (f'<p><strong>🤖 ODEX AI Assistant</strong> '
                    f'<em>({config["provider"].title()} · {config["model"]})</em>:</p>'
                    f'<p>{content.replace(chr(10), "<br/>")}</p>')
            msg = record.message_post(
                body=body, message_type='comment',
                subtype_xmlid=subtype,
                author_id=env.ref('base.partner_root').id)
            return {'success': True, 'message_id': msg.id}
        except Exception as e:
            _logger.error('ODEX AI post_to_chatter error: %s', e)
            return {'error': str(e)}

    # ── Feedback ─────────────────────────────────────────────────────
    @http.route('/odex_ai/message_feedback', type='json', auth='user', methods=['POST'])
    def message_feedback(self, message_id, feedback_type, comment='', **kw):
        self._check_access()
        env = request.env
        try:
            msg = env['odex.ai.message'].browse(int(message_id))
            if msg.exists():
                msg.write({'feedback': 'positive' if feedback_type == 'positive' else 'negative'})
                env['odex.ai.feedback'].create({
                    'message_id': msg.id, 'user_id': env.user.id,
                    'feedback_type': feedback_type, 'comment': comment,
                })
                return {'success': True}
            return {'error': _('Message not found')}
        except Exception as e:
            return {'error': str(e)}

    # ── Analytics ────────────────────────────────────────────────────
    @http.route('/odex_ai/get_analytics', type='json', auth='user', methods=['POST'])
    def get_analytics(self, **kw):
        if not request.env.user.has_group('odex_ai_assistant.group_ai_manager'):
            return {'error': _('Access denied')}
        return request.env['odex.ai.usage.log'].get_usage_stats(days=kw.get('days', 30))

    # ── Provider test ─────────────────────────────────────────────────
    @http.route('/odex_ai/test_connection', type='json', auth='user', methods=['POST'])
    def test_connection(self, **kw):
        """Quick connectivity test — sends a minimal prompt and returns success/error."""
        self._check_access()
        config = self._get_config()
        svc    = self._provider_svc()
        try:
            svc.get_active_api_key(config)
        except UserError as e:
            return {'success': False, 'error': str(e)}

        test_messages = [
            {'role': 'system', 'content': 'You are a test assistant.'},
            {'role': 'user',   'content': 'Reply with exactly: OK'},
        ]
        # Use a small token budget for the test
        test_config = dict(config, max_tokens=10, streaming_enabled=False)
        try:
            resp = svc.call_provider(test_messages, test_config, stream=False)
            content, _ = svc.extract_content_from_response(resp, config['provider'])
            return {
                'success': True,
                'provider': config['provider'],
                'model':    config['model'],
                'response': content[:100],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ────────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────────

    def _get_conversation(self, conversation_id, res_model, res_id):
        env = request.env
        if conversation_id:
            conv = env['odex.ai.conversation'].browse(int(conversation_id))
            if conv.exists() and conv.user_id.id == env.user.id:
                return conv
        return env['odex.ai.conversation'].get_or_create_session(res_model, res_id)
