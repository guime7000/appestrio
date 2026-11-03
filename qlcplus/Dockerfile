# QLC+ (https://qlcplus.org/) -- the lighting control app a
# `handles_dmx` device's "QLC+" nav link opens, directly on this
# container's own port 9999 (see root App.vue and compose.yml, which
# every lumestrio runs unconditionally -- decided 2026-11-03). Runs
# headless (QT_QPA_PLATFORM=offscreen, see qt_export.sh) with its web
# interface enabled (-w); no DMX interface is required just to run this
# container and tune a show in the web UI -- a real USB-DMX dongle etc.
# only matters once you actually want DMX output, and is passed through
# per-device via a commented `devices:` placeholder in compose.yml.
#
# Installed from Debian's own `qlcplus` package rather than the
# project's upstream .deb (which only ever publishes amd64 builds) --
# this is the one thing that makes the same Dockerfile actually install
# on both an amd64 dev machine and the real arm64 Raspberry Pi target
# (apt resolves the right architecture automatically). Slightly behind
# upstream's latest (4.12.6 in bookworm vs. 4.13.1), accepted as the
# tradeoff for working on real hardware at all.

FROM debian:bookworm-slim

COPY qlcplus.sh /QLC/entrypoint.sh
COPY qtexport.sh /QLC/qt_export.sh

RUN apt-get update \
    && apt-get install -y --no-install-recommends qlcplus curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Web interface (see qlcplus.sh's `-w` flag). `curl` above is
# qlcplus.sh's own -- it polls this port and POSTs the project to
# /loadProject once the server is actually up (see that script's own
# comment for why loading it via the `-o` command-line flag at launch
# doesn't work).
EXPOSE 9999

# Deliberately NOT `VOLUME /QLC` -- found and fixed 2026-11-03: an
# anonymous volume at /QLC would freeze /QLC/entrypoint.sh and
# /QLC/qt_export.sh at whatever they were on *first* container
# creation, silently surviving later image rebuilds (confirmed directly
# -- a rebuilt image's own content was correct, but a recreated
# container kept running the stale script until its anonymous volume
# was discarded). compose.yml only ever needs to bind-mount the two
# specific subpaths below `/QLC` (`/QLC/project`,
# `/root/.qlcplus/fixtures`), never `/QLC` itself, so no volume
# declaration is needed here at all.

ENTRYPOINT ["bash", "/QLC/entrypoint.sh"]
