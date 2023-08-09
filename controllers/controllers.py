# -*- coding: utf-8 -*-
# from odoo import http


# class MayaValid(http.Controller):
#     @http.route('/maya/maya/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/maya/maya/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('maya.listing', {
#             'root': '/maya/maya',
#             'objects': http.request.env['maya.maya'].search([]),
#         })

#     @http.route('/maya/maya/objects/<model("maya.maya):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('maya.object', {
#             'object': obj
#         })