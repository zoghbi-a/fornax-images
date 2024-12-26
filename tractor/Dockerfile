# ONBUILD instructions in base-image/Dockerfile are used to
# perform certain actions based on the presence of specific
# files (such as conda-linux-64.lock, start) in this repo.
# Refer to the base-image/Dockerfile for documentation.
ARG IMAGE_TAG=latest
FROM public.ecr.aws/f6e2z3b0/fornax-images:base_image-24.1126.1926


LABEL org.opencontainers.image.ref.name="Fornax Default Astrophysics"

# add notebook updater script to run when jupyter starts
USER root
COPY --chmod=0755 update-notebooks.sh /usr/local/bin/before-notebook.d
USER $NB_USER

# For firefly
ENV FIREFLY_URL=https://irsa.ipac.caltech.edu/irsaviewer
