#!/usr/bin/env python
"""
perms.py

Command-line interface to the permissions database.
"""

import sys

import procedural

USAGE = """\
Usage:

perms.py -h/--help
perms.py list
perms.py admins
perms.py promote [USER_ID] [...]
perms.py demote [USER_ID] [...]
perms.py show USER_ID
perms.py allow USER_ID ACTION ITEM
perms.py revoke USER_ID ACTION ITEM
perms.py add_user USER_ID
perms.py add_each USERLIST_FILENAME
perms.py allow_each USERLIST_FILENAME ACTION ITEM
perms.py revoke_each USERLIST_FILENAME ACTION ITEM

Commands:

  list - Lists the user_id of every user.
  admins - List the user_id of each admin.
  promote - Promotes the given user to an admin.
  demote - Demotes the given user to a normal user.
  show - Shows which permissions the target user has.
  allow - Allows the given user to take the given action on the given item.
  revoke - Revokes permission for the given user to take the given action on
    the given item.
  add_user - Adds a new user with the given user ID.
"""

def fail(msg=None):
  """
  Prints a message (optional), then usage, and then exit with an error.
  """
  if msg:
    sys.stderr.write(msg + '\n')
  sys.stderr.write(USAGE)
  exit(1)

# Print usage and exit without an error:
if '-h' in sys.argv or '--help' in sys.argv:
  print(USAGE)
  exit()

if len(sys.argv) < 2:
  fail()

cmd = sys.argv[1]
args = sys.argv[2:]

if cmd == "list":
  conn = procedural.get_perm_db_connection()
  cur = conn.execute(
    'SELECT username FROM permissions;'
  )
  for row in cur.fetchall():
    print(row[0])

elif cmd == "admins":
  conn = procedural.get_perm_db_connection()
  cur = conn.execute(
    'SELECT username FROM permissions WHERE is_admin = "True";'
  )
  for row in cur.fetchall():
    print(row[0])


elif cmd == "promote":
  if len(args) < 1:
    fail("Must supply at least one user ID to promote.")
  else:
    for user in args:
      if not procedural.set_admin(user, 'True'):
        fail("Failed to promote user '{}'".format(user))

elif cmd == "demote":
  if len(args) < 1:
    fail("Must supply at least one user ID to demote.")
  else:
    for user in args:
      if not procedural.set_admin(user, 'False'):
        fail("Failed to demote user '{}'".format(user))

elif cmd == "show":
  if len(args) != 1:
    fail("Must supply exactly one user ID to view permissions.")
  user = args[0]
  perms = procedural.get_permisisons(user)
  if perms == None:
    fail("User '{}' does not exist.".format(user))

  print("Permissions for user '{}':".format(user))
  for action in sorted(perms):
    print("{}:".format(action))
    for item in sorted(perms[action]):
      print("  {}".format(item))

elif cmd == "allow":
  if len(args) != 3:
    fail("Must supply exactly user ID, action, and item for 'allow'.")
  user, action, item = args
  if not procedural.grant_permission(user, action, item):
    fail("Failed to allow user '{}' to {} on {}".format(user, action, item))

elif cmd == "revoke":
  if len(args) != 3:
    fail("Must supply exactly user ID, action, and item for 'revoke'.")
  user, action, item = args
  if not procedural.revoke_permission(user, action, item):
    fail(
      "Failed to revoke permission for user '{}' to {} on {}".format(
        user,
        action,
        item
      )
    )

elif cmd == "add_user":
  if len(args) != 1:
    fail("Must supply exactly one user ID for 'add_user'.")
  user = args[0]
  if not procedural.add_user(user):
    fail("Unable to add user '{}'.".format(user))

elif cmd == "add_each":
  if len(args) != 1:
    fail("Must supply exactly one user list filename for 'add_each'.")
  ulf = args[0]
  with open(ulf, 'r') as fin:
    for line in fin:
      if len(line.strip()) == 0 or line.strip().startswith('#'):
        continue
      user = line.strip()
      if not procedural.add_user(user):
        fail("Unable to add user '{}'.".format(user))

elif cmd == "allow_each":
  if len(args) != 3:
    fail(
      (
        "Must supply exactly a user list filename, an action, and an item "
        "for 'allow_each'."
      )
    )
  ulf, action, item = args
  with open(ulf, 'r') as fin:
    for line in fin:
      if len(line.strip()) == 0 or line.strip().startswith('#'):
        continue
      user = line.strip()
      if not procedural.grant_permission(user, action, item):
        fail("Failed to allow user '{}' to {} on {}".format(user, action, item))

elif cmd == "revoke_each":
  if len(args) != 3:
    fail(
      (
        "Must supply exactly a user list filename, an action, and an item "
        "for 'revoke_each'."
      )
    )
  ulf, action, item = args
  with open(ulf, 'r') as fin:
    for line in fin:
      if len(line.strip()) == 0 or line.strip().startswith('#'):
        continue
      user = line.strip()
      if not procedural.revoke_permission(user, action, item):
        fail(
          "Failed to revoke permission for user '{}' to {} on {}".format(
            user,
            action,
            item
          )
        )

else:
  fail("Unknown command '{}'".format(cmd))
