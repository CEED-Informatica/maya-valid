# -*- coding: utf-8 -*-

from odoo import models, api
import os
from datetime import date, timedelta, datetime
import logging
import pycurl,json
from io import BytesIO
from unicodedata import normalize

# Moodle
from ....maya_core.support.maya_moodleteacher.maya_moodle_connection import MayaMoodleConnection
from ....maya_core.support.maya_moodleteacher.maya_moodle_assigments import MayaMoodleAssignments
from ....maya_core.support.maya_moodleteacher.maya_moodle_user import MayaMoodleUser
from ....maya_core.support.maya_moodleteacher.maya_moodle_user import MayaMoodleUsers

from ....maya_core.models.cron_register_jobs.cron_job_enrol_users import CronJobEnrolUsers

from ....maya_core.support.maya_logger.exceptions import MayaException

from ....maya_core.support.helper import create_HTML_list_from_list
from ....maya_core.support.helper import get_data_from_pdf
from ....maya_core.support.helper import is_set_flag,set_flag
from ...support.fitz_pdf_templates import PDF_NOFIELDS_FITZ_VALIDATION, PDF_NOFIELDS_FITZ_COMPETENCY_VALIDATION
from ...support.constants import PDF_VALIDATION_FIELDS_MANDATORY, PDF_COMPETENCY_VALIDATION_FIELDS_MANDATORY
from ...support import constants

from ..validation import STUDIES_VAL, COMPETENCY_VAL

_logger = logging.getLogger(__name__)

