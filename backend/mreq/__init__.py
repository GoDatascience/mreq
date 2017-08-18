import multiprocessing

from flask import Flask
from flask_script import Manager
from mrq import context

from mreq import worker

# Flask
app = Flask(__name__)
app.config.from_object('config')

manager = Manager(app)

@manager.command
def runserver():
    # MRQ
    context.setup_context()
    worker.start_workers_in_new_process("SequentialWorker", 1, "sequential")
    worker.start_workers_in_new_process("ParallelWorker", (multiprocessing.cpu_count()-1), "parallel")
    # Flask
    app.run()

from mreq.controllers import index