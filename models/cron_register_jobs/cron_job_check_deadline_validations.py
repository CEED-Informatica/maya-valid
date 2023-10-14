# -*- coding: utf-8 -*-

from odoo import models, api
from datetime import date, timedelta, datetime
import logging

_logger = logging.getLogger(__name__)

class CronJobCheckDeadlineValidations(models.TransientModel):
  _name = 'maya_valid.cron_job_check_deadline_validations'
  
  @api.model
  def cron_check_deadline_validations(self):
    today = date.today()
    validations = self.env['maya_valid.validation'].search([])

    updated_validations = []
    for val in validations:
      if val["correction_date_end"] != False and today > val["correction_date_end"]:
        val.write({
          'situation': '4'  
        })
        updated_validations.append(f'{val["course_abbr"]}/studend_id: {val["student_id"].id}')


    _logger.info('Subsanaciones fuera de plazo: ', updated_validations)