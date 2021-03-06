import hashlib

from commis.generic_views import CommisAPIViewBase, api
from commis.exceptions import ChefAPIError
from commis.sandboxes.models import Sandbox, SandboxFile
from commis.db import update

class SandboxAPIView(CommisAPIViewBase):
    model = Sandbox

    @api('POST', admin=True)
    def create(self, request):
        checksums = request.json['checksums'].keys()
        sandbox = Sandbox.objects.create()
        data = {'uri': self.reverse(request, 'update', sandbox.uuid),
                'sandbox_id': sandbox.uuid, 'checksums': {}}
        for csum in sorted(checksums):
            csum_data = data['checksums'][csum] = {}
            qs = SandboxFile.objects.filter(checksum=csum)
            if qs and qs[0].uploaded:
                csum_data['needs_upload'] = False
            else:
                if qs:
                    sandbox_file = qs[0]
                else:
                    sandbox_file = SandboxFile.objects.create(checksum=csum, created_by=request.client)
                sandbox_file.sandboxes.add(sandbox)
                csum_data['needs_upload'] = True
                csum_data['url'] = self.reverse(request, 'upload', sandbox.uuid, csum)
        return data


    @api('PUT', admin=True)
    def update(self, request, sandbox_id):
        try:
            sandbox = Sandbox.objects.get(uuid=sandbox_id)
        except Sandbox.DoesNotExist:
            raise ChefAPIError(404, 'Sandbox not found')
        if request.json['is_completed']:
            sandbox.commit()
        return {}


    @api('PUT', admin=True)
    def upload(self, request, sandbox_id, checksum):
        try:
            sandbox = Sandbox.objects.get(uuid=sandbox_id)
        except Sandbox.DoesNotExist:
            raise ChefAPIError(404, 'Sandbox not found')
        try:
            sandbox_file = SandboxFile.objects.get(checksum=checksum)
        except SandboxFile.DoesNotExist:
            raise ChefAPIError(404, 'Invalid upload target')
        if sandbox_file.uploaded:
            raise ChefAPIError(500, 'Duplicate upload')
        if sandbox_file.created_by_id != request.client.id:
            raise ChefAPIError(403, 'Upload client mismatch')
        if hashlib.md5(request.raw_post_data).hexdigest() != checksum:
            raise ChefAPIError(500, 'Checksum mismatch')
        update(sandbox_file, content_type=request.META['CONTENT_TYPE'])
        sandbox_file.write(sandbox, request.raw_post_data)
        return {'uri': self.reverse(request, 'upload', sandbox.uuid, checksum)}
