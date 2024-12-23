import argparse
import glob
import logging
import os
import re
import subprocess
import sys


order = (
    "base_image",
    "tractor",
    # "heasoft",
)


class TaskRunner:
    """Base class for running system commands and logging

    this class only exists (instead of module-level functions) to make unit
    testing less painful; it is also used by "release.py"
    """
    def __init__(self, logger):
        """Create a new TaskRunner
        
        Parameters:
        -----------
        logger: logging.Logger
            Logging object
        
        """
        self.logger = logger

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
        self.out(f"Running {command} with timeout {timeout}")
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            text=True,
            timeout=timeout,
            **runargs,
        )
        return result


class Builder(TaskRunner):

    def build(
        self,
        repository,
        image_path,
        tag,
        build_args=None,
        build_pars=None,
    ):
        """Build an image by called 'docker build'
        
        Parameters:
        -----------
        repository: str
            repository name
        image_path: str
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
        extra_args = []
    
        # cope with forks of the repository (see tractor/heasoft Dockerfiles) by
        # setting a build arg
        build_args = build_args or []
        default_tag = tag.rsplit(":", 1)[1]
        # Ensure we have: name=value
        build_args = [arg.strip() for arg in build_args]
        
        # add passed parameters to build_args
        mapping = {
            'REPOSITORY': repository,
            'BASE_IMAGE_TAG': default_tag,
            'IMAGE_TAG': default_tag
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
            extra_args.append(f"--build-arg {name}={val}")

        # now add any other line parameters
        if build_pars:
            extra_args.append(build_pars)

        extra_args = " ".join(extra_args)
        buildcommand = f"docker build {extra_args} --tag {tag} {image_path}"
        self.out(f"Building {image_path} via '{buildcommand}'")
        result = self.run(buildcommand, timeout=10000)
        self.out(result)

    def push(self, tag):
        """Push the image with 'docker push'
        
        Parameters:
        -----------
        tag: str
            a tag name for the image

        """
        push_command = f"docker push {tag}"
        self.out(f"Pushing {tag} via '{push_command}'")
        result = self.run(push_command, timeout=1000)
        self.out(result)

    def remove_lockfiles(self, image_path):
        """Remove conda lock files from image_path"""
        self.out(f"Removing the lock files for {image_path}")
        lockfiles = glob.glob(f"{image_path}/conda-*lock.yml")
        for lockfile in lockfiles:
            self.out(f"Removing {image_path}/{lockfile}")
            os.unlink(lockfile)

    def update_lockfiles(self, image_path, repository, tag):
        """Update the conda lock files for the image {image_path}
        
        Parameters
        ----------
        image_path: str
            path to the image folder (e.g. tractor or heasoft)
        repository: str
            repository name
        tag: str
            a tag name for the image
        """
        tag = tag.rsplit(":", 1)[1]
        self.out(f"Updating the lock files for {image_path}")
        envfiles = glob.glob(f"{image_path}/conda-*.yml")
        envfiles = [
            env for env in glob.glob(f"{image_path}/conda-*.yml") if "lock" not in env
        ]
        for env in envfiles:
            match = re.match(rf"{image_path}/conda-(.*).yml", env)
            if match:
                env_name = match[1]
            else:
                env_name = "base"
            cmd = (
                f'docker run --entrypoint="" --rm '
                f"ghcr.io/{repository}/{image_path}:{tag} "
                f"mamba env export -n {env_name}"
            )

            result = self.run(cmd, 500, capture_output=True)
            lines = []
            include = False
            # capture lines after: 'name:'
            for line in result.stdout.split("\n"):
                if "name:" in line:
                    include = True
                if include:
                    lines.append(line)
            with open(f"{image_path}/conda-{env_name}-lock.yml", "w") as fp:
                fp.write("\n".join(lines))

    def builds_necessary(self, repository, tag, images):
        """Construct a list of images to be built"""
        tobuild = []
        for name in images:
            if not name in order:
                self.out(f"Unknown image name {name}", logging.ERROR)
                raise SystemExit(2)

        # tractor and heasoft depend on base_image, so ordering is important
        # here (I think)
        for name in order:
            if name in images:
                struct = (
                    name,
                    f"ghcr.io/{repository}/{name}:{tag}",
                )
                tobuild.append(struct)

        return tobuild

    def chdir(self, path):
        os.chdir(path)


def main(
    builder,
    repository,
    tag=None,
    do_push=False,
    update_lock=False,
    no_build=False,
    build_args=None,
    images=order,
    build_pars=None
):
    if no_build and do_push:
        builder.out(
            "--no-build and --do-push cannot be used together", logging.ERROR
        )
        raise SystemExit(2)
    
    if build_pars is not None and ('--tag' in build_pars or '--build-arg' in build_pars):
        builder.out(
            "--tag and --build-arg cannot be passed in build-pars", logging.ERROR
        )
        raise SystemExit(2)

    builder.out(f"Repository {repository}, tag {tag}")
    tobuild = builder.builds_necessary(repository, tag, images)

    # parent dir of the dir of this file (root of this checkout)
    here = __file__
    if not here.startswith(os.path.sep):
        here = os.path.join(os.getcwd(), here)

    root = os.path.dirname(os.path.dirname(here))
    builder.chdir(root)  # indirection for testing sanity

    for dockerdir, tag in tobuild:
        if not no_build:
            if update_lock:
                builder.remove_lockfiles(dockerdir)
            builder.build(
                repository, dockerdir, tag, build_args, build_pars
            )
        if update_lock:
            builder.update_lockfiles(dockerdir, repository, tag)
        if do_push:
            builder.push(tag)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "repository", help="GH repository name (e.g. 'fornax-core/images')"
    )
    ap.add_argument("tag", help="Container registry tag name (e.g. 'mybranch')")
    ap.add_argument(
        "--push",
        action="store_true",
        help=(
            "After building, push to container registry (incompatible with "
            "--no-build)."
        ),
        default=False,
    )
    ap.add_argument(
        "--update-lock",
        action="store_true",
        help="Update conda lock files. Meant to be used when run to update conda lock files in local directories. A suitable command might be 'python3 src/buildimages.py nasa-fornax/fornax-images mybranch --update-lock'",
        default=False,
    )
    ap.add_argument(
        "--no-build",
        action="store_true",
        help="don't actually build images (incompatible with --push)",
        default=False,
    )
    ap.add_argument(
        "--build-args",
        nargs="*",
        help=(
            "Extra --build-arg arguments passed to docker build e.g. 'a=b c=d'"
        ),
    )
    ap.add_argument(
        "--images",
        nargs="*",
        help=("Image names separated by spaces e.g. 'base_image tractor'"),
        default=order,
    )
    ap.add_argument(
        "--build-pars",
        help="Arguments to be passed directly to `docker build`",
        default=None,
    )

    args = ap.parse_args()

    # see https://github.com/docker/docker-py/issues/2230 for rationale
    # as to why we set DOCKER_BUILDKIT (--chmod flag to COPY)
    os.environ["DOCKER_BUILDKIT"] = "1"
    logging.basicConfig(
        format="%(asctime)s|%(levelname)5s| %(message)s",
        datefmt="%Y-%m-%d|%H:%M:%S",
    )
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    builder = Builder(logger)

    main(
        builder,
        args.repository,
        args.tag,
        args.push,
        args.update_lock,
        args.no_build,
        args.build_args,
        args.images,
        args.build_pars,
    )
