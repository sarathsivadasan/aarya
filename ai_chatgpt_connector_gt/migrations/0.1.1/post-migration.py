from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    configs = env['ai.config'].search([('type', '=', 'chatgpt')])
    if configs:
        configs._compute_allow_web_search()
