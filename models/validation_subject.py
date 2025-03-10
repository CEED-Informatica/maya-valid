# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo.exceptions import ValidationError, AccessDenied
import logging
import os

from datetime import date

_logger = logging.getLogger(__name__)

VALIDATION_SUBJECTS_STATES = [
          ('0', 'Sin procesar'),
          ('1', 'Subsanación'), # hay que solicitar documentación
          ('2', 'Instancia superior'), # no está clara y los convalidadores la envian a instancia superior
          ('3', 'Resuelta'), # los convalidadores la han resuelto
          ('4', 'Revisada'), # jefatura la ha dado por buena
          ('5', 'Por revisar'), # desde secretaria ven un error y la tiran para atrás (a jefatura)
          ('6', 'Finalizada'), # Introducida en el expediente del alumno
          ('7', 'Cerrada'), # no seleccionable (salvo por el root). Se asigna automáticamente cuando todas las 
                                 # convalidaciones han sido finalizadas y el mensaje se ha enviado al alumno.
                                 # La convalidación queda bloqueada (salvo para el root)
          ('8', 'Reclamada'),
          ('9', 'Revisada tras reclamación')]

    # no hay estado de devolución desde jefatura (coordinación) a los convalidadores.  Directamente resuelve jefatura o 
    # se puede poner sin procesar ya que coordinación tiene acceso los estados previos. 

