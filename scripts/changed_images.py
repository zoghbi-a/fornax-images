import argparse
import json
import os
import sys
import logging

sys.path.insert(0, f'{os.path.dirname(__file__)}')
from build import TaskRunner

def find_changed_images(github_data:dict, runner:TaskRunner):
    """Find changed images

    Returns a list of image names that changed after the git event
    """

    if github_data['event_name'] == 'pull_request':
        base_ref = github_data['event']['base_ref']

        cmd = f'git fetch origin {base_ref}'
        out = runner.run(cmd, 500, capture_output=True)

        cmd = f'git --no-pager diff --name-only HEAD origin/${base_ref} | xargs -n1 dirname | sort -u'
        final_out = runner.run(cmd, 500, capture_output=True)

    elif github_data['event_name'] == 'push':
        before = github_data['event']['before']
        after = github_data['event']['after']

        cmd = f'git fetch origin {before}'
        out = runner.run(cmd, 500, capture_output=True)

        cmd = f'git --no-pager diff-tree --name-only -r {before}..{after} | xargs -n1 dirname | sort -u'
        final_out = runner.run(cmd, 500, capture_output=True)

    else:
        cmd = 'git ls-files | xargs -n1 dirname | sort -u'
        final_out = runner.run(cmd, 500, capture_output=True)

    changed_images = []
    if not runner.dryrun:
        changed_images = final_out.stdout.strip()

        # from str to list
        changed_images = changed_images.split()

        # keep a list of images, i.e. folders that contain Dockerfile
        changed_images = [cdir for cdir in changed_images if os.path.exists(f'{cdir}/Dockerfile')]

    return changed_images


if __name__ == '__main__':
    
    ap = argparse.ArgumentParser()

    ap.add_argument('jsonfile',
        help="File name of the json file that contains Github action context")
    
    ap.add_argument('--dryrun', action='store_true',
        help='prepare but do not run commands',
        default=False)
    
    ap.add_argument('--debug', action='store_true',
        help='Print debug messages',
        default=False)

    args = ap.parse_args()
    # get parameters
    dryrun = args.dryrun
    debug = args.debug
    jsonfile = args.jsonfile
    
    with open(args.jsonfile, "r") as file:
        data = json.load(file)
    
    logging.basicConfig(
        format="%(asctime)s|%(levelname)5s| %(message)s",
        datefmt="%Y-%m-%d|%H:%M:%S",
    )
    logger = logging.getLogger('::Changed-dirs::')
    logger.setLevel(level=logging.DEBUG if debug else logging.INFO)
    runner = TaskRunner(logger, dryrun)

    # some logging:
    runner.out('+++ INPUT +++', logging.DEBUG)
    runner.out(f'jsonfile: {jsonfile}', logging.DEBUG)
    runner.out(f'debug: {debug}', logging.DEBUG)
    runner.out(f'dryrun: {dryrun}', logging.DEBUG)
    runner.out(f'event_name: {data["event_name"]}', logging.DEBUG)
    runner.out('+++++++++++++', logging.DEBUG)
    
    changed_images = find_changed_images(data, runner)
    
    # print the result in json text so it is picked up in the CI script
    res = json.dumps(changed_images)
    runner.out('+++ OUTPUT +++', logging.DEBUG)
    runner.out(res)
    runner.out('++++++++++++++', logging.DEBUG)
    # clean print so it is picked up by the CI
    print(res)