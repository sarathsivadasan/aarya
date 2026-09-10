def migrate(cr, version):
    if not version:
        return
    # Create the join table manually so we can populate it from the old context_id
    # column while it still exists. The ORM will find the table already present and
    # skip its own DDL. PRIMARY KEY covers the unique constraint Odoo would add.
    cr.execute("""
        CREATE TABLE IF NOT EXISTS ai_assistant_ai_context_rel (
            ai_assistant_id INTEGER NOT NULL REFERENCES ai_assistant(id) ON DELETE CASCADE,
            ai_context_id   INTEGER NOT NULL REFERENCES ai_context(id)   ON DELETE CASCADE,
            PRIMARY KEY (ai_assistant_id, ai_context_id)
        )
    """)
    cr.execute("""
        INSERT INTO ai_assistant_ai_context_rel (ai_assistant_id, ai_context_id)
        SELECT id, context_id
        FROM ai_assistant
        WHERE context_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
