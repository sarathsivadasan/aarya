# -*- coding: utf-8 -*-
"""Per-user masking of product cost / sales price.

Two complementary layers, both server side:

* **View layer** -- ``_get_view()`` injects
  ``invisible="context.get('odex_hide_price')"`` (``column_invisible`` in list
  views) on every node bound to a price field. The injected expression is the
  same for everybody, so view caching stays valid and the web client evaluates
  it against each user's own context.
* **Data layer** -- ``_read_format()`` (used by ``read``, ``web_read``,
  ``web_search_read``) and ``export_data()`` blank the values out, so the
  numbers are not merely hidden in the DOM.

Adjust ``PRICE_FIELDS`` below to add or remove masked fields.
"""
from odoo import api, models

PRICE_FIELDS = (
    'standard_price',   # Cost (product.template / product.product)
    'list_price',       # Sales Price (template)
    'lst_price',        # Sales Price (variant)
    'price_extra',      # Variant extra price
    'price',            # Pricelist computed price
    'avg_cost',         # stock_account
    'total_value',      # stock_account
    'value_svl',        # stock_account
)

HIDE_EXPRESSION = "context.get('odex_hide_price')"


class OdexPriceMaskMixin(models.AbstractModel):
    _name = 'odex.price.mask.mixin'
    _description = 'Per User Price Masking'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _odex_hide_price(self):
        """True when the *current* user must not see prices.

        ``self.env.su`` short-circuits the check so that server side logic
        running as superuser (valuation, invoicing, reports, crons) keeps
        working on real values.
        """
        if self.env.su:
            return False
        return bool(self.env.user.sudo().context_odex_hide_price)

    @api.model
    def _odex_hide_node(self, node, attribute):
        existing = node.get(attribute)
        if existing:
            node.set(attribute, '(%s) or %s' % (existing, HIDE_EXPRESSION))
        else:
            node.set(attribute, HIDE_EXPRESSION)

    @api.model
    def _odex_apply_price_visibility(self, arch, view_type):
        field_attribute = 'column_invisible' if view_type == 'list' else 'invisible'
        for fname in PRICE_FIELDS:
            for node in arch.xpath("//field[@name='%s']" % fname):
                self._odex_hide_node(node, field_attribute)

                # Kanban cards wrap the value in a labelled container
                # (``<div name="product_lst_price">Price: <field .../></div>``);
                # hiding the field alone would leave the label behind. Only do
                # it when the container holds this field and nothing else.
                parent = node.getparent()
                if (
                    view_type == 'kanban'
                    and parent is not None
                    and parent.tag in ('div', 'span')
                    and parent.get('name')
                    and len(parent.xpath('.//field')) == 1
                ):
                    self._odex_hide_node(parent, 'invisible')

            for node in arch.xpath("//label[@for='%s']" % fname):
                self._odex_hide_node(node, 'invisible')

    # ------------------------------------------------------------------
    # view layer
    # ------------------------------------------------------------------
    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        self._odex_apply_price_visibility(arch, view_type)
        return arch, view

    # ------------------------------------------------------------------
    # data layer
    # ------------------------------------------------------------------
    def _read_format(self, fnames, load='_classic_read'):
        result = super()._read_format(fnames, load=load)
        masked = [fname for fname in fnames if fname in PRICE_FIELDS]
        if masked and self._odex_hide_price():
            for values in result:
                for fname in masked:
                    if fname in values:
                        values[fname] = 0.0
        return result

    def export_data(self, fields_to_export):
        result = super().export_data(fields_to_export)
        if not self._odex_hide_price():
            return result
        indexes = [
            index for index, fname in enumerate(fields_to_export)
            if fname.split('/')[0] in PRICE_FIELDS
        ]
        if indexes:
            for row in result.get('datas') or []:
                for index in indexes:
                    row[index] = ''
        return result


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'odex.price.mask.mixin']


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'odex.price.mask.mixin']