class CronJobDownloadValidationsClaims(models.TransientModel):
  _name = 'maya_valid.cron_job_download_validations_claims'

  @api.model
  def cron_download_validations_claims(self, validation_classroom_id, course_id, subject_id, validation_task_id, val_type = 0):

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
    
    validations_path = self.env['ir.config_parameter'].get_param('maya_valid.validations_path') or None
    if validations_path == None:
      _logger.error('La ruta de almacenamiento de convalidaciones no está definida')
      return
        
    try:
      conn = MayaMoodleConnection( 
        user = self.env['ir.config_parameter'].get_param('maya_core.moodle_user'), 
        moodle_host = self.env['ir.config_parameter'].get_param('maya_core.moodle_url')) 
    except Exception as e:
      raise Exception('No es posible realizar la conexión con Moodle' + e)
    
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
          'No se ha encontrado la tarea para reclamaciones de convalidaciones (moodle_id: {})'.format(validation_task_id),
          50, # critical
          comments = '''Es posible que la tarea con moodle_id:{} no exista en moodle o no
                      exista dentro del curso con moodle_id: {}. 
                      Es posible que se haya creado un nuevo curso escolar y no se haya
                      actualizado los moodle_id dentro de maya'''.
                      format(validation_task_id, validation_classroom_id))
    
    msg_text = 'estudios' if val_type == STUDIES_VAL else 'UC'
  
    # creación del directorio del ciclo para descomprimir la reclamación convalidaciones
    today = date.today()
    course = self.env['maya_core.course'].browse([course_id])
  
    path = os.path.join(validations_path, 
          '%s_%s' % (current_school_year.date_init.year, current_school_year.date_init.year + 1), 
          course.abbr) 

    if not os.path.exists(path):  
      os.makedirs(path)

    # comprobación de cada una de las tareas
    # TODO: probar con un parámetro en submission must_have_files = True
    for submission in assignments[0].submissions():
      # esta comprobación se hace la primera para evitar problemas de resto de datos que puede
      # haber en el tarea de Moodle
      if len(submission.files) == 0:
        _logger.info(f"No hay ficheros en la entrega {submission.userid}")
        continue

      _logger.info("Entrega reclamación de convalidaciones {} del usuario moodle {}".format(msg_text, submission.userid))   
      user = MayaMoodleUser.from_userid(conn, submission.userid)   # usuario moodle
      a_user =  CronJobEnrolUsers.enrol_student(self, user, subject_id, course_id)  # usuario maya
  
      # obtención de la convalidación 
      validation_list = [ val for val in a_user.validations_ids if val.course_id.id == course_id]
      
      validation = validation_list[0]

      if validation.claimed and validation.state == '15':   # ya ha sido resuelta y notificada al alumno
        # en caso de que esté en trámite, cada vez que se ejecute el cron, se descargará de nuevo
        # ni es eficiente, pero no hay muchas y no vale la pena el esfuerzo
        return

      ############                     ############
      ##### comprobación de errores a subsanar ####
      ############                     ############
      # en caso de subsanación se abre un perido de 15 dias naturales
      new_due_date = today + timedelta(days = 15)
      new_timestamp =  int(datetime(year = new_due_date.year, 
                         month = new_due_date.month,
                         day = new_due_date.day,
                         hour = 21,
                         minute = 59,
                         second = 59).timestamp())     
      
      # descarga del archivo
      foldername = '[{}] {}, {}'.format(
        user.id_,
        user.lastname.upper() if user.lastname is not None else 'SIN-APELLIDOS', 
        user.firstname.upper() if user.firstname is not None else 'SIN-NOMBRE')
      
      filename = 'RECLAMACION {}[{}] {}, {}'.format(
        'UC ' if val_type == COMPETENCY_VAL else '',
        user.id_,
        user.lastname.upper() if user.lastname is not None else 'SIN-APELLIDOS', 
        user.firstname.upper() if user.firstname is not None else 'SIN-NOMBRE')
      
      filename_nor = normalize('NFKD',filename.replace(' ','_')).encode('ASCII', 'ignore').decode('utf-8')

      # Al ser una reclamación el directorio del usuario para almacenarlo ya existe
      path_user = os.path.join(path, foldername, '')
      path_user_nor = normalize('NFKD',path_user.replace(' ','_')).encode('ASCII', 'ignore').decode('utf-8')
      
      submission.files[0].from_url(conn = conn, url = submission.files[0].url)
      submission.files[0].save_as(path_user_nor, filename_nor + '.zip')
      
      # creación del directorio para descomprimirlo
      path_user_submission = os.path.join(path_user_nor, filename_nor, '') 
      if not os.path.exists(path_user_submission):
        os.makedirs(path_user_submission)

      # ## llegados a este punto puden pasar varias cosas en función de la situaciíon de la convalidación
      # # Habia una subsanación debida a un error general: no firmada, faltan campos, etc
      # if validation.correction_reason != False and \
      #    validation.correction_reason != 'INT' and\
      #    validation.correction_reason[:3] != 'ERR' and \
      #   new_documentation:
      #   if val_type == STUDIES_VAL:
      #     self._create_pending_academic_record(fields['C_Docu6'][constants.PDF_FIELD_VALUE], fields['C_EstudiosCEED'][constants.PDF_FIELD_VALUE], 
      #                                          validation)

      #   submission.save_grade(2, feedback = '<h3>La documentación ha sido aceptada a trámite.<h3><p>La solicitud pasa a estado de <strong>en trámite</strong>.</p>')
      #   submission.lock()
      #   validation.write({ 
      #     'correction_reason': False,
      #     'state': '1',
      #     'correction_date': False
      #   })
      # # subsanación por falta de documentación de uno de los módulos
      # elif validation.correction_reason == 'INT' and new_documentation:
      #   validation.situation = '3'
      #   submission.save_grade(2)
      # # ha pasado los filtros iniciales => cambio el estado a en proceso
      # else:
      #   if val_type == STUDIES_VAL:
      #     self._create_pending_academic_record(fields['C_Docu6'][constants.PDF_FIELD_VALUE],fields['C_EstudiosCEED'][constants.PDF_FIELD_VALUE], validation)
        
      submission.save_grade(2, feedback = '<h3>La documentación de la reclamación ha sido aceptada a trámite.<h3><p>La solicitud pasa a estado de <strong>en trámite</strong>.</p>')
      submission.lock()
      validation.write({ 
        'state': '16',
        'claimed': True
      })

      # todas las convalidaciones de modulos pasan a estado reclamada
      for val in validation.validation_subjects_ids:
        val.write({ 
          'state': '8',
        })

        
    return