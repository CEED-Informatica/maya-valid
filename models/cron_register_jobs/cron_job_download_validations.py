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

class CronJobDownloadValidations(models.TransientModel):
  _name = 'maya_valid.cron_job_download_validations'

  def _assigns_end_date_validation_period(self, conn, validation_classroom_id, subject_id, course_id, current_school_year):
    """
    Asignación de la fecha fin de plazo del periodo de convalidaciones
    Se actualiza la fecha de todos los participantes en caso de que aún no la
    tengan asignada.

    Devuelve un array de tuplas (moodle_user_id, nueva fecha)
    """

    users = MayaMoodleUsers.from_course(conn, validation_classroom_id, only_students = True)

    users_to_change_due_date = []
    today = date.today()

    for user in users:
      a_user = CronJobEnrolUsers.enrol_student(self,user, subject_id, course_id)

      subject_student = self.env['maya_core.subject_student_rel']\
        .search([('subject_id', '=', subject_id),('student_id', '=', a_user.id),('course_id', '=', course_id)])
      
      if len(subject_student) == 0:
        _logger.warning('Incongruencia en la matricula. En el aula de Moodle de módulo (id Maya: {subject_id}) hay matriculado un alumno (id Maya: {a_user.id}) que no lo está en Maya')
        continue

      # aún no tiene abierto el periodo de convalidaciones. 
      # TODO alumno en dos ciclos!!!. mejor seria poner esto en subject_student_rel
      if not is_set_flag(subject_student[0].status_flags,constants.VALIDATION_PERIOD_OPEN):
        # asigno un periodo de 30 dias de plazo
        if current_school_year.date_init_valid > today: # el proceso ha ocurrido antes de abrir las aulas virtuales
          new_due_date = current_school_year.date_init_valid + timedelta(days = 30)
        else:
          new_due_date = today + timedelta(days = 30)
          
        users_to_change_due_date.append((user.id_,int(datetime(year = new_due_date.year, 
                     month = new_due_date.month,
                     day = new_due_date.day,
                     hour = 21,
                     minute = 59,
                     second = 59).timestamp())))
        
        # indicamos que ese usuario ya tiene el periodo abierto
        subject_student[0].write({
          'status_flags': set_flag(subject_student.status_flags,constants.VALIDATION_PERIOD_OPEN)
        })
     
    return users_to_change_due_date

  def _create_pending_academic_record(self, estudies: str, courses: str, validation):

    if len(courses) == 0 or estudies != 'Yes':
      return 
    
    courses_list = courses.split(',')
    
    for course in courses_list:
      academic_record = self.env['maya_valid.academic_record'].create([
        { 'validation_id': validation.id,
          'state': '0',
          'info': course.strip() }])

    return

  @api.model
  def cron_download_validations(self, validation_classroom_id, course_id, subject_id, validation_task_id, val_type = 0):

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
          'No se ha encontrado la tarea para convalidaciones (moodle_id: {})'.format(validation_task_id),
          50, # critical
          comments = '''Es posible que la tarea con moodle_id:{} no exista en moodle o no
                      exista dentro del curso con moodle_id: {}. 
                      Es posible que se haya creado un nuevo curso escolar y no se haya
                      actualizado los moodle_id dentro de maya'''.
                      format(validation_task_id, validation_classroom_id))
    
    msg_text = 'estudios' if val_type == STUDIES_VAL else 'UC'
    chk_fields = PDF_NOFIELDS_FITZ_COMPETENCY_VALIDATION if val_type == COMPETENCY_VAL else PDF_NOFIELDS_FITZ_VALIDATION
    mandatory_fields = PDF_COMPETENCY_VALIDATION_FIELDS_MANDATORY if val_type == COMPETENCY_VAL else PDF_VALIDATION_FIELDS_MANDATORY
    
    if val_type == STUDIES_VAL:
      assignments[0].set_extension_due_date(self._assigns_end_date_validation_period(
        conn, 
        validation_classroom_id, 
        subject_id, 
        course_id,
        current_school_year))
  
    # creación del directorio del ciclo para descomprimir las convalidaciones
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

      new_documentation = False

      _logger.info("Entrega convalidaciones {} del usuario moodle {}".format(msg_text, submission.userid))   
      user = MayaMoodleUser.from_userid(conn, submission.userid)   # usuario moodle
      a_user =  CronJobEnrolUsers.enrol_student(self, user, subject_id, course_id)  # usuario maya
  
      # obtención de la convalidación 
      validation_list = [ val for val in a_user.validations_ids if val.course_id.id == course_id]
      
      if len(validation_list) == 0:
        validation = self.env['maya_valid.validation'].create([
            { 'student_id': a_user.id,
              'course_id': course_id,
              'validation_type': val_type,
              'attempt_number': submission.attemptnumber + 1,
              'school_year_id': current_school_year.id }])
      else:
        validation = validation_list[0]

        _logger.info("Intento de entrega de convaldaciones de {} de A{}:M{}".format(msg_text, validation.attempt_number, submission.attemptnumber + 1))   

        if validation.attempt_number == submission.attemptnumber + 1: # no ha habido cambios en la entrega
          continue
        else:
          # esta condición está pensanda para el caso en el que hay una nueva entrega, pero también controla
          # el caso de que sean diferentes por problemas de sincronización entre Moodle y Maya:
          # si el registro desaparece de Maya => se iguala al de Moodle (en la creación de la convalidación)
          # si el registro desaparece en Moodle => Maya se igual al de Moodle
          validation.attempt_number = submission.attemptnumber + 1
          new_documentation = True
 
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
      
      # más de un fichero enviado (debería ser comprobado en Moodle)
      if len(submission.files) != 1:
        _logger.error("Sólo está permitido subir un archivo. Estudiante moodle id: {} {}".format(submission.userid, len(submission.files)))      
        submission.save_grade(3, new_attempt = True, feedback = validation.create_correction('MFL'))
        submission.set_extension_due_date(to = new_timestamp)
        continue
      
      # fichero no en formato zip  (debería ser comprobado en Moodle)
      if not submission.files[0].is_zip:
        _logger.error('El archivo de convalidaciones debe ser un zip. Estudiante moodle id: {}'.format(submission.userid))
        submission.save_grade(3, new_attempt = True, feedback = validation.create_correction('NZP')) 
        submission.set_extension_due_date(to = new_timestamp)
        continue
 
      # descarga del archivo
      foldername = '[{}] {}, {}'.format(
        user.id_,
        user.lastname.upper() if user.lastname is not None else 'SIN-APELLIDOS', 
        user.firstname.upper() if user.firstname is not None else 'SIN-NOMBRE')
      
      filename = '{}[{}][{}] {}, {}'.format(
        'UC ' if val_type == COMPETENCY_VAL else '',
        user.id_,
        submission.attemptnumber + 1,
        user.lastname.upper() if user.lastname is not None else 'SIN-APELLIDOS', 
        user.firstname.upper() if user.firstname is not None else 'SIN-NOMBRE')
      
      filename_nor = normalize('NFKD',filename.replace(' ','_')).encode('ASCII', 'ignore').decode('utf-8')

      # creación del directorio para almacenarlo
      path_user = os.path.join(path, foldername, '')
      path_user_nor = normalize('NFKD',path_user.replace(' ','_')).encode('ASCII', 'ignore').decode('utf-8')
      if not os.path.exists(path_user_nor):  
        os.makedirs(path_user_nor)

      submission.files[0].from_url(conn = conn, url = submission.files[0].url)
      submission.files[0].save_as(path_user_nor, filename_nor + '.zip')
      
      # creación del directorio para descomprimirlo
      path_user_submission = os.path.join(path_user_nor, filename_nor, '') 
      if not os.path.exists(path_user_submission):
        os.makedirs(path_user_submission)

      # lo descomprime. si el fichero existe, lo sobreescribe
      submission.files[0].unpack_to(path_user_submission, remove_directories = False)

      files_unzip = []
      for file in os.listdir(path_user_submission):
        file_nor = normalize('NFKD',file.replace(' ','_')).encode('ASCII', 'ignore').decode('utf-8')
        os.rename(os.path.join(path_user_submission, file), os.path.join(path_user_submission, file_nor.upper()))

      for file in os.listdir(path_user_submission):
        if os.path.isfile(os.path.join(path_user_submission, file)):
            files_unzip.append(file)
  
      _logger.info(files_unzip)
        
      annex_file = [file for file in files_unzip if 'ANEXO' in file or 'ANNEX' in file]

      # más de un anexo (o ninguno)
      if len(annex_file) != 1:
        _logger.error("Es necesario que haya un (y sólo un) fichero llamado anexo o annex. Estudiante moodle id: {} {}".format(submission.userid, len(annex_file)))   
        submission.save_grade(3,
                              new_attempt = True, 
                              feedback = validation.create_correction('NNX', 
                                                                         create_HTML_list_from_list( 
                                                                           ['No ha enviado en el zip una carpeta con los ficheros. En el zip no puede haber carpetas, solo uno o más ficheros pdf',
                                                                            'Uno de los ficheros (y sólo 1) tiene en su nombre la palabra anexo o annex'
                                                                         ], 'Compruebe que:')))
        submission.set_extension_due_date(to = new_timestamp)
        continue
  
      # datos obligatorios rellenados  
      fields = get_data_from_pdf(os.path.join(path_user_submission, annex_file[0]), chk_fields)
      _logger.info(fields)

      missing_fields = []
      for mandatory_field in mandatory_fields:
        assert isinstance(mandatory_field, tuple),  f'Valor incorrecto en constants.PDF_VALIDATION_FIELDS_MANDATORY o constants.PDF_COMPETENCY_VALIDATION_FIELDS_MANDATORY. Cada entrada tiene que ser una tupla'
        assert isinstance(mandatory_field[0], (str, tuple)), f'Valor incorrecto en constants.PDF_VALIDATION_FIELDS_MANDATORY o constants.PDF_COMPETENCY_VALIDATION_FIELDS_MANDATORY. La primera entrada de cada tupla o es una str o una tuple'
        
        if isinstance(mandatory_field[0], str):
          assert mandatory_field[0] in fields, f'La clave {mandatory_field[0]} no existe en el pdf'

          # un campo obligatorio no está definido
          if fields[mandatory_field[0]][constants.PDF_FIELD_VALUE] is None or \
             len(fields[mandatory_field[0]][constants.PDF_FIELD_VALUE]) == 0:
              missing_fields.append(mandatory_field[1])

        elif isinstance(mandatory_field[0], tuple):
          exist = False
          for option in mandatory_field[0]:
            if (fields[option][constants.PDF_FIELD_TYPE] != 'Button' and \
                fields[option][constants.PDF_FIELD_VALUE] is not None and \
                len(fields[option][constants.PDF_FIELD_VALUE]) != 0) or \
               (fields[option][constants.PDF_FIELD_TYPE] == 'Button' and fields[option][constants.PDF_FIELD_VALUE] == 'Yes'):
              exist = True
              break

          if not exist:
            missing_fields.append(mandatory_field[1])

      if len(missing_fields) > 0:
        _logger.error('Faltan campos obligatorios por definir en el pdf. Estudiante moodle id: {} {}'.format(submission.userid, missing_fields))

        appendix = ''
        if len(missing_fields) > 5:
          appendix = '<p><strong>Sugerencia</strong>. Compruebe que ha utilizado el anexo proporcionado \
            en el aula virtual, que no envía una versión escaneada/fotografiada o \
            que el anexo se encuentra en un documento separado.</p>'
        
        submission.save_grade(3, new_attempt = True, 
                                 feedback = validation.create_correction('ANC', 
                                                                         create_HTML_list_from_list(missing_fields, 'Campos a revisar:') + 
                                                                         appendix))
        submission.set_extension_due_date(to = new_timestamp)
        continue

      # integridad en la selección de campos
      paired_fields = []
      for paired_field in constants.PDF_VALIDATION_FIELDS_PAIRED:
        assert isinstance(paired_field, tuple),  f'Valor incorrecto en constants.PDF_VALIDATION_FIELDS_PAIRED. Cada entrada tiene que ser una tupla'

        if  ((fields[paired_field[0]][constants.PDF_FIELD_TYPE] != 'Button' and \
            fields[paired_field[0]][constants.PDF_FIELD_VALUE] is not None and \
            len(fields[paired_field[0]][constants.PDF_FIELD_VALUE]) != 0) or \
            (fields[paired_field[0]][constants.PDF_FIELD_TYPE] == 'Button' and \
            fields[paired_field[0]][constants.PDF_FIELD_VALUE] == 'Yes')) and \
            ((fields[paired_field[1]][constants.PDF_FIELD_TYPE] != 'Button' and \
            fields[paired_field[1]][constants.PDF_FIELD_VALUE] is None or \
            len(fields[paired_field[1]][constants.PDF_FIELD_VALUE]) == 0) or \
            (fields[paired_field[1]][constants.PDF_FIELD_TYPE] == 'Button' and \
             fields[paired_field[0]][constants.PDF_FIELD_VALUE] == 'Off')):
              paired_fields.append(fields[paired_field[0]][constants.PDF_FIELD_VALUE])

      if len(paired_fields) > 0:
        _logger.error("No se han definido correctamente si se solicita AA o CO. Estudiante moodle id: {} {}".format(submission.userid, paired_fields))
        # TODO, descomentar. Se comenta para facilitar las pruebas
        submission.save_grade(3, new_attempt = True, feedback = validation.create_correction('ANP'))
        submission.set_extension_due_date(to = new_timestamp)
        continue

      # Comprobación de firma digital
      buffer = BytesIO()
      pycurl_connex = pycurl.Curl()
      pycurl_connex.setopt(pycurl_connex.URL, 'http://pdf-signature-validator:80/verify_signature')
      pycurl_connex.setopt(pycurl_connex.POST, 1)
      pycurl_connex.setopt(pycurl_connex.HTTPPOST, 
                           [("file", (pycurl_connex.FORM_FILE, 
                                      os.path.join(path_user_submission, annex_file[0])))])
      pycurl_connex.setopt(pycurl_connex.WRITEDATA, buffer)
      
      pycurl_connex.perform()
      pycurl_connex.close()

      response_curl = buffer.getvalue().decode('utf-8')
      response_curl_data = json.loads(response_curl)

      validation.sign_data = response_curl
      if 'error' in response_curl_data:
        if response_curl_data['error'] == 'PDFSIG_ERROR' or \
           response_curl_data['error'] == 'NOT_SIGNED' or \
           response_curl_data['error'] == 'EXPIRED_CERTIFICATE' or \
           response_curl_data['error'] == 'REVOKED_CERTIFICATE' or \
           response_curl_data['error'] == 'NOT_VALID_CERTIFICATE':
           # response_curl_data['error'] == 'INVALID_SIGNATURE'
            _logger.error(f'El documento no está firmado electrónicamente. Estudiante moodle id: {submission.userid}. Error: {response_curl_data["error_message"]} ')
            submission.save_grade(3, new_attempt = True, feedback = validation.create_correction('SNF'))
            submission.set_extension_due_date(to = new_timestamp)
            continue
    

      # obtengo el NIA del formulario
      # aunque el login del alumno es su NIA, a dia de hoy Aules no me lo proporciona
      a_user.write({
        'nia': fields['A_NIA'][0].strip()
      })

      # asignacion de módulos a CO/AA
      validation_subjects = []
      validation_subjects_code_previous = {}
      # diccionario con todos los code de los modulos solicitados en la anterior entrega
      for val_subject in self.env['maya_valid.validation_subject'].search([('validation_id', '=', validation.id)]):
        validation_subjects_code_previous[val_subject.subject_id.code] = {
          'id': val_subject.subject_id.id,
          'type': val_subject.validation_type } 

      # TODO comprobar y eliminar si es el caso, si un mismo módulo aparece más de una vez
      id_subjects = []
      for key in fields:

        # es el nombre del módulo
        if key.startswith('C_Modulo') and len(key) < 12:
          #code = fields[key][0][:(fields[key][0].find(' -'))]
          if fields[key][0][:2] == 'CV':
            code = fields[key][0][:6]
          else:
            code = fields[key][0][:4]

          if val_type == STUDIES_VAL:
            validation_type = fields[key + 'AACO'][0][:2].lower()
          else: # las competenciales siempre son convalidaciones
            validation_type = 'CO'
          
          if len(code) == 0:
            continue

          if code in validation_subjects_code_previous and \
              validation_subjects_code_previous[code]['type'] == validation_type:
              del validation_subjects_code_previous[code]
              continue
          
          subject = self.env['maya_core.subject'].search([('code', '=', code)])
            
          if len(subject) == 0:
            raise MayaException(
              _logger, 
              'No se encuentra en Maya el módulo con código {}'.format(code),
              50, # critical
              comments = '''Tal vez falten módulos por codificar o que el código del PDF no sea el correcto. Código: {}
                '''. format(code))

          if code not in validation_subjects_code_previous:
            valid_subject = (0, 0, {
              'subject_id': subject.id,
              'state': '0',
              'validation_type': validation_type 
            }) 
          else:
            # actualizo el registro con el nuevo tipo de validación
            valid_subject = (1, validation_subjects_code_previous[code]['id'], {
              'validation_type': validation_type 
            }) 
            del validation_subjects_code_previous[code]
    
          # lo añade a la lista si no existe ya => en caso de módulo repetido
          # se queda con la primera aparición
          if subject.id not in id_subjects: 
            validation_subjects.append(valid_subject)
            id_subjects.append(subject.id)

      # los módulos solicitados en anteriores entregas que no han sido solcitados en esta
      # se eliminan
      for val_key in validation_subjects_code_previous:
        _logger.error(" va: {} {}".format(validation_subjects_code_previous[val_key], validation.id))
        self.env['maya_valid.validation_subject']. \
          search([('subject_id', '=', validation_subjects_code_previous[val_key]['id']),
                  ('validation_id', '=', validation.id)]). \
                  unlink()

      # añade nuevos registro, pero los mantiene en "el aire" hasta que se grabe el school_year 
      validation.validation_subjects_ids = validation_subjects

      ## llegados a este punto puden pasar varias cosas en función de la situaciíon de la convalidación
      # Habia una subsanación debida a un error general: no firmada, faltan campos, etc
      if validation.correction_reason != False and \
         validation.correction_reason != 'INT' and\
         validation.correction_reason[:3] != 'ERR' and \
        new_documentation:
        if val_type == STUDIES_VAL:
          self._create_pending_academic_record(fields['C_Docu6'][constants.PDF_FIELD_VALUE], fields['C_EstudiosCEED'][constants.PDF_FIELD_VALUE], 
                                               validation)

        submission.save_grade(2, feedback = '<h3>La documentación ha sido aceptada a trámite.<h3><p>La solicitud pasa a estado de <strong>en trámite</strong>.</p>')
        submission.lock()
        validation.write({ 
          'correction_reason': False,
          'state': '1',  # creo que deberia ser 0 :S, necesito madurarlo
          'correction_date': False
        })
      # subsanación por falta de documentación de uno de los módulos
      elif validation.correction_reason == 'INT' and new_documentation:
        validation.situation = '3'
        submission.save_grade(2)
      # ha pasado los filtros iniciales => cambio el estado a en proceso
      else:
        if val_type == STUDIES_VAL:
          self._create_pending_academic_record(fields['C_Docu6'][constants.PDF_FIELD_VALUE],fields['C_EstudiosCEED'][constants.PDF_FIELD_VALUE], validation)
        
        submission.save_grade(2, feedback = '<h3>La documentación ha sido aceptada a trámite.<h3><p>La solicitud pasa a estado de <strong>en trámite</strong>.</p>')
        submission.lock()
        
    return