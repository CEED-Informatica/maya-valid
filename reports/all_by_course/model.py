# -*- coding: utf-8 -*-

from odoo import models, fields, tools
import os
import base64
import shutil
from datetime import datetime

class WizardReportAllByCourse(models.TransientModel):
  """
  Wizard para mostrar la configuración del informe de convalidaciones por curso
  """
  _name = 'maya_valid.report_all_by_course_wizard' 

  # lo normal seria que fuera un one2many, pero no es posible referenciar un trnsient con un model normal
  # así que la mejor solución es optar por un many2many que no requiere la referencia en el otro modelo
  courses_ids = fields.Many2many('maya_core.course', string = 'Ciclo Formativo')
  all_courses = fields.Boolean(string = 'Todos los ciclos', default = False)

  def generate_report(self):
    self.ensure_one()

    if len(self.courses_ids) == 0 and not self.all_courses:
      return
    
    if self.all_courses == True: 
      courses = self.env['maya_core.course'].search([])
    else:
      courses = self.courses_ids 
      
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    addons_path = max([path for path in tools.config['addons_path'].split(',') if path in os.path.dirname(__file__)], key = len)

    if len(courses) == 1:
      now = ''
    else:
       os.makedirs(os.path.join(addons_path, 'maya_core','tmp_files', 'reports', now))

    for course in courses:
      validations = self.env['maya_valid.validation'].search([('course_id', '=', course.id), ('state', '=', 14)], order = 'student_surname asc')

      pdf = self.env.ref('maya_valid.validations_pdf_report')._render_qweb_pdf([val.id for val in validations])[0]
      data = base64.encodestring(pdf)
   
      path_tmp = os.path.join(addons_path, 'maya_core/tmp_files/reports', now, f'Convalidaciones_cerradas_{course.abbr}.pdf')
      kdb = open(path_tmp, 'wb')
      kdb.write(pdf)
      kdb.close()

    base_url = self.env['ir.config_parameter'].get_param('web.base.url')
    
      
    if len(courses) > 1:
      path_tmp = os.path.join(addons_path, 'maya_core/tmp_files/reports', now)
      zip_name = os.path.join(f'{addons_path}/maya_core/static/reports', f'Convalidaciones_cerradas_{now}')
      shutil.make_archive(zip_name, 'zip', path_tmp)
      url = f'{base_url}/maya_core/static/reports/Convalidaciones_cerradas_{now}.zip'
    else:
      filename = os.path.join(f'{addons_path}/maya_core/static/reports', f'Convalidaciones_cerradas_{courses[0].abbr}.pdf')
      shutil.copy(path_tmp, filename)
      url = f'{base_url}/maya_core/static/reports/Convalidaciones_cerradas_{courses[0].abbr}.pdf'

    return {
      'type': 'ir.actions.act_url',
      'target': 'self',
      'url': url
    }

  """   
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'company_id'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=get_lang(self.env).code)
        return self.with_context(discard_logo_check=True)._print_report(data) """
