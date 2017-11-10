import os

from datetime import datetime

from flask_security import RoleMixin, UserMixin
from mongoengine import *
from werkzeug.security import gen_salt

from pyor.celery.states import PENDING
from pyor.models.eve_support import VersionedReferenceField
from pyor.models.constants import *


class Role(Document, RoleMixin):
    name = StringField(max_length=80, unique=True)
    description = StringField(max_length=255)
    allowed_scopes = ListField(StringField(choices=ALL_SCOPES))


class User(Document, UserMixin):
    name = StringField(max_length=255)
    email = StringField(max_length=255, unique=True, required=True)
    password = StringField(max_length=255, required=True)
    active = BooleanField(default=True)
    confirmed_at = DateTimeField(api_readonly=True)
    roles = ListField(ReferenceField(Role), default=[])

    def get_security_payload(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email
        }


class Client(Document):
    name = StringField()
    client_id = StringField(unique=True, required=True, default=lambda:gen_salt(40))
    client_secret = StringField()
    confidential = BooleanField(default=False)
    redirect_uris = ListField(StringField())
    default_scopes = ListField(StringField(choices=ALL_SCOPES))
    allowed_grant_types = ListField(StringField(choices=GRANT_TYPES))

    @property
    def client_type(self):
        if self.confidential:
            return 'confidential'
        return 'public'

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]


class Token(Document):
    client = ReferenceField(Client)
    user = ReferenceField(User, required=True)
    access_token = StringField(unique=True, required=True)
    refresh_token = StringField(unique=True)
    token_type = StringField(default="bearer")
    expires = DateTimeField()
    scopes = ListField(StringField())

    @property
    def client_id(self) -> str:
        return self.client.client_id

    @property
    def user_id(self) -> str:
        return str(self.user.id)


class FileSource(Document):
    filename = StringField(required=True)
    original_filename = StringField()
    filepath = StringField(required=True)
    length = LongField(required=True, min_value=0)
    md5 = StringField()
    content_type = StringField()
    upload_date = DateTimeField(default=datetime.utcnow)


class Queue(Document):
    name = StringField(required=True, unique=True)


class Worker(Document):
    name = StringField(required=True, unique=True)
    queues = ListField(ReferenceField(Queue))
    num_processes = IntField(min_value=1)

    @property
    def start_command(self):
        return "celery multi start {} -A pyor.celery --loglevel=INFO --events --concurrency={} --queues={} --pidfile={} --logfile={}" \
            .format(self.name, self.num_processes, ",".join([queue.name for queue in self.queues]), self.pidfile,
                    self.logfile)

    @property
    def pidfile(self):
        return os.path.join(os.environ["PYOR_RUN"], "%n.pid")

    @property
    def logfile(self):
        return os.path.join(os.environ["PYOR_LOG"], "%n%I.log")


class ParamDefinition(EmbeddedDocument):
    name = StringField(required=True)
    type = StringField(required=True, choices=("text", "number", "date", "boolean"))


class TaskFile(Document):
    data = ReferenceField(FileSource)


class Task(Document):
    name = StringField(required=True, unique=True)
    script_file = ReferenceField(TaskFile, required=True)
    auxiliar_files = ListField(ReferenceField(TaskFile))
    param_definitions = ListField(EmbeddedDocumentField(ParamDefinition))
    _version = IntField(api_autogenerated=True, db_field=VERSION)
    _latest_version = IntField(api_autogenerated=True, db_field=LATEST_VERSION)
    # Ignore
    _id_document = ObjectIdField(api_autogenerated=True, db_field=ID_FIELD+VERSION_ID_SUFFIX)

    @property
    def dirpath(self):
        return os.path.join(os.environ["PYOR_DATA"], "tasks", str(self.id))


class Experiment(Document):
    task = VersionedReferenceField(Task, required=True)
    params = DictField()
    queue = ReferenceField(Queue, required=True)
    status = StringField(default=PENDING, api_readonly=True)
    result = DynamicField(api_readonly=True)
    result_files = ListField(ReferenceField(FileSource), api_readonly=True)
    retry_count = IntField(default=0, api_readonly=True)
    date_received = DateTimeField(api_readonly=True)
    date_started = DateTimeField(api_readonly=True)
    date_last_update = DateTimeField(api_readonly=True)
    date_done = DateTimeField(api_readonly=True)
    traceback = StringField(api_readonly=True)
    children = DynamicField(api_readonly=True)
    progress = FloatField(min_value=0.0, max_value=1.0, api_readonly=True)
