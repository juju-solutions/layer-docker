from charmtools.build.tactics import WheelhouseTactic
from charmtools.utils import Process
import tempfile
from path import Path as path


class DockerWheelhouseTactic(WheelhouseTactic):
    ''' The references to process, path, and tempfile are implicit
    below because  they come from the global scope of
    charmtools.utils which gets passed in during
    charmtools.utils.load_class
    Investigate there if there is abrupt breakage here.
    '''
    def __call__(self, venv=None):
        create_venv = venv is None
        venv = venv or path(tempfile.mkdtemp())
        pip = venv / 'bin' / 'pip3'
        wheelhouse = self.target.directory / 'wheelhouse'
        wheelhouse.mkdir_p()
        if create_venv:
            Process(('virtualenv', '--python', 'python3', venv)).exit_on_error()()  # noqa
            Process((pip, 'install', '-U', 'pip', 'wheel')).exit_on_error()()  # noqa
        Process((pip, 'install', '-U', 'setuptools')).exit_on_error()()  # noqa
        for tactic in self.previous:
            tactic(venv)
        self._add(pip, wheelhouse, '-r', self.entity)
        if create_venv:
            venv.rmtree_p()
