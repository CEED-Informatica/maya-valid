# -*- coding: utf-8 -*-

from odoo import fields, models


class Course(models.Model):
  """
  Herencia de clase
  Herencia del modelo maya_core.course
  Lo que hace es modificar el modelo maya_core.course para incluir 
  la función create_mbz_validation_tasks
  """
  _inherit = 'maya_core.course'

  def create_mbz_validation_tasks(self):
    print("hoola")
