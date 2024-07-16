# -*- coding: utf-8 -*-

import datetime
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, AccessDenied

from ...maya_core.support.maya_logger.exceptions import MayaException

from datetime import date
import toolz
import logging

_logger = logging.getLogger(__name__)

class SchoolYear(models.Model):
  """
  Herencia de clase
  Herencia del modelo maya_core.school_year
  Lo que hace es modificar el modelo maya_core.school_year para incluir 
  la fecha de incio de las convalidaciones
  """
  _inherit = 'maya_core.school_year'

  # inicio real de las convalidaciones
  date_init_valid = fields.Date(string = 'Inicio periodo de convalidaciones', compute = '_compute_date_init_valid', readonly = False, store = True)

  @api.depends('date_init_lective')
  def _compute_date_init_valid(self):
    for record in self:
      if record.date_init_lective == False:
        record.date_init_valid = ''
      else:
        record.date_init_valid = record.date_init_lective