# Decision: git repo root is Downloads, not plumb

`git rev-parse --show-toplevel` = `/home/ashutosh/Downloads`. plumb/ is a subdir of a
large personal repo full of PDFs/zips/mp4s. `git add -A` scans the whole tree and times out.

Rule for all commits this project: stage ONLY plumb paths with explicit pathspecs
(e.g. `git add plumb/docs plumb/engine ...` or from plumb cwd `git add docs engine`).
Never use `git add -A` or `git add .` at repo root. Never `git push`.
