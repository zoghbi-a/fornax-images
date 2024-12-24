import logging
import subprocess
import sys
import os
import glob


class Builder:
    """Base class for running system commands and logging

    this class only exists (instead of module-level functions) to make unit
    testing less painful; it is also used by "release.py"
    """
    def __init__(self, logger, dryrun=False):
        """Create a new TaskRunner
        
        Parameters:
        -----------
        logger: logging.Logger
            Logging object
        dryrun: bool
            If True, print the commands without running them
        
        """
        self.logger = logger
        self.dryrun = dryrun

    def out(self, msg, severity=logging.INFO):
        """Log progress message
        
        Parameters
        ----------
        msg: str
            Message to log
        severity: int
            Logging level: logging.INFO, DEBUG, ERROR etc.

        """
        self.logger.log(severity, msg)
        sys.stdout.flush()

    def run(self, command, timeout, **runargs):
        """Run system command {command}
        
        Parameters:
        -----------
        command: str
            Command to pass to subprocess.run()
        timout: int
            Timeout in sec
        **runargs:
            to be passed to subprocess.run
        
        """
        self.out(f"Running (timeout: {timeout})::\n{command}")
        result = None
        if not self.dryrun:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                text=True,
                timeout=timeout,
                **runargs,
            )
        return result
    
    def build( self, repo, image, tag, build_args=None, build_pars=None):
        """Build an image by called 'docker build'
        
        Parameters:
        -----------
        repo: str
            repository name
        image: str
            path to the image folder (e.g. tractor or heasoft)
        tag: str
            a tag name for the image
        build_args: list
            A list of str arguments to be passed directly to 'docker build'. e.g.
            'SOME_ENV=myvalue'
        build_pars: str
            Extra command line arguments to be passed to 'docker build'
            e.g. '--no-cache --network=host'
        
        """
        cmd_args = []
    
        # build_args is a list
        build_args = build_args or []
        if not isinstance(build_args, list):
            raise ValueError(f'build_args is of type {type(build_args)}. Expected a list.')
        if ':' in tag:
            tag = tag.rsplit(':', 1)[1]
        
        # Ensure we have: name=value
        build_args = [arg.strip() for arg in build_args]
        
        # add passed parameters to build_args
        mapping = {
            'REPOSITORY': repo,
            'IMAGE_TAG': tag,
        }
        for key,val in mapping.items():
            if not any([arg.startswith(f'{key}=') for arg in build_args]):
                build_args.append(f'{key}={val}')

        # loop through the build_args and add them extra_args
        for arg in build_args:
            if not arg.count("=") == 1:
                raise ValueError(
                    f"build_args should be of the form 'name=value'. "
                    f"Got '{arg}'."
                )
            name, val = arg.split("=", 1)
            cmd_args.append(f"--build-arg {name}={val}")

        # now add any other line parameters
        if build_pars:
            cmd_args.append(build_pars)

        cmd_args = " ".join(cmd_args)
        build_cmd = f"docker build {cmd_args} --tag {tag} {image}"
        self.out(f"Building {image} ...")
        result = self.run(build_cmd, timeout=10000)

    def push(self, tag):
        """Push the image with 'docker push'
        
        Parameters:
        -----------
        tag: str
            a tag name for the image of the form: repo:tag

        """
        if not isinstance(tag, str) or ':' not in tag:
            raise ValueError(f'tag: {tag} is not a str the form repo:tag')
        push_command = f'docker push {tag}'
        self.out(f"Pushing {tag} ...")
        result = self.run(push_command, timeout=1000)

    def remove_lockfiles(self, image):
        """Remove conda lock files from image
        
        Parameters
        ----------
        image: str
            name of the image folder containing Dockerfile and lockfiles if any.
        """
        self.out(f"Removing the lock files for {image}")
        lockfiles = glob.glob(f"{image}/conda-*lock.yml")
        for lockfile in lockfiles:
            self.out(f"Removing {image}/{lockfile}")
            os.unlink(lockfile)


if __name__ == '__main__':
    
    logger = logging.getLogger('::Builder::')
    logging.basicConfig(level=logging.DEBUG)
    builder = Builder(logger, dryrun=True)
    builder.build('fornax-images', 'tractor', 'some-tag')