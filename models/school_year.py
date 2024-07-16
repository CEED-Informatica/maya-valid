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
  # Fecha final de las convalidaciones
  date_end_valid = fields.Date(string = 'Fin periodo de convalidaciones', compute = '_compute_date_end_valid', readonly = True)

  @api.depends('date_init_lective')
  def _compute_date_init_valid(self):
    for record in self:
      if record.date_init_lective == False:
        record.date_init_valid = ''
      else:
        record.date_init_valid = record.date_init_lective

  @api.depends('date_init_valid')
  def _compute_date_end_valid(self):
    for record in self:
      if record.date_init_valid == False:
        record.date_end_valid = ''
      else:
        record.date_end_valid =  record.date_init_valid + datetime.timedelta(days = 30)

  def update_dates(self):
    self.dates['init_valid'] = { 
      'date': self.date_init_valid,
      'desc': self._fields['date_init_valid'].string, 
      'type': 'G'
    }

    self.dates['end_valid'] = { 
      'date': self.date_end_valid,
      'desc': self._fields['date_end_valid'].string, 
      'type': 'G'
    }

    return super(SchoolYear, self).update_dates()
