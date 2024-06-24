# -*- coding: utf-8 -*-

from odoo import models, fields
import os
import base64
from odoo.exceptions import ValidationError

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
      
    for course in courses:
      validations = self.env['maya_valid.validation'].search([('course_id', '=', course.id), ('state', '=', 14)], order = 'student_surname asc')
      pdf = self.env.ref('maya_valid.validations_pdf_report')._render_qweb_pdf([val.id for val in validations])[0]
      data = base64.encodestring(pdf)
   
      #sss = os.path.join(os.path.dirname(__file__), f'{course.abbr}.pdf')
      kdb = open(os.path.join(os.path.dirname(__file__), f'{course.abbr}.pdf'), 'wb')
      kdb.write(pdf)
      kdb.close()

  """   
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move', 'company_id'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=get_lang(self.env).code)
        return self.with_context(discard_logo_check=True)._print_report(data) """
