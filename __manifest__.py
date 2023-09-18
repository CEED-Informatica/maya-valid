# -*- coding: utf-8 -*-
{
    'name': "Maya | Convalidaciones",
    'version': '0.1.0a',

    'summary': """
        Extensión de Maya | Core para la gestión de convalidaciones""",

    'description': """
        Permite la gestión de las convalidaciones utilizando Moodle como plataforma de entrega y notificación.
         
        Este módulo permite entre otras cosas
         - Asignar convalidadores, revisores
         - Recepcionar las solicitudes desde Moodle
         - Detectar de manera automatica errores de forma: módulos incorrectos, no firmados...
         - Solicitar subsanaciones
         - Notificar al alumno el estado de las solicitudes en Moodle
         - Notificar a Secretaria las convalidaciones pendientes
    """,

    'website': "https://portal.edu.gva.es/ceedcv/",
    'author': 'Alfredo Oltra',
    'maintainer': 'Alfredo Oltra <alfredo.ptcf@gmail.com>',
    'company': '',
    'category': 'Productivity',

    'license': 'AGPL-3',
    # precio del módulo
    'price': 0,

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'maya_core'],

    # always loaded
    'data': [
        # seguridad
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/validation_access.xml',   # politicas de acceso a convalidaciones (reescribe las anteriores)
        # vistas
        'views/views.xml',
        'views/templates.xml',
        'views/config_settings_view.xml',
        # datos de modelos
        'data/config/config_data.xml',
        'data/registered_cron_jobs.xml',
        # reports
        
    ],
    'installable': True,
    'application': True,
}