# -*- coding: utf-8 -*-

import base64
import functools
import io
import json
import logging
import os
import unicodedata

from odoo import http
from odoo.http import content_disposition, request
from odoo.tools import html_escape
from odoo.modules import get_resource_path
import odoo.modules.registry
from odoo.tools.mimetypes import guess_mimetype

try:
    from werkzeug.utils import send_file
except ImportError:
    from odoo.tools._vendor.send_file import send_file


class SammyStaticFile(http.Controller):

    @http.route([
        '/sammi/<string:file>',
        '/sammi/signature',
    ], type='http', auth="none", cors="*")
    def signature_email(self, dbname=None, **kw):
        imgname = 'signature'
        imgext = '.jpg'
        placeholder = functools.partial(get_resource_path, 'opsol_sammy', 'static', 'img')
        dbname = request.db
        uid = (request.session.uid if dbname else None) or odoo.SUPERUSER_ID

        if not dbname:
            response = http.Stream.from_path(placeholder(imgname + imgext)).get_response()
        else:
            try:
                # create an empty registry
                registry = odoo.modules.registry.Registry(dbname)
                with registry.cursor() as cr:
                    company = int(kw['company']) if kw and kw.get('company') else False
                    if company:
                        cr.execute("""SELECT signature, write_date
                                        FROM res_company
                                       WHERE id = %s
                                   """, (company,))
                    else:
                        cr.execute("""SELECT c.signature, c.write_date
                                        FROM res_users u
                                   LEFT JOIN res_company c
                                          ON c.id = u.company_id
                                       WHERE u.id = %s
                                   """, (uid,))
                    row = cr.fetchone()
                    if row and row[0]:
                        image_base64 = base64.b64decode(row[0])
                        image_data = io.BytesIO(image_base64)
                        mimetype = guess_mimetype(image_base64, default='image/png')
                        imgext = '.' + mimetype.split('/')[1]
                        if imgext == '.svg+xml':
                            imgext = '.svg'
                        response = send_file(image_data, request.httprequest.environ,
                                             download_name=imgname + imgext, mimetype=mimetype, last_modified=row[1])
                    else:
                        response = http.Stream.from_path(placeholder('nologo.png')).get_response()

            except Exception:
                response = http.Stream.from_path(placeholder(imgname + imgext)).get_response()

        return response
