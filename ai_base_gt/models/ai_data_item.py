from fastembed import TextEmbedding
import numpy as np
import psycopg2.extensions
from odoo import fields, models, api
from odoo.tools import ormcache, groupby, SQL

# Register the vector type with psycopg2
def adapt_numpy_array(numpy_array):
    return psycopg2.extensions.adapt(','.join(map(str, numpy_array.flatten()))).getquoted()

psycopg2.extensions.register_adapter(np.ndarray, adapt_numpy_array)


class AiDataItem(models.Model):
    _name = 'ai.data.item'
    _description = 'AI Data Item'
    _rec_name = 'source'

    source = fields.Char(string="Source", required=True, index=True)
    res_model = fields.Char(string="Resource Model", index='btree_not_null')
    res_id = fields.Integer(string="Resource ID", index='btree_not_null')
    res_url = fields.Char(string="Resource URL", index='btree_not_null')
    data = fields.Text(string="Data")
    data_source_id = fields.Many2one('ai.data.source', string="Data Source", required=True, index=True, ondelete='cascade')
    vector = fields.Binary(string="Vector Embedding", attachment=False)
    vector_generated = fields.Boolean(string="Vector Generated", default=False)

    _sql_constraints = [
        ('data_id_unique', 'unique (source, data_source_id)', 'Source must be unique within a data source')
    ]

    def init(self):
        """Initialize pgvector when installing the module"""
        super().init()
        self._init_pgvector()

    @api.model
    def _init_pgvector(self):
        """Initialize pgvector extension and add vector column if not exists"""
        self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'ai_data_item'
                    AND column_name = 'embedding'
                ) THEN
                    ALTER TABLE ai_data_item ADD COLUMN embedding vector(384);
                END IF;
            END $$;
        """)
        # Create index for faster vector search
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ai_data_item_embedding_idx
            ON ai_data_item
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

    @ormcache()
    @api.model
    def _get_embedding_model(self):
        """Get or initialize the embedding model"""
        return TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            max_length=512
        )

    def _index(self, batch_size=32):
        """Generate embeddings for ``self`` where ``vector_generated`` is False.

        Runs FastEmbed in chunks of ``batch_size`` (default 32).
        Updates pgvector ``embedding``, ``vector`` (bytea), and ``vector_generated``.
        """
        todo = self.filtered(lambda r: not r.vector_generated)
        if not todo:
            return
        embed_model = self._get_embedding_model()
        total = len(todo)
        for start in range(0, total, batch_size):
            batch = todo[start:start + batch_size]
            texts = [(rec.data or '') for rec in batch]
            embeddings = list(embed_model.embed(texts))
            if len(embeddings) != len(batch):
                raise ValueError(
                    'FastEmbed batch size mismatch: %s texts vs %s embeddings'
                    % (len(batch), len(embeddings))
                )
            for rec, embedding in zip(batch, embeddings):
                self.env.cr.execute(
                    """
                    UPDATE ai_data_item
                    SET embedding = %s,
                        vector_generated = %s,
                        vector = %s
                    WHERE id = %s
                    """,
                    (str(embedding.tolist()), True, embedding.tobytes(), rec.id),
                )
            batch.invalidate_recordset(['vector', 'vector_generated'])

    @api.model
    def _search_similar(self, query, data_sources, limit=5):
        """Search for similar items using vector similarity"""
        EmbeddingModel = self._get_embedding_model()
        query_embedding = next(EmbeddingModel.embed([query]))
        embedding = str(query_embedding.tolist())

        model_sources = data_sources.filtered(lambda ds: ds.type == 'model' and ds.model_id)
        non_model_sources = data_sources - model_sources

        sub_queries = []

        # For non-model sources, users can access all data items.
        if non_model_sources:
            sub_queries.append(SQL(
                """
                SELECT id, data,
                       1 - (embedding <=> %s)::numeric AS similarity
                FROM ai_data_item
                WHERE data_source_id IN %s
                ORDER BY similarity DESC
                LIMIT %s
                """,
                embedding, tuple(non_model_sources.ids), limit,
            ))

        # For model sources, users can only access data items that are related to the records
        # they can access.
        for model_name, sources in groupby(model_sources, lambda ds: ds.model):
            source_ids = tuple(source.id for source in sources)
            Model = self.env[model_name]
            orm_query = Model._where_calc([])
            Model._apply_ir_rules(orm_query, 'read')
            model_table = SQL.identifier(Model._table)
            where_part = SQL("WHERE %s", orm_query.where_clause) if orm_query._where_clauses else SQL()
            sub_queries.append(SQL(
                """
                SELECT ai_data_item.id, ai_data_item.data,
                       1 - (ai_data_item.embedding <=> %s)::numeric AS similarity
                FROM %s
                JOIN ai_data_item
                    ON ai_data_item.data_source_id IN %s
                    AND ai_data_item.res_model = %s
                    AND ai_data_item.res_id = %s.id
                %s
                ORDER BY similarity DESC
                LIMIT %s
                """,
                embedding, orm_query.from_clause, source_ids, model_name, model_table, where_part, limit,
            ))

        if not sub_queries:
            return []

        if len(sub_queries) == 1:
            union_sql = sub_queries[0]
        else:
            union_sql = sub_queries[0]
            for q in sub_queries[1:]:
                union_sql = SQL("(%s) UNION ALL (%s)", union_sql, q)

        final_sql = SQL(
            "SELECT * FROM (%s) results ORDER BY similarity DESC LIMIT %s",
            union_sql, limit,
        )
        self.env.cr.execute(final_sql)

        results = self.env.cr.dictfetchall()
        for r in results:
            item = self.sudo().browse(r.pop('id'))
            if url := item._get_access_url():
                r['url'] = url
            if item.res_model and item.res_id:
                r['res_model'] = item.res_model
                r['res_id'] = item.res_id
        return results

    def _get_access_url(self):
        """Get the URL of the current data item."""
        self.ensure_one()
        base_url = self.get_base_url()
        url = False
        if self.res_url:
            url = self.res_url
        elif self.res_model and self.res_id:
            record = self.env[self.res_model].browse(self.res_id)
            if hasattr(record, 'website_url') and getattr(record, 'is_published', False):
                return f"{base_url}{record.website_url}"
            else:
                url = f"{base_url}/web#id={self.res_id}&model={self.res_model}"
        return url

    def write(self, vals):
        if 'data' in vals:
            vals['vector_generated'] = False  # Force regenerate vector if data changed
        return super().write(vals)
