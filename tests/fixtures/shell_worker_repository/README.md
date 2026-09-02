# Shell worker fixture repository

This directory is a deliberately tiny, deterministic workspace used by the shell-worker tests.
It represents repository content only; it is copied into a temporary directory before each test
and is never executed in-place.

`fixture_command.py` exposes deterministic operations for success, argument-literal, failure,
timeout, and environment tests. `input.txt` is the stable input for the render operation.
