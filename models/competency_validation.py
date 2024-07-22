# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo.exceptions import ValidationError

from odoo.exceptions import AccessDenied 

import datetime
import logging
import base64
import os, json

from unicodedata import normalize

from ...maya_core.support.helper import create_HTML_list_from_list
from ...maya_core.support.maya_logger.exceptions import MayaException

_logger = logging.getLogger(__name__)

from validation import COMPETENCY_VAL

class CompetencyValidation(models.Model):
  """
  Define la entrega de convalidaciones de estudios por parte del alumnado
  """
  _name = 'maya_valid.competency_validation'
  _description = 'Solicitud convalidación por experiencia'
  _inherit = ['maya_valid.validation']
  
  validation_subjects_ids = fields.One2many('maya_valid.competency_validation_subject', 'validation_id', 
     string = 'Módulos que se solicita convalidar')

  validation_subjects_not_for_correction_ids = fields.One2many('maya_valid.competency_validation_subject', 
  'validation_id', 
    string = 'Módulos que se solicita convalidar', 
    domain = [('state', '!=', '1')],
    compute = '_compute_validation_subjects_not', readonly = False)

  validation_subjects_for_correction_ids = fields.One2many('maya_valid.competency_validation_subject', 'validation_id', 
    string = 'Módulos pendientes de subsanación',
    domain = [('state', '=', '1')],
    compute = '_compute_validation_subjects', readonly = False)
     
  validation_subjects_info = fields.Char(string = 'Res. / Fin. / Sol.', compute = '_compute_validation_subjects_info')

  # TODO que hacer con instancia superior si tardan en responder??
  # una opción es pasado un tiempo enviar el mail de confirmación al alumno
  # y finalizarla parcialmente
  state = fields.Selection([
      ('0', 'Sin procesar'),
      ('1', 'En proceso'),
      ('2', 'Subsanación'),
      ('3', 'Instancia superior'),
      ('4', 'Subsan. / Inst. superior'),
      ('5', 'Resuelta'),
      ('6', 'En proceso de revisión'),
      ('7', 'En proceso de revisión (parcial)'), # algunas revisadas, otras aun resueltas y algunas elevadas a una instancia superior
      ('10', 'En proceso de finalización (parcial)'),
      ('11', 'Finalizada parcialmente'),
      ('12', 'En proceso de finalización'),
      ('13', 'Finalizada'), # todas las convalidaciones finalizadas pero sin notificación al alumno
      ('14', 'Cerrada'),
      ], string ='Estado', help = 'Estado de la convalidación', 
      default = '0', compute = '_compute_state', store = True)
  
  def _compute_validation_subjects_info(self):
    for record in self:
        num_resolved = len([val for val in record.validation_subjects_ids if int(val.state) >= 3])
        num_finished = len([val for val in record.validation_subjects_ids if int(val.state) >= 6])
        record.validation_subjects_info = f'{num_resolved} / {num_finished} / {len(record.validation_subjects_ids)}'

  def download_validation_action(self):
    """
    Descarga la última versión de la documentación
    """  
    self.download_validation_action(self, COMPENTENCY_VAL)
