import logging
import subprocess
import sys
import os
import glob
import re


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
    
    def build( self, repo, image, tag, build_args=None, extra_args=None):
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
        extra_args: str
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
        if extra_args:
            cmd_args.append(extra_args)

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

    def update_lockfiles(self, image, tag, extra_args=None):
        """Update the conda lock files in {image} using image {tag}
        
        Parameters
        ----------
        image: str
            path to the image folder (e.g. tractor or heasoft)
        tag: str
            a tag name for the image of the form: repo:tag
        extra_args: str
            Extra command line arguments to be passed to 'docker run'
            e.g. '--network=host'
        """
        if not isinstance(tag, str) or ':' not in tag:
            raise ValueError(f'tag: {tag} is not a str the form repo:tag')
        tag = tag.rsplit(":", 1)[1]

        extra_args = extra_args or ''
        if not isinstance(extra_args, str):
            raise ValueError(f'Expected str for extra_args; got: {extra_args}')

        self.out(f'Updating the lock files for {image}')
        envfiles = [env for env in glob.glob(f'{image}/conda-*.yml')
                    if 'lock' not in env]
        for env in envfiles:
            match = re.match(rf"{image}/conda-(.*).yml", env)
            env_name = match[1] if match else 'base'
            cmd = (f'docker run --entrypoint="" --rm {extra_args} {tag}'
                   f'mamba env export -n {env_name}')
            result = self.run(cmd, 500, capture_output=True)
            # capture lines after: 'name:'
            lines = []
            include = False
            for line in result.stdout.split("\n"):
                if "name:" in line:
                    include = True
                if include:
                    lines.append(line)
            with open(f"{image}/conda-{env_name}-lock.yml", "w") as fp:
                fp.write("\n".join(lines))

if __name__ == '__main__':
    
    logger = logging.getLogger('::Builder::')
    logging.basicConfig(level=logging.DEBUG)
    builder = Builder(logger, dryrun=True)
    builder.build('fornax-images', 'tractor', 'some-tag')