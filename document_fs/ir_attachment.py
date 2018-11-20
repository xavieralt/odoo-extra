import glob
import logging
import os
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ir_attachment(models.Model):
    _name = "ir.attachment"
    _inherit = 'ir.attachment'

    document_fs_path = fields.Char('Fs path', compute='_get_document_fs_path')

    def _document_fs_sanitize(self, name):
        if isinstance(name, bytes):
            try:
                name = name.decode('utf-8')
            except UnicodeDecodeError:
                name = ''
        name = name.replace('/', '')
        name = re.sub('^[.]+', '', name)
        return name

    @api.depends('res_model', 'res_id', 'datas_fname')
    def _get_document_fs_path(self):
        for attachment in self:
            link_dir = os.path.join(self._filestore(), 'file', 'models')
            res_model = self._document_fs_sanitize(attachment.res_model or '')
            res_id = self._document_fs_sanitize(str(attachment.res_id))
            datas_fname = self._document_fs_sanitize(attachment.datas_fname or '')
            if not (datas_fname and res_model and res_id):
                attachment.document_fs_path = ''
                continue
            link_path = os.path.join(link_dir, res_model, res_id, datas_fname)
            attachment.document_fs_path = link_path

    def _document_fs_unlink(self):
        for attachment in self:
            if os.path.isfile(attachment.document_fs_path or ''):
                os.unlink(attachment.document_fs_path)

    def _document_fs_link(self):
        for attachment in self:
            src = self._full_path(attachment.store_fname or '')
            path = attachment.document_fs_path
            if not src or not path:
                continue
            link_dir = os.path.dirname(path)
            if not os.path.isdir(link_dir):
                os.makedirs(link_dir)
            os.link(src, path)

    def _document_fs_sync(self):
        # WARNING files must be atomically renamed(2) if used in a cron job as
        # we read and unlink them
        if self._storage() == 'file':
            link_dir = os.path.join(self._filestore(), 'file', 'models')
            l = glob.glob('%s/*/*/*' % link_dir)
            for path in l:
                if not os.path.isfile(path):
                    continue
                (p, fname) = os.path.split(path)
                (p, res_id) = os.path.split(p)
                (p, res_model) = os.path.split(p)
                try:
                    name = unicode(fname,'utf-8')
                except UnicodeError:
                    continue
                if res_model in self.pool:
                    if not self.search([
                            ('res_model','=',res_model),
                            ('res_id','=',res_id),
                            ('datas_fname','=',name)
                        ]):
                        continue
                    data = open(path).read().encode('base64')
                    os.unlink(path)
                    attachment = {
                        'res_model': res_model,
                        'res_id': res_id,
                        'name': name,
                        'datas_fname': name,
                        'datas': data,
                    }
                    self.create([attachment])

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super(ir_attachment, self).create(vals_list)
        if self._storage() == 'file':
            attachments._document_fs_link()
        return attachments

    @api.multi
    def write(self, vals):
        if self._storage() == 'file':
            self._document_fs_unlink()
        r = super(ir_attachment, self).write(vals)
        if self._storage() == 'file':
            self._document_fs_link()
        return r

    @api.multi
    def unlink(self):
        if self._storage() == 'file':
            self._document_fs_unlink()
        return super(ir_attachment, self).unlink()

# vim:et:
