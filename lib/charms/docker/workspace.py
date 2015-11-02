import os

class Workspace:
    '''
    Docker workspaces are unique in our world, as they can be one of two context
    dependent things: A Docker build directory, containing only a single
    Dockerfile, or they can be part of a formation using docker-compose in which
    they warehouse a docker-compose.yml file.

    Under most situations we only care about the context the charm author wishes
    to be in, and what implications that has on the workspace to be valid.

    This method simply exposes an overrideable object to determine these
    characteristics.
    '''
    def __init__(self, path, context="compose"):
        self.path = path
        self.context = context

    def __str__(self):
        return self.path

    def __repr__(self):
        return self.path

    def validate(self):
        dcyml = os.path.isfile("{}/docker-compose.yml".format(self.path))
        dcyaml = os.path.isfile("{}/docker-compose.yaml".format(self.path))
        dfile = os.path.isfile("{}/Dockerfile".format(self.path))

        if self.context == "compose":
            if not dcyml and not dcyaml:
                msg = "Missing yaml definition: docker-compose.yml"
                raise OSError(msg)
        else:
            if not dfile:
                msg = "Missing Dockerfile"
                raise OSError(msg)
        return True
