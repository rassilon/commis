import os

import chef
from django.conf import settings
from django.db import models
from django_extensions.db.fields import UUIDField, CreationDateTimeField

from commis.api import conf
from commis.api.models import Client
from commis.db import update
from commis.utils import json

class NodeManager(models.Manager):
    def from_dict(self, data):
        chef_node = chef.Node.from_search(data)
        node, created = self.get_or_create(name=chef_node.name)
        node.automatic_data = json.dumps(chef_node.automatic)
        node.override_data = json.dumps(chef_node.override)
        node.normal_data = json.dumps(chef_node.normal)
        node.default_data = json.dumps(chef_node.default)
        node.save()
        node.run_list.all().delete()
        for entry in chef_node.run_list:
            if '[' not in entry:
                continue # Can't parse this
            type, name = entry.split('[', 1)
            name = name.rstrip(']')
            node.run_list.create(type=type, name=name)
        return node


class Node(models.Model):
    name = models.CharField(max_length=1024, unique=True)
    automatic_data = models.TextField()
    override_data = models.TextField()
    normal_data = models.TextField()
    default_data = models.TextField()

    objects = NodeManager()

    @property
    def automatic(self):
        if not self.automatic_data:
            return {}
        return json.loads(self.automatic_data)

    @property
    def override(self):
        if not self.override_data:
            return {}
        return json.loads(self.override_data)

    @property
    def normal(self):
        if not self.normal_data:
            return {}
        return json.loads(self.normal_data)

    @property
    def default(self):
        if not self.default_data:
            return {}
        return json.loads(self.default_data)

    def to_dict(self):
        chef_node = chef.Node(self.name, skip_load=True)
        chef_node.automatic = self.automatic
        chef_node.override = self.override
        chef_node.normal = self.normal
        chef_node.default = self.default
        chef_node.run_list = [unicode(entry) for entry in self.run_list.all()]
        return chef_node

    def expand_run_list(self):
        recipes = []
        for entry in self.run_list.all().order_by('id'):
            if entry.type == 'role':
                pass # Do role lookup here
            elif entry.type == 'recipe':
                if entry.name not in recipes:
                    recipes.append(entry.name)
        return recipes


class NodeRunListEntry(models.Model):
    node = models.ForeignKey(Node, related_name='run_list')
    name = models.CharField(max_length=1024)
    type = models.CharField(max_length=1024, choices=[('recipe', 'Recipe'), ('role', 'Role')])

    def __unicode__(self):
        return u'%s[%s]'%(self.type, self.name)