class ValidationSubject(models.Model):
  """
  Define los módulos a convalidar
  """
  _name = 'maya_valid.validation_subject'
  _description = 'Módulo a convalidar'
  _rec_name = 'validation_subject_info' 
  # necesario para poder asociar actividades
  #_inherit = ['mail.thread', 'mail.activity.mixin']

  validation_id = fields.Many2one('maya_valid.validation', string = 'Convalidación', required = True)
  student_nia = fields.Char(related = 'validation_id.student_nia')
  student_info = fields.Char(string = 'Estudiante', compute = '_compute_student_info')
  course_info = fields.Char(related = 'validation_id.course_abbr')

  validation_subject_info = fields.Char(string = 'Convalidación módulo', compute = '_compute_validation_subject_info')

  subject_id = fields.Many2one('maya_core.subject', string = 'Módulo', required = True)
  subject_abbr = fields.Char(related = 'subject_id.abbr') 

  validator_id = fields.Many2one('maya_core.employee', string = 'Resuelta por')
  validation_date_id = fields.Date(string = 'Fecha resolución') 
  reviewer_id = fields.Many2one('maya_core.employee', string = 'Revisada por')
  review_date_id = fields.Date(string = 'Fecha revisión') 
  finisher_id = fields.Many2one('maya_core.employee', string = 'Finalizada por')
  end_date_id = fields.Date(string = 'Fecha finalización') 
  
  validation_type = fields.Selection([
      ('aa', 'Aprobado con Anterioridad'),
      ('co', 'Convalidación'),
      ('ca', 'Aprobado/convalidado previamente'),
      ], string ='Tipo de convalidación', default = 'aa',
      help = "Permite indicar si la convalidación es un aprobado con anterioridad (mismo código de módulo), una convalidación o ya se habia aprobado/convalidado")
  
  mark = fields.Selection([
      ('5', '5'),
      ('6', '6'),
      ('7', '7'),
      ('8', '8'),
      ('9', '9'),
      ('10', '10'),
      ('CO', 'CO')
      ], string ="Nota")
  
  comments = fields.Text(string = 'Comentarios / Razón rechazo',
                         help = 'Ciclo aportado, centro donde se cursó, titulación de inglés aportada...')
  # accepted = fields.Boolean(default = False)
  accepted = fields.Selection([
      ('1', 'Sí'),
      ('2', 'No')
      ], string = "Aceptada")
  
  state = fields.Selection(selection = '_populate_state', 
                           string ='Estado de la convalidación', default = '0')
  
  # almacena los mismos datos de state, pero permite visualizar (sin cambiar), de manera que
  # aunque el usuario no tenga permisos para poner ese estado, si podrá verlo
  state_read_only = fields.Selection(VALIDATION_SUBJECTS_STATES, 
                           string ='Estado de la convalidación', compute = '_compute_state_read_only')
  
  validation_reason = fields.Selection([
      ('FOLRL', 'Ciclo LOGSE + RL (>30h)'),
      ('B2', 'Título B2 o superior'),
      ('IDI', 'Grado/Licenciatura en Filología o Traducción'),
      ('AA', 'Común con otro ciclo formativo (AA)'),
      ('OCF', 'Otro(s) módulo(s) de Ciclo Formativo'),
      ('AUC', 'Aporta todas las Unidades de Competencia'),
      ('CPM', 'Convalidada previamente por el Ministerio'),
      ], string ='Razón de la convalidación', 
      help = "Permite indicar el motivo por el que acepta o deniega la convalidación")
  
  correction_reason = fields.Selection([
    ('ANC', 'Anexo no cumplimentado correctamente. Campos obligatorios no rellenados.'),
    ('ANP', 'Anexo no cumplimentado correctamente. Tipo (convalidación/aprobado con anterioridad) no indicado.'),
    ('SNF', 'Documento no firmado digitalmente'),
    ('RL', 'Ciclo LOGSE: no se aporta curso de riesgo laborales > 30h'),
    ('EXP', 'No se aporta expediente académico'),
    ('TLE', 'No se aporta titulación lengua extranjera'),
    ('NCO', 'Es necesario aportar certificado de los estudios originales.'),
    ('NAI', 'Es necesario indicar el idioma acreditado.'),
    ('NAUC', 'Es necesario aportar unidades de competencia asociadas.'),
    ], string ='Razón de la subsanación',
    help = "Permite indicar el motivo por el que se solicita la subsanación")
  
  is_read_only = fields.Boolean(store = False, compute = '_is_read_only', readonly = False)
    
  def _populate_state(self):
    """
    Rellena el selection en función del grupo al que pertenece el usuario
    """
    choices = VALIDATION_SUBJECTS_STATES.copy()

    # si está en solo lectura se cargan todas para poder visualizar el estado
    """ if self.is_read_only == True:
      return choices """

    # if ordenados por orden de grupos de más importante a menos
    if self.env.user.has_group('maya_core.group_ROOT'): # root todas las opciones
      return choices

    # si ya se ha enviado notificación no puede volver a en proceso
    if self.validation_id.situation == '2' or self.validation_id.situation == '5':
      del choices[0]
    
    if self.env.user.has_group('maya_core.group_MNGT_FP') and int(self.state) == 5 :  # coordinación de FP, en caso de que venga rebotada de secretaria
      del choices[-2:]
    elif self.env.user.has_group('maya_core.group_MNGT_FP'): # coordinación de FP todas menos finalizar, por revisar y cerrar
      del choices[0]  # no se puede asignar el estado sin procesar
      del choices[-5:]
    elif self.env.user.has_group('maya_valid.group_VALID'): # convalidadores, todas menos las 4 últimas
      del choices[-6:]
    elif self.env.user.has_group('maya_core.group_ADMIN') and int(self.state) == 17: # Secretaria en una cnovalidacion con reclamacion resuelta
      del choices[:-6]  # TODO esot es mal!!!
      del choices[-3:]
    elif self.env.user.has_group('maya_core.group_ADMIN'): # Secretaria sólo las tres penúltimas
      del choices[:-6]
      del choices[3]
      del choices[3]
    else: # cualquier otro grupo no tiene opciones
      choices.clear()

    return choices 
  
  def _compute_validation_subject_info(self):
    for record in self:
      record.validation_subject_info = f'[{record.subject_abbr}/{record.course_info}] {record.validation_id.student_surname}, {record.validation_id.student_name}'

  def _compute_student_info(self):
    self.ensure_one()
    self.student_info = f'{self.validation_id.student_surname}, {self.validation_id.student_name}'
  
  @api.depends('state')
  def _compute_state_read_only(self):
    for record in self:
      record.state_read_only = record.state

  @api.onchange('state', 'correction_reason', 'comments')
  def _change_notified_validation(self):
    if self.is_read_only == False and self.validation_id.state == '2' and \
                (self.validation_id.situation == '2' or self.validation_id.situation == '5'):
      if ((self._origin.state == '1' and self.state != '1') or \
           (self._origin.state != '1' and self.state == '1') or \
           (self._origin.state == '1' and 
              (self._origin.correction_reason != self.correction_reason or self._origin.comments != self.comments))):
        self._origin.validation_id.situation = '5'
        return { 'warning': {
              'title': "¡Atención!", 
              'message': "Esta convalidación ya ha sido notificada al estudiante. Cambiar su contenido implica la notificación del cambio en cuanto se realice la grabación"
              }}

  @api.onchange('accepted')
  def _change_mark_competency_validation(self):
    self.ensure_one()
    if self.validation_id.validation_type == 0:
      return
    
    if self.accepted == '1':
      self.mark = 'CO'
      self.validation_reason = 'AUC'
    else:
      self.mark = ''
      self.validation_reason = ''

  def _check_attribute_value(self, field_name, vals) -> bool:
    if isinstance(self._fields[field_name], fields.Char) or \
       isinstance(self._fields[field_name], fields.Text):
      return not ((field_name in vals and (vals[field_name] == '' or vals[field_name] == False)) or \
              (field_name not in vals and (self[field_name] == '' or self[field_name] == False)))
    
    if isinstance(self._fields[field_name], fields.Selection):
      return not ((field_name in vals and vals[field_name] == False) or \
              (field_name not in vals and self[field_name] == False))
    
    return False
 
  def write(self, vals):
    """
    Actualiza en la base de datos un registro
    """
    if 'state' in vals: # si cambia el estado
      state = vals['state']
    else:
      state = self.state

    if 'validation_type' in vals: # si cambia el estado
      validation_type = vals['validation_type']
    else:
      validation_type = self.validation_type

    # si el estado es subsanación tiene que haber una razón
    if state == '1' and not self._check_attribute_value('correction_reason', vals): 
      raise ValidationError(f'La convalidación de {self.subject_id.name} tiene un estado de subsanación y no se ha definido la razón')
    
    # si el estado es instancia superior tiene que haber un comentario  
    if state == '2' and not self._check_attribute_value('comments', vals): 
      raise ValidationError(f'La convalidación de {self.subject_id.name} se ha escalado a un instancia superior y no se ha definido un comentario justificándolo')
  
    if int(state) > 2 and validation_type != 'ca' and \
      not self._check_attribute_value('accepted', vals):
        raise ValidationError(f'No se ha definido si la convalidación de {self.subject_id.name} está aceptada o no.')
    
    if 'accepted' in vals: # si cambia el estado
      accepted = vals['accepted']
    else:
      accepted = self.accepted

    if int(state) > 2 and validation_type == 'ca' and accepted != False:
        raise ValidationError(f'No se puede aceptar o denegar la convalidación de {self.subject_id.name} ya que fue aprobado o convalidado anteriormente')

    if int(state) > 2 and accepted == '1' and \
      (not self._check_attribute_value('mark', vals) or \
        not self._check_attribute_value('validation_reason', vals) or \
        not self._check_attribute_value('validation_type', vals) or \
        not self._check_attribute_value('accepted', vals) or \
        not self._check_attribute_value('comments', vals)):
        raise ValidationError(f'La convalidación de {self.subject_id.name} no ha definido la nota y/o la razón y/o un comentario')
    
    if int(state) > 2 and accepted == '2' and \
      not self._check_attribute_value('comments', vals):
        raise ValidationError(f'La convalidación de {self.subject_id.name} está rechazada pero no se ha definido un comentario')
    
    if int(state) > 2 and validation_type == 'ca':
      vals['mark'] = False
      vals['comments'] = ''
      vals['validation_reason'] = False
    
    # si no es subsanación se elimina la razon
    if state != '1':
      vals['correction_reason'] = False
    
    if state == '0' or state == '1':
      vals['mark'] = False
      vals['accepted'] = False
      vals['validation_reason'] = False
      vals['comments'] = ''

    # datos parala traza de la convalidación
    if 'state' in vals: # si cambia el estado
      state = vals['state']

    if int(state) < 3:
      vals['validator_id'] = False
      vals['validation_date_id'] = False
      vals['reviewer_id'] = False
      vals['review_date_id'] = False
      vals['finisher_id'] = False
      vals['end_date_id'] = False

    today = date.today()
    current_employee = self.env.user.maya_employee_id
    if int(state) == 3:
      vals['validator_id'] = current_employee
      vals['validation_date_id'] = today

    if int(state) == 4:
      vals['reviewer_id'] = current_employee
      vals['review_date_id'] = today

    if int(state) == 5:
      vals['reviewer_id'] = False
      vals['review_date_id'] = False

    if int(state) == 6:
      vals['finisher_id'] = current_employee
      vals['end_date_id'] = today
      
    return super(ValidationSubject, self).write(vals)
  
  def _is_read_only(self):
    """
    Devuelve true o false en función de si la fila que se muestra en la lista
    de convalidaciones es o no de solo lectura
    """
     
    for record in self:
      if self.validation_id.locked:
        record.is_read_only = True
        continue
    
      record.is_read_only = True
      
      if record.env.user.has_group('maya_core.group_ROOT'):
        record.is_read_only = False
    
      if (int(record.state) < 7 or int(record.state) == 9) and self.env.user.has_group('maya_core.group_ADMIN'): 
        record.is_read_only = False
    
      if int(record.state) < 6 and self.env.user.has_group('maya_core.group_MNGT_FP'):
        record.is_read_only = False

      if int(record.state) < 4 and int(record.validation_id.state) < 6 and self.env.user.has_group('maya_valid.group_VALID'):
        record.is_read_only = False 

  """ def _create_validations(self):
    validations_path = self.env['res.config_parameter'].sudo().get_param('validation_path') or None
    if validations_path == None:
        self._logger.error('El directorio de convalidaciones no está definido')
        return
    
    courses = self.env['maya_core.course'].search([])

    # bucle por cada ciclo
    for course in courses:
      validations_path_course = validations_path + '/' + course.abbr
      files = []

      for file_path in os.listdir(validations_path_course):
        if os.path.isfile(os.path.join(validations_path_course, file_path)):
          files.append(file_path) # aunque mejor hacer ya la descompresion, no? """

