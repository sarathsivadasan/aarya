import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class Users(models.Model):
    _inherit = "res.users"

    repair_category = fields.Many2one(
        'repair.category.custom',
        string="Category"
    )
    repair_sub_category = fields.Many2one('repair.sub.category.custom')

    def update_user_categories(self, category, subcategory):
        self.env.user.repair_category = category if category else False
        self.env.user.repair_sub_category = subcategory if subcategory else False

    def get_current_category(self):
        repair_category = self.env.user.repair_category.id if self.env.user.repair_category else 0
        repair_sub_category = self.env.user.repair_sub_category.id if self.env.user.repair_sub_category else 0
        return repair_category, repair_sub_category

    def get_category_data(self):
        categories = self.env['repair.category.custom'].sudo().search([])
        result = []
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'subcategories': [
                    {
                        'id': subcategory.id,
                        'name': subcategory.name
                        # Add other subcategory fields as needed
                    }
                    for subcategory in category.repair_sub_category_ids
                ]
                # Add other category fields as needed
            }
            result.append(category_data)
        return result