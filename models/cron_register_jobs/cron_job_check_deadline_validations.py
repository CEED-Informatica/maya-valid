# -*- coding: utf-8 -*-

from odoo import models, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class CronJobCheckDeadlineStudiesValidations(models.TransientModel):
  _name = 'maya_valid.cron_job_check_deadline_studies_validations'
  
  @api.model
  def cron_check_deadline_validations(self):
    today = date.today()
   
    # convalidaciones por estudios
    validations = self.env['maya_valid.studies_validation'].search([])

    updated_validations = ''
    for val in validations:
      if val["correction_date_end"] != False and today > val["correction_date_end"]:
        val.write({
          'situation': '4'  
        })
        updated_validations += f'{val["course_abbr"]}/studend_id: {val["student_id"].id},'

    _logger.info('Subsanaciones por estudios fuera de plazo: '+ updated_validations)

    # convalidaciones por experiencia profesional
    validations = self.env['maya_valid.competency_validation'].search([])

    updated_validations = ''
    for val in validations:
      if val["correction_date_end"] != False and today > val["correction_date_end"]:
        val.write({
          'situation': '4'  
        })
        updated_validations += f'{val["course_abbr"]}/studend_id: {val["student_id"].id},'

    _logger.info('Subsanaciones por acreditación de competencias fuera de plazo: '+ updated_validations)

