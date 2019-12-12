#!/usr/bin/env python
"""
list.py

Lists items from solutions table of the solutions.sqlite3 database in TSV
format. If command-line arguments are given, lists just solutions for those
users.

The '-p' or '--puzzles' flag may be given to treat command-line arguments as a
list of puzzle IDs instead of a list of usernames to filter by.
"""

import sys
import csv
import json
import sqlite3

import procedural

USAGE = """\
list.py -h|--help
list.py [-m|--missing] [-p|--puzzles] [IDs...]

Lists submissions that match one of the given user IDs (or puzzle IDs if
-p/--puzzles is given). If no user/puzzle ID is given, it lists all
submissions.

If -m/--missing is given, it lists either all puzzles not solved by (all of)
the given user(s), or all users who did not solve (all of) the given puzzle(s).

Both -p and -m are ignored if no ID values are given.
"""

if '-h' in sys.argv or '--help' in sys.argv:
  print(USAGE)
  exit()

puzzles = False
if '-p' in sys.argv or '--puzzles' in sys.argv:
  try:
    sys.argv.remove('-p')
  except:
    pass
  try:
    sys.argv.remove('--puzzles')
  except:
    pass
  puzzles = True

missing = False
if '-m' in sys.argv or '--missing' in sys.argv:
  try:
    sys.argv.remove('-m')
  except:
    pass
  try:
    sys.argv.remove('--missing')
  except:
    pass
  missing = True


if sys.argv[1:]:
  ids = sys.argv[1:]
else:
  ids = None

rows = []
results = []

roster = procedural.get_roster()
students = procedural.get_student_list()
plist = procedural.get_puzzles_list()

if ids:
  if puzzles:
    if missing:
      solved_all = set(students)
      for puzzle in ids:
        solved_this = set(
          procedural.solution_info(x)[0]
            for x in procedural.all_solutions_to(puzzle)
        )
        # Remove students who didn't solve this puzzle from the solved_all set
        solved_all -= set(students) - solved_this
      results = set(students) - solved_all
    else:
      for puzzle in ids:
        results.extend([x[1] for x in procedural.all_solutions_to(puzzle)])
  else:
    if missing:
      solved_by_all = set(plist)
      for user in ids:
        solved_by_this_user = set(
          procedural.solution_info(x)[1]
          for x in procedural.all_solutions_by(user)
        )
        solved_by_all -= set(plist) - solved_by_this_user
      results = set(plist) - solved_by_all
    else:
      for user in ids:
        results.extend(procedural.all_solutions_by(user))
else:
  results = []
  for user in roster:
    results.extend(procedural.all_solutions_by(user))

if missing:
  writer = csv.writer(sys.stdout, dialect='excel-tab')
  if puzzles:
    writer.writerow(('username',))
  else:
    writer.writerow(('puzzle_id',))
  for thing in results:
    writer.writerow([thing])
else:
  for fn in results:
    username, puzzle_id, timestamp = procedural.solution_info(fn)
    rows.append((username, puzzle_id, timestamp))

  writer = csv.writer(sys.stdout, dialect='excel-tab')
  writer.writerow(('username', 'timestamp', 'puzzle_id'))
  for row in rows:
    writer.writerow(row)
