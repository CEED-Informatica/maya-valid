#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import csv
import sys, argparse

print('\033[1mMaya | create-validation-manually. v1.0\033[0m')

parser = argparse.ArgumentParser(
  description = 'Asocia módulos a una convalidación de un alumno')

# argumentos
parser.add_argument('csv_filename', help = 'Fichero csv con los datos: código del módulo, AA/CO') 
parser.add_argument('-mid', '--mid', required = True, help = 'Identificador de Moodle del alumno. Requerido')
parser.add_argument('-exp', '--dossier', default = '', help = 'Solicita espediente académico')
parser.add_argument('-t', '--type', default = 0, help = 'Tipo de convalidación. 0 (Estudios) / 1 (Competencias). Por defecto: 0')
parser.add_argument('-u', '--url', default = 'http://localhost', help = 'URL del servidor Odoo. Por defecto: http://localhost')
parser.add_argument('-p', '--port', default = '8069', help = 'Puerto del servidor Odoo. Por defecto: 8069')
parser.add_argument('-db', '--database', required = True, help = 'Base de datos. Requerido')
parser.add_argument('-sr', '--user', default = 'admin', help = 'Usuario administrador Odoo. Por defecto: admin')
parser.add_argument('-ps', '--password', default = 'admin', help = 'Contraseña usuario administrador Odoo. Por defecto: admin')

args = parser.parse_args()

url = args.url + ':' + args.port
db = args.database
username = args.user
password = args.password
moodle_id = args.mid
val_type = args.type
dossier = args.dossier

try:
  # end point xmlrpc/2/common permite llamadas sin autenticar
  print('\033[0;32m[INFO]\033[0m Conectando con',url, ' -> ', db)
  common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
  print('\033[0;32m[INFO]\033[0m Odoo server', common.version()['server_version'])
  
  # autenticación
  uid = common.authenticate(db, username, password, {})

except Exception as e:
  print('\033[0;31m[ERROR]\033[0m ' + str(e))
  print('\033[0;31m[ERROR]\033[0m Compruebe que el servidor de Odoo esté arrancado')
  print(f'\033[0;32m[INFO]\033[0m Saliendo...')
  exit()

subjects = []
with open(args.csv_filename) as csv_file:
  csv_reader = csv.reader(csv_file, delimiter = ',')
  line_count = 0
  for row in csv_reader:
    if line_count > 0:
      subjects.append({
          'code': row[0],
          'type': row[1],
      })
    line_count += 1

print('\033[0;32m[INFO]\033[0m Módulos solicitados:', len(subjects))    

try:
  models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

  # Localizando al usuario
  maya_user = models.execute_kw(db, uid, password, 'maya_core.student', 'search_read', [[['moodle_id','=', moodle_id]]], { 'fields': ['id', 'name', 'surname']})
  print(f'\033[0;32m[INFO]\033[0m Estudiante:', maya_user[0]['name'], maya_user[0]['surname'])
  
  # Localizando la convalidacion
  validation = models.execute_kw(db, uid, password, 'maya_valid.validation', 'search_read', [[['student_id','=', maya_user[0]['id']]]], { 'fields': ['id', 'course_abbr', 'state']})
  print(f'\033[0;32m[INFO]\033[0m Convalidación:', validation[0]['course_abbr'], '|', validation[0]['state'])
  
  confirm = input('¿Desea continuar? (s/n) ')

  if confirm.upper() != 'S':
    print('\033[0;31m[ERROR]\033[0m Proceso de actualización de la convalidación cancelado')
    exit()

  # creando los módulo solicitados
  print(f'\033[0;32m[INFO]\033[0m Creando convalidaciones de módulos')
  for sub in subjects:
    subject = models.execute_kw(db, uid, password, 'maya_core.subject', 'search_read', [[['code','=', sub['code']]]], { 'fields': ['id', 'code', 'name']})
    print(f'\033[0;32m[INFO]\033[0m\t', subject[0]['code'], '|', subject[0]['name'])

    valid_subject = {
        'validation_id': validation[0]['id'],
        'subject_id': subject[0]['id'],
        'state': '0',
        'validation_type': sub['type'].lower()
      }

    subject_val = models.execute_kw(db, uid, password, 'maya_valid.validation_subject', 'create', [valid_subject])
  
  # actualizando la convalidación
  update_validation =  {'correction_reason': False,  'correction_date': False }
  if dossier:
    update_validation['situation'] = '6'

  update_validation_id = models.execute_kw(db, uid, password, 'maya_valid.validation', 'write', [[validation[0]['id']],
                                           update_validation]) 
  
  # actualizando expediente
  dossier_list = dossier.split(',')

  for dos in dossier_list:
    dossier_id = models.execute_kw(db, uid, password, 'maya_valid.academic_record', 'create', [{
      'validation_id': validation[0]['id'],
      'state': '0',
      'info': dos.strip() 
    }])

except Exception as e:
  print('\033[0;31m[ERROR]\033[0m ' + str(e))
  print(f'\033[0;32m[INFO]\033[0m Saliendo...')
  exit()