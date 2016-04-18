from charmtools.build.tactics import WheelhouseTactic


class DockerWheelhouseTactic(WheelhouseTactic):
    def __call__(self, venv=None):
        # this was due to some weird scoping issue during execution.
        # investigate more later
        from charmtools import utils
        create_venv = venv is None
        venv = venv or path(tempfile.mkdtemp())
        pip = venv / 'bin' / 'pip3'
        wheelhouse = self.target.directory / 'wheelhouse'
        wheelhouse.mkdir_p()
        if create_venv:
            utils.Process(('virtualenv', '--python', 'python3', venv)).exit_on_error()()
            utils.Process((pip, 'install', '-U', 'pip', 'wheel')).exit_on_error()()
        utils.Process((pip, 'install', '-U', 'setuptools')).exit_on_error()()  # custom bit
        for tactic in self.previous:
            tactic(venv)
        self._add(pip, wheelhouse, '-r', self.entity)
        if create_venv:
            venv.rmtree_p()
