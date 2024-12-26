This is a list of image updates
# 08/30/2024
- `Default Astrophysics` image published in daskhub-dev as tractor-24.0829.1903.
    - The demo notebooks run in a conda environment called. `science_demo`
    - The LSDB notebooks run in the `base` environment.
- `High Energy Astrophysics` image published in daskhub-dev as heasoft-24.0829.1903.
    - This contains HEASoft 6.34.

# 11/26/2024
## Updates:
- The primary conda environment is changed to `notebook`. It is the environment
where the notebooks should be run. With this change, the dask extension should
work naturally.
- Added the openvscode extension.
- Updates to prevent sessions with CPU activity from being stopped. The policy now is:
    - If there is CPU activity, the notebook will not be stopped, even if the browser
    is closed.
    - If there is no activity (e.g. the notebook or browser tab is closed),
    the session terminates after 15 min. 
- The notebooks are updated automatically using `nbgitpuller` and they are
stored in the user's home directory. The update policy for `nbgitpuller`can be found
[here](https://nbgitpuller.readthedocs.io/en/latest/topic/automatic-merging.html#topic-automatic-merging).
The summary is:
    - 1. A file that is changed in the remote repo but not in the local clone will be updated.
    - 2. If different lines are changed by both the remote and local clone, the remote
    changes will be merged similar to case 1.
    - 3. If the same lines are changed by both the remote and local clone, the local
    changes are kept and the remote changes are discarded.
    - 4. If a file is deleted locally but still present in the remote repo, it will be restored.
    - 5. If a new file is added in the locall clone, and the remote repo has a new file with
    the same name, the local copy will be renamed by adding `_<timestamp>`, and the remote copy
    will be used.
If the user has a file (it can be empty) called `.no-notebook-update.txt` in their home
directory, then `nbgitpuller` will not be used and the notebook folder in the home
directory will **not** be updated.
- Switched to using conda yaml files to keep track of the installed software.

## Development Changes:
- Image tags:
    - base image: base_image-24.1127.1227
    - Default Astrophysics: tractor-24.1127.1421
    - High Energy Astrophysics: heasoft-24.1127.1235
- Switched to using conda yaml files to keep track of the installed software.
- Both Jupyterlab and the notebooks run in the `notebook` environemnt. The reason 
is that `dask-labextension` needs to run in the same environment as the notebooks.
- Clean the base image to start from `jupyter/docker-stacks-foundation`, adding
some files from `jupyter/base-notebook`. Needed to reduced the the size of the image
since we are not using the conda base environment.
- Updated heasoft image to also install heasoft in the main notebook environment.
- Update the CI to use only 2 stages instead of 3.
- Add `jupyter_cpu_alive` to track CPU usage and keep the server alive.
With this in place, as long as there is CPU activity, the jupyterhub culler
will not cull the server (unless maxAge is set in the backend).
- Use the `nbgitpuller` to update the notebooks when the session starts. This
is called from the `update-notebooks.sh` that is located in `/usr/local/bin/before-notebook.d`.
- `users_conda_envs` from conda `nb_conda_kernels` is not long used, so it is deleted from
the user's space
- The cache from `pip`, `astropy` and `conda` is now in /tmp/ instead of the home folder.
- disable scrollHeadingToTop in notebooks to fix scrolling issues.
- Add support for a landing page. This is set in the depolyment code by defining `JUPYTERHUB_DEFAULT_URL`. That is set
to `~/notebooks/introduction.md` all the time. The images have the option of modifying it. If `introduction.md` file exists, it is copied to `/opt/scritps`, then copied to the user's `~/notebooks` (by the pre-notebook script).