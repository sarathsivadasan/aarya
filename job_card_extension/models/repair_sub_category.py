# -*- coding: utf-8 -*-

from odoo import models, fields


class RepairCategory(models.Model):
    _inherit = 'repair.category.custom'

    repair_sub_category_ids = fields.One2many("repair.sub.category.custom", "repair_category_id", string="Sub Category")


class RepairSubCategory(models.Model):
    _name = 'repair.sub.category.custom'
    _description = "Repair Category"

    name = fields.Char(string="Name")
    repair_category_id = fields.Many2one("repair.category.custom", string="Category")
