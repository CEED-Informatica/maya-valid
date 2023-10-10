# -*- coding: utf-8 -*-

from odoo import models, api
from datetime import date, timedelta, datetime
import logging


# Moodle
from ....maya_core.support.maya_moodleteacher.maya_moodle_connection import MayaMoodleConnection
from ....maya_core.support.maya_moodleteacher.maya_moodle_assigments import MayaMoodleAssignments
from ....maya_core.support.maya_moodleteacher.maya_moodle_user import MayaMoodleUser
from ....maya_core.support.maya_moodleteacher.maya_moodle_user import MayaMoodleUsers

from ....maya_core.models.cron_register_jobs.cron_job_enrol_users import CronJobEnrolUsers

from ....maya_core.support.maya_logger.exceptions import MayaException


_logger = logging.getLogger(__name__)

class CronJobNotifyValidations(models.TransientModel):
  _name = 'maya_valid.cron_job_notify_validations'

  @api.model
  def cron_notify_validations(self, validation_classroom_id, course_id, subject_id, validation_task_id, correction_notification =  False):
    """
    Publica notificaciones sobre las convalidaciones 
    correction notification indica si es una notificación para realizar una corrección sobre una notificación anterior
    """
    # comprobaciones iniciales
    if validation_classroom_id == None:
      _logger.error("CRON: validation_classroom_id no definido")
      return
    
    if validation_task_id == None:
      _logger.error("CRON: validation_task_id no definido")
      return
    
    if course_id == None:
      _logger.error("CRON: course no definido")
      return
    
    if not correction_notification:
      validations = self.env['maya_valid.validation'].search([('course_id', '=', course_id)])
    else:
      validations = self.env['maya_valid.validation'].search([('course_id', '=', course_id), ('situation','=', '5')])

    if len(validations) == 0:
      return
    
    try:
      conn = MayaMoodleConnection( 
        user = self.env['ir.config_parameter'].get_param('maya_core.moodle_user'), 
        moodle_host = self.env['ir.config_parameter'].get_param('maya_core.moodle_url')) 
    except Exception:
      raise Exception('No es posible realizar la conexión con Moodle')
    
    current_sy = (self.env['maya_core.school_year'].search([('state', '=', 1)])) # curso escolar actual  

    if len(current_sy) == 0:
      raise MayaException(
          _logger, 
          'No se ha definido un curso actual',
          50, # critical
          comments = '''Es posible que no se haya marcado como actual ningún curso escolar''')
    else:
      current_school_year = current_sy[0]
        
    # obtención de las tareas entregadas
    assignments = MayaMoodleAssignments(conn, 
      course_filter=[validation_classroom_id], 
      assignment_filter=[validation_task_id])
    
    if len(assignments) == 0:
      raise MayaException(
          _logger, 
          'No se ha encontrado la tarea para convalidaciones (moodle_id: {})'.format(validation_task_id),
          50, # critical
          comments = '''Es posible que la tarea con moodle_id:{} no exista en moodle o no
                      exista dentro del curso con moodle_id: {}. 
                      Es posible que se haya creado un nuevo curso escolar y no se haya
                      actualizado los moodle_id dentro de Maya'''.
                      format(validation_task_id, validation_classroom_id))
    
    today = date.today()

    # en caso de subsanación se abre un perido de 15 dias naturales
    new_due_date = today + timedelta(days = 15)
    new_timestamp = int(datetime(year = new_due_date.year, 
                      month = new_due_date.month,
                      day = new_due_date.day,
                      hour = 0,
                      minute = 1,
                      second = 0).timestamp())     
    
    submissions = assignments[0].submissions()
    
    for validation in validations:

      # obtengo la primera entrega que tenga como estudiante al que se indica en la convalidación
      submission = next((sub for sub in submissions if sub.userid == int(validation.student_id.moodle_id)), None)
      if submission == None:
        _logger.error(f'No es posible encontrar en la tarea de Moodle {validation_task_id} la entrega del usuario id A{submission.user_id}:A{validation.student_id}')
        continue

      # está en estado de subsanación y el alumno no ha sido avisado
      if validation.state == '2' and validation.situation == '1':
        submission.save_grade(3, new_attempt = True, 
                                 feedback = validation.create_correction('INT',
                                                                         'Para más información consulte la Tabla de Convalidaciones (Real Decreto 1085/2020, de 9 de diciembre)'))
        submission.set_extension_due_date(to = new_timestamp)
        # TODO comprobar que la nota se haya almacenado correctamente en Moodle
        validation.write({
          'situation': '2'  
        })

      # está en estado de proceso, instancia superior o resuelto y el alumno había sido notificado de una subsanación
      if validation.state in ('1','3','5') and validation.situation == '5':
        submission.save_grade(2, new_attempt = False, feedback = validation.create_correction('ERR1'))
        # submission.set_extension_due_date(to = new_timestamp)
        # TODO comprobar que la nota se haya almacenado correctamente en Moodle
        validation.write({
          'situation': '0'  
        })

      # está en estado de subsanación o subsanacion/instancia superior y el alumno había sido notificado de una subsanación
      if validation.state in('2','4') and validation.situation == '5':
        submission.save_grade(3, new_attempt = True, feedback = validation.create_correction('ERR2'))
        submission.set_extension_due_date(to = new_timestamp)
        # TODO comprobar que la nota se haya almacenado correctamente en Moodle
        validation.write({
          'situation': '2'  
        })

      # está finalizada
      if validation.state == '13':
        submission.save_grade(4, new_attempt = False, feedback = validation.create_finished_notification_message())
