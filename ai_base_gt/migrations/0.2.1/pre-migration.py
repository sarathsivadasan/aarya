import re

from odoo.tools.misc import remove_accents


def _to_code(name):
    s = remove_accents(name or '').lower()
    s = re.sub(r'[^a-z0-9-]+', '-', s)
    return s.strip('-') or 'template'


def migrate(cr, version):
    cr.execute("ALTER TABLE ai_prompt_template ADD COLUMN IF NOT EXISTS code VARCHAR")
    cr.execute("SELECT id, name FROM ai_prompt_template WHERE code IS NULL")
    rows = cr.fetchall()
    seen = set()
    for rec_id, name in rows:
        base = _to_code(name)
        code = base
        suffix = 2
        while code in seen:
            code = f"{base}-{suffix}"
            suffix += 1
        seen.add(code)
        cr.execute(
            "UPDATE ai_prompt_template SET code = %s WHERE id = %s",
            (code, rec_id),
        )
    cr.execute("ALTER TABLE ai_prompt_template ALTER COLUMN code SET NOT NULL")
