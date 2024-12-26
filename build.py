#!/usr/bin/env python3

"""

Description:
------------
A python script for building docker images on fornax.

"""

import argparse
import glob
import subprocess
import os
import re
import json
import shlex
import time
import logging
import sys

    

def build_images(image, dryrun, build_args, update_lock, no_cache, no_build):
    """call 'docker build' on each element in images

    Parameters
    ----------
    images: str
        The name of the image to build.
    dryrun: bool
        Print docker command without running.
    build_args: dict
        extra build arguments.
    update_lock: bool
        update lock file?
    no_cache: bool
        if True, pass '--no-cache' to docker build
    no_build: bool
        If True, do not run 'docker build'. Useful for doing update-lock only
        
    """    
    
    # loop through requested images
    logging.debug(f'Working on image {image} ...')
    if os.path.exists(image) and os.path.exists(f'{image}/Dockerfile'):
        logging.debug(f'Found {image}/Dockerfile ...')
    else:    
        raise ValueError(f'No image folder found for {image}')

    # check build_args
    extra_args = []
    if build_args is not None:
        for arg in build_args:
            if '=' not in arg:
                raise ValueError(f'build_args should be of the form "name=value". Got "{arg}".')
        args = arg.split('=')
        args = f'{args[0].upper()}={args[1]}'
        extra_args = [i for arg in build_args for i in ['--build-arg', args]]
    
    # build the image #
    logging.debug(f'\tBuilding {image}')
    nocache = ['--no-cache'] if no_cache else []
    cmd = [
        'docker', 'build', '--network=host', '--progress=plain'] + nocache + ['-t', 
        f'fornax/{image}:latest'
    ] + extra_args + [f'./{image}']
    logging.debug('\t' + (' '.join(cmd)))
    
    if not dryrun:
        if update_lock and len(glob.glob(f'{image}/conda-*-lock.yml')):
            # If update_lock, remove the old ones so the build does
            # not use them
            # TODO: handle individual files separately
            if not no_build:
                os.system(f'rm {image}/conda-*-lock.yml')
        if not no_build:
            out = subprocess.call(cmd)
            if out:
                logging.error('\tError encountered.')
                sys.exit(1)

    # update lock-file?
    if update_lock:
        logging.debug(f'Updating the lock file for {image}')
        envfiles = [
            env for env in glob.glob(f'{image}/conda-*.yml') if 'lock' not in env
        ]
        for env in envfiles:
            match = re.match(rf'{image}/conda-(.*).yml', env)
            if match:
                env_name = match[1]
            else:
                env_name = 'base'
            # create an env file; use shelx so ="" works
            cmd = shlex.split(f'docker run --entrypoint="" --rm fornax/{image}:latest ' +
                              f'mamba env export -n {env_name}')
            logging.debug('\t' + (' '.join(cmd)))
    
            if not dryrun:
                out = subprocess.check_output(cmd)
                lines = []
                include = False
                for line in out.decode().split('\n'):
                    if 'name:' in line:
                        include = True
                    if include:
                        lines.append(line)
                with open(f'{image}/conda-{env_name}-lock.yml', 'w') as fp:
                    fp.write('\n'.join(lines))


if __name__ == '__main__':

    ap = argparse.ArgumentParser()
    ap.add_argument('--dryrun', action='store_true', default=False)
    ap.add_argument('--update-lock', action='store_true', help='update conda lock file', default=False)
    ap.add_argument('--no-cache', action='store_true', help='pass --no-cache to docker', default=False)
    ap.add_argument('--no-build', action='store_true', help='Do not run docker build', default=False)
    ap.add_argument('image', help='image to build')
    ap.add_argument('--build-args', nargs='*', help='Extra arguments passed to docker build')
    args = ap.parse_args()


    logging.basicConfig(format='%(asctime)s|%(levelname)5s| %(message)s',
                        datefmt='%Y-%m-%d|%H:%M:%S')
    logging.getLogger().setLevel(logging.DEBUG)

    build_images(args.image, args.dryrun, args.build_args, args.update_lock, args.no_cache, args.no_build)
