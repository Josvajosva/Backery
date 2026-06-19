from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ingredients_name = fields.Html(string="")
    ingredients_first_value = fields.Char(string="")
    ingredients_second_value = fields.Char(string="")
    ingredients_third_value = fields.Char(string="")
    ingredients_fourth_value = fields.Char(string="")
    ingredients_fifth_value = fields.Char(string="")
    ingredients_sixth_value = fields.Char(string="")
    ingredients_seventh_value = fields.Char(string="")
    ingredients_eighth_value = fields.Char(string="")
    ingredients_ninth_value = fields.Char(string="")
    ingredients_tenth_value = fields.Char(string="")
    ingredients_eleventh_value = fields.Char(string="")
    ingredients_twelfth_value = fields.Char(string="")
    ingredients_thirteenth_value = fields.Char(string="")
    ingredients_fourteenth_value = fields.Char(string="")
    
        # Nutrition fields
    nutrition_first_value1 = fields.Char(string="")
    nutrition_first_value2 = fields.Char(string="")

    nutrition_second_value1 = fields.Char(string="")
    nutrition_second_value2 = fields.Char(string="")

    nutrition_third_value1 = fields.Char(string="")
    nutrition_third_value2 = fields.Char(string="")

    nutrition_fourth_value1 = fields.Char(string="")
    nutrition_fourth_value2 = fields.Char(string="")

    nutrition_fifth_value1 = fields.Char(string="")
    nutrition_fifth_value2 = fields.Char(string="")

    nutrition_sixth_value1 = fields.Char(string="")
    nutrition_sixth_value2 = fields.Char(string="")

    nutrition_seventh_value1 = fields.Char(string="")
    nutrition_seventh_value2 = fields.Char(string="")


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ingredients_name = fields.Html(string="")
    ingredients_first_value = fields.Char(string="")
    ingredients_second_value = fields.Char(string="")
    ingredients_third_value = fields.Char(string="")
    ingredients_fourth_value = fields.Char(string="")
    ingredients_fifth_value = fields.Char(string="")
    ingredients_sixth_value = fields.Char(string="")
    ingredients_seventh_value = fields.Char(string="")
    ingredients_eighth_value = fields.Char(string="")
    ingredients_ninth_value = fields.Char(string="")
    ingredients_tenth_value = fields.Char(string="")
    ingredients_eleventh_value = fields.Char(string="")
    ingredients_twelfth_value = fields.Char(string="")
    ingredients_thirteenth_value = fields.Char(string="")
    ingredients_fourteenth_value = fields.Char(string="")
    
        # Nutrition fields
    nutrition_first_value1 = fields.Char(string="")
    nutrition_first_value2 = fields.Char(string="")

    nutrition_second_value1 = fields.Char(string="")
    nutrition_second_value2 = fields.Char(string="")

    nutrition_third_value1 = fields.Char(string="")
    nutrition_third_value2 = fields.Char(string="")

    nutrition_fourth_value1 = fields.Char(string="")
    nutrition_fourth_value2 = fields.Char(string="")

    nutrition_fifth_value1 = fields.Char(string="")
    nutrition_fifth_value2 = fields.Char(string="")

    nutrition_sixth_value1 = fields.Char(string="")
    nutrition_sixth_value2 = fields.Char(string="")

    nutrition_seventh_value1 = fields.Char(string="")
    nutrition_seventh_value2 = fields.Char(string="")

  