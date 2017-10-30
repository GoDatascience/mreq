import os

from datetime import datetime
from typing import Type

import mongoengine
from pyor.utils import document_etag

from pyor.celery.states import PENDING
from mongoengine import *

connect(os.environ["MONGO_DBNAME"], host=os.environ["MONGO_HOST"], port=int(os.environ["MONGO_PORT"]))

LAST_UPDATED = "_updated"
DATE_CREATED = "_created"
ETAG = "_etag"

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
        return "celery multi start {} -A pyor.celery --loglevel=INFO --events --concurrency={} --queues={} --pidfile={} --logfile={}"\
            .format(self.name, self.num_processes, ",".join([queue.name for queue in self.queues]), self.pidfile, self.logfile)

    @property
    def pidfile(self):
        return os.path.join(os.environ["PYOR_RUN"], "%n.pid")

    @property
    def logfile(self):
        return os.path.join(os.environ["PYOR_LOG"], "%n%I.log")


class ParamDefinition(EmbeddedDocument):
    name = StringField(required=True)
    type = StringField(required=True, choices=("text", "number", "date", "boolean"))


class TaskFiles(Document):
    script_file = ReferenceField(FileSource)
    auxiliar_files = ListField(ReferenceField(FileSource))


class Task(Document):
    name = StringField(required=True, unique=True)
    files = ReferenceField(TaskFiles)
    param_definitions = ListField(EmbeddedDocumentField(ParamDefinition))

    @property
    def dirpath(self):
        return os.path.join(os.environ["PYOR_DATA"], "tasks", str(self.id))


class Experiment(Document):
    task = ReferenceField(Task, required=True)
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


def last_updated_hook(sender : Type[Document], document: Document, **kwargs):
    """
    Hook which updates LAST_UPDATED field before every Document.save() call.
    """

    field_name = LAST_UPDATED.lstrip('_')
    if field_name in document._fields:
        document[field_name] = datetime.utcnow()

def etag_hook(sender: Type[Document], document:Document, **kwargs):
    """
    Hook which updates ETAG field before every Document.save() call.
    """

    field_name = ETAG.lstrip('_')
    if field_name in document._fields:
        etag = document_etag(document.to_mongo(), ignore_fields=["_SON__keys"])
        document[field_name] = etag

def patch_model_class(model_cls: Type[Document]):
    """
    Internal method invoked during registering new model.

    Adds necessary fields (updated, created and etag) into model class
    to ensure Eve's default functionality.

    This is a helper for correct manipulation with mongoengine documents
    within Eve. Eve needs 'updated' and 'created' fields for it's own
    purpose, but we cannot ensure that they are present in the model
    class. And even if they are, they may be of other field type or
    missbehave.

    :param model_cls: mongoengine's model class (instance of subclass of
                      :class:`mongoengine.Document`) to be fixed up.
    """

    # field names have to be non-prefixed
    last_updated_field_name = LAST_UPDATED.lstrip('_')
    date_created_field_name = DATE_CREATED.lstrip('_')
    etag_field_name = ETAG.lstrip('_')

    new_fields = {
        last_updated_field_name: DateTimeField(db_field=LAST_UPDATED,
                                                default=datetime.utcnow),
        date_created_field_name: DateTimeField(db_field=DATE_CREATED,
                                                default=datetime.utcnow),
        etag_field_name: StringField(db_field=ETAG)
    }

    for attr_name, attr_value in new_fields.items():
        # If the field does exist, we just check if it has right
        # type (mongoengine.DateTimeField) and pass
        if attr_name in model_cls._fields:
            attr_value = model_cls._fields[attr_name]
            if not isinstance(attr_value, type(attr_value)):
                info = (attr_name, attr_value.__class__.__name__)
                raise TypeError("Field '%s' is needed by Eve, but has"
                                " wrong type '%s'." % info)
            continue
        # The way how we introduce new fields into model class is copied
        # out of mongoengine.base.DocumentMetaclass
        attr_value.name = attr_name
        if not attr_value.db_field:
            attr_value.db_field = attr_name
        # TODO: reverse-delete rules
        attr_value.owner_document = model_cls

        # now add a flag that this is automagically added field - it is
        # very useful when registering class more than once - create_schema
        # has to know, if it is user-added or auto-added field.
        attr_value.eve_field = True

        # now simulate DocumentMetaclass: add class attributes
        setattr(model_cls, attr_name, attr_value)
        model_cls._fields[attr_name] = attr_value
        model_cls._db_field_map[attr_name] = attr_value.db_field
        model_cls._reverse_db_field_map[attr_value.db_field] = attr_name

        # this is just copied from mongoengine and frankly, i just dont
        # have a clue, what it does...
        created = [(v.creation_counter, v.name) for v in model_cls._fields.values()]
        model_cls._fields_ordered = tuple(i[1] for i in sorted(created))

# Needed because the worker process doesn't call the pyor.api.mapper.register_resource()
patch_model_class(Queue)
patch_model_class(Worker)
patch_model_class(TaskFiles)
patch_model_class(Task)
patch_model_class(Experiment)

mongoengine.signals.pre_save.connect(last_updated_hook)
mongoengine.signals.pre_save.connect(etag_hook)