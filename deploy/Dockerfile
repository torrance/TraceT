FROM docker.io/library/debian:trixie

RUN apt update

RUN apt install -y --no-install-recommends \
  ca-certificates \
  curl

# Install UV Python package manager
ADD https://astral.sh/uv/0.9.28/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"
ENV UV_NO_DEV=1

RUN mkdir /tracet

COPY pyproject.toml /tracet
COPY uv.lock /tracet
COPY .python-version /tracet

WORKDIR /tracet
RUN ls -al .
RUN uv sync --locked
