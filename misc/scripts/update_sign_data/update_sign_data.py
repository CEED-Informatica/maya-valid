#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xmlrpc.client
import csv
import sys, argparse

print('\033[1mMaya | update-sign-data. v1.0\033[0m')

parser = argparse.ArgumentParser(
  description = 'Actualiza el campo de firma digital en caso de problemas con pdf-signature-validator')

# argumentos
parser.add_argument('csv_filename', help = 'Fichero csv con los datos: moodle_id') 
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

moodle_ids = []

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

with open(args.csv_filename) as csv_file:
  csv_reader = csv.reader(csv_file, delimiter = ',')
  line_count = 0
  for row in csv_reader:
    if line_count > 0:
      moodle_ids.append({
          'id': row[0],
      })
    line_count += 1

print('\033[0;32m[INFO]\033[0m Usuarios en csv:', len(moodle_ids))    

try:
  models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

  for moodle_id in moodle_ids:
    print(f'\033[0;32m[INFO]\033[0m Actualizando firma para usuario moodle {moodle_id["id"]}')

    user = models.execute_kw(db, uid, password, 'maya_core.student', 'search_read', [[('moodle_id','=',moodle_id['id'])]] )
    print(f'\033[0;32m[INFO]\033[0m   Usuario ({user[0]["nia"]}) {user[0]["surname"]}, {user[0]["name"]}    @:{user[0]["email"]}')
   
    validation = models.execute_kw(db, uid, password, 'maya_valid.validation', 'search_read', [[('student_id','=',user[0]["id"])]] )
    print(f'\033[0;32m[INFO]\033[0m   Convalidacion ({validation[0]}) ')
    sign_data = '{"success": true, "CN": "' + user[0]["surname"] + ', ' + user[0]["name"] + ' (MAYA AUTENTICACI\u00d3N)"}'
    # print(sign_data)
    
    models.execute_kw(db, uid, password, 'maya_valid.validation', 'write', [[validation[0]['id']], {"sign_data": sign_data}])

    # validation = models.execute_kw(db, uid, password, 'maya_valid.validation', 'search_read', [[('student_id','=',user[0]["id"])]] )
    # print(f'\033[0;32m[INFO]\033[0m   Convalidacion ({validation[0]}) ')

except Exception as e:
  print('\033[0;31m[ERROR]\033[0m ' + str(e))
  print(f'\033[0;32m[INFO]\033[0m Saliendo...')
  exit()