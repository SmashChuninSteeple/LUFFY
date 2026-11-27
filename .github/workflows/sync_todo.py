import os
import re
import subprocess
import sys

ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
README = os.path.join(ROOT, "README.md")


def sh(args):
    return subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


# TODO additions/removals/line-updates are scoped to the main-to-dev changes.
# Use the three-dot diff (merge-base..HEAD), the same set a main->dev PR shows.
out = sh(["git", "diff", "--name-only", "origin/main...HEAD"])
changed = [
    p
    for p in out.split()
    if p.endswith(".py") and not p.startswith(".github/")
]
print("Changed project .py files:", changed)

# README TODO bullet:  - [ ] **path/to/file.py:123** - TODO text
BULLET = re.compile(
    r'^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<text>.*)$'
)
# Full-line Python TODO comments:
#   # TODO: text
#   # TODO(author): text      -> keeps "(author): ..."
#   # TODO(author) text       -> keeps "(author) ..."
#   # TODO (author): text
PYTODO = re.compile(
    r'^[ \t]*#[ \t]*TODO[ \t]*(?::[ \t]*)?(.*?)[ \t]*$'
)


def todo_bullets(rel_path):
    found = []
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            m = PYTODO.match(raw.rstrip("\r\n"))
            if m:
                found.append((lineno, m.group(1)))
    found.sort()
    return [
        "- [ ] **%s:%d** - %s\n" % (rel_path, n, text) for n, text in found
    ]


with open(README, "rb") as fh:
    # Keep every original line ending / blank line byte-for-byte outside the
    # contiguous TODO bullet block we replace.
    lines = fh.read().decode("utf-8").splitlines(keepends=True)

heading = "### \U0001f4dd Complete TODO List"
head_idx = next(i for i, line in enumerate(lines) if line.startswith(heading))


def is_bullet(line):
    return BULLET.match(line.rstrip("\r\n")) is not None


start = next(
    i for i in range(head_idx + 1, len(lines)) if is_bullet(lines[i])
)
end = start
while end < len(lines) and is_bullet(lines[end]):
    end += 1

bullets = lines[start:end]

# Preserve existing file ordering and reuse unchanged bullet strings verbatim.
order = []
groups = {}
for bullet in bullets:
    m = BULLET.match(bullet.rstrip("\r\n"))
    path = m.group("path")
    if path not in groups:
        groups[path] = []
        order.append(path)
    groups[path].append(bullet)

for path in changed:
    if path in groups:
        groups[path] = todo_bullets(path)
    else:
        # Only update files already tracked by the README TODO list.
        print("Skipping (not present in README TODO list):", path)

new_bullets = []
for path in order:
    def line_no(bullet, _p=path):
        return int(
            BULLET.match(bullet.rstrip("\r\n")).group("line")
        )
    entries = groups[path]
    # Entries within a file must stay ordered by ascending line number.
    entries.sort(key=line_no)
    new_bullets.extend(entries)

# Splice in place; surrounding blank lines and all other sections untouched.
lines[start:end] = new_bullets
data = "".join(lines).encode("utf-8")
with open(README, "wb") as fh:
    fh.write(data)

print(
    "TODO bullets:",
    len(bullets),
    "->",
    len(new_bullets),
    "| README bytes:",
    len(data),
)
