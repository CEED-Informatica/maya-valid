# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.exceptions import ValidationError

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
import os
import pathlib
import shutil
from ..support import helper
import base64
import logging

from datetime import date, timedelta, datetime

from ...maya_core.support.maya_logger.exceptions import MayaException


_logger = logging.getLogger(__name__)

class Course(models.Model):
  """
  Herencia de clase
  Herencia del modelo maya_core.course
  Lo que hace es modificar el modelo maya_core.course para incluir 
  la función create_mbz_validation_tasks
  """
  _inherit = 'maya_core.course'

  def create_mbz_validation_tasks(self):
    """  for re in self:
      print("dio") """

    self.ensure_one()
   
    path_mbz_template = os.path.join(os.path.dirname(__file__), '../misc/moodle/validation_section_mbz')
    path_tmp = os.path.join(os.path.dirname(__file__), '../static/mbz', f'validation_section_{self.abbr}_{self.code}_mbz')

    if not os.path.exists(path_tmp):  
      os.makedirs(path_tmp)

    # calculo de las variables
    current_sy = (self.env['maya_core.school_year'].search([('state', '=', 1)])) # curso escolar actual  

    if len(current_sy) == 0:
      raise MayaException(
          _logger, 
          'No se ha definido un curso actual',
          50, # critical
          comments = '''Es posible que no se haya marcado como actual ningún curso escolar''')
    else:
      current_school_year = current_sy[0]

    new_due_date = current_school_year.date_init_lective + timedelta(days = 30)
    init_due_date_task = current_school_year.date_init_lective - timedelta(days = 2)

    dict_variables =  {
      'desc_term_lan1': f'Del {current_school_year.date_init_lective.day}/{current_school_year.date_init_lective.month} al {new_due_date.day}/{new_due_date.month} (ambos incluidos/tots dos inclosos)',
      'title_annex_lan1': f'Anexo convalidaciones {self.abbr} (es)', 
      'file_annex_lan1': f'Anexo convalidaciones {self.abbr}.pdf',   # (es)
      'date_due': int(datetime(year = init_due_date_task.year, 
                               month = init_due_date_task.month, 
                               day = init_due_date_task.day).timestamp()),
      'date_due_competency': int(datetime(year = init_due_date_task.year + 1, day = 15, month=6).timestamp()),
      'desc_term_competency_lan1': f'15/06/{init_due_date_task.year + 1}'
      }
    
    dict_variables['hash_annex_lan1'], dict_variables['size_annex_lan1'] = self._insert_annex_in_mbz('file_annex_lan1', dict_variables, path_tmp)
    
    try:
      # /misc/moodle/valid_block_mbz/aula_valid
      env = Environment(
        loader = FileSystemLoader(path_mbz_template),
        autoescape = select_autoescape())

      for path, subdirs, files in os.walk(path_mbz_template):
        for name in files:
          try:
            full_path = pathlib.PurePath(path, name)
            path_file_tmp = os.path.join(path_tmp, os.path.relpath(full_path, path_mbz_template))

            path_rel = os.path.relpath(full_path, path_mbz_template)
            template = env.get_template(path_rel)

            if not os.path.exists(os.path.join(path_tmp, os.path.relpath(path, path_mbz_template))):  
              os.makedirs(os.path.join(path_tmp, os.path.relpath(path, path_mbz_template)))
            
            f = open(path_file_tmp, 'w')
            f.write(template.render(dict_variables))
            f.close()
          except UnicodeDecodeError:
            if not os.path.exists(os.path.join(path_tmp, os.path.relpath(path, path_mbz_template))):  
              os.makedirs(os.path.join(path_tmp, os.path.relpath(path, path_mbz_template)))
            
            shutil.copyfile( full_path, path_file_tmp)  
    except Exception as e:
      print(e.toString())

    zip_name = f'validation_section_{self.abbr}_{self.code}.mbz'
    # cambio del plazo 
    shutil.make_archive(os.path.join(path_tmp[:path_tmp.find('validation_section_')], zip_name), 'zip', path_tmp)
    os.rename(os.path.join(path_tmp[:path_tmp.find('validation_section_')], f'{zip_name}.zip'), os.path.join(path_tmp[:path_tmp.find('validation_section_')], zip_name))

    base_url = self.env['ir.config_parameter'].get_param('web.base.url')

    url = f'{base_url}/maya_valid/static/mbz/{zip_name}'
    return {
      'type': 'ir.actions.act_url',
      'target': 'self',
      'url': url
    }


  def _insert_annex_in_mbz(self, key: str, dict_variables: dict, path_tmp: str) -> str:
    """
    Inserta en la estructura de archivos del mbz los anexos

    Devuelve el sha1 del fichero o None en caso de que la key no este definida
    """
    if key in dict_variables:
      try:
        sha1 = helper.get_sha1_file(os.path.join(os.path.dirname(__file__), f'../misc/pdf/{dict_variables[key]}'))
        size = os.path.getsize(os.path.join(os.path.dirname(__file__), f'../misc/pdf/{dict_variables[key]}'))
        path_file_tmp = os.path.join(path_tmp, 'files', sha1[:2])
        if not os.path.exists(path_file_tmp):  
          os.makedirs(path_file_tmp)
        shutil.copyfile(os.path.join(os.path.dirname(__file__), f'../misc/pdf/{dict_variables[key]}'), os.path.join(path_file_tmp, sha1))  
      except MayaException:
        raise ValidationError('No se puede generar el mbz. Posiblemente no se encuentren los anexos')

      return sha1, size  
    
    else:
      return None

    