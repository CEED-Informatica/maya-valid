# -*- coding: utf-8 -*-

from odoo import api, models, fields

import logging

_logger = logging.getLogger(__name__)

class AcademicRecord(models.Model):
  """
  Expedientes académicos que hay que generar de antiguos alumnos del Centro
  """

  _name = 'maya_valid.academic_record'
  _description = 'Expedientes académicos de antiguos alumnos del Centro'
  _order = 'write_date'

  validation_id = fields.Many2one('maya_valid.validation', string = 'Convalidación', required = True)
  state = fields.Selection([
      ('0', 'Pendiente'),
      ('1', 'No existe'),
      ('2', 'Finalizado')], required = True)
  
  info = fields.Text(string = 'Ciclo/curso', required = True)
  comments = fields.Text(string = 'Comentarios')