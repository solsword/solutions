#!/usr/bin/env python3
"""
solutions.py

Flask WSGI app that serves solution files with permissions decided using CAS
logins.
"""

import flask
import flask_cas
#import flask_talisman
import werkzeug

import os
import sys
import json
import traceback
import time
import datetime

#------------------#
# Global Variables #
#------------------#

# content security policy
CSP = {
  'default-src': [
    "https:",
    "'self'",
  ],
  'script-src': [
    "https:",
    "'self'",
    "'unsafe-inline'",
    "'unsafe-eval'",
  ],
}

# Default permissions
DEFAULT_PERMISSIONS = {
  "admins": [],
  "roster": [],
  "controls": {}
}

# Default per-solution controls
DEFAULT_CONTROLS = {
  "release": False,
  "release_to": "roster",
  "submitted": [],
  "deny": []
}

#-------------------------#
# Setup and Configuration #
#-------------------------#

app = flask.Flask(__name__)
#flask_talisman.Talisman(app, content_security_policy=CSP) # force HTTPS
cas = flask_cas.CAS(app, '/cas') # enable CAS

app.config.from_object('config')
app.config["DEBUG"] = False

# Set secret key from secret file:
with open("secret", 'rb') as fin:
  app.secret_key = fin.read()

# Redirect from http to https:
# TODO: Test in production whether this is necessary given Talisman...
#@app.before_request
#def https_redirect():
#  print("REQ: " + str(flask.request.url))
#  if not flask.request.is_secure:
#    url = flask.request.url.replace('http://', 'https://', 1)
#    code = 301
#    return flask.redirect(url, code=code)

#-------------------#
# Custom Decorators #
#-------------------#

def returnJSON(f):
  """
  Wraps a function so that returned objects are dumped to JSON strings before
  being passed further outwards. 
  """
  def wrapped(*args, **kwargs):
    r = f(*args, **kwargs)
    return json.dumps(r)

  wrapped.__name__ = f.__name__
  return wrapped

def admin_only(f):
  """
  Wraps a function so that it first checks the CAS username against the
  permissions file and returns 403 (forbidden) if the user isn't set up
  as an admin.
  """
  def wrapped(*args, **kwargs):
    username = flask.session.get("CAS_USERNAME", None)
    if username == None:
      return ("Unauthenticated user.", 403)
    else:
      if not is_admin(username):
        return ("You must be an administrator to access this page.", 403)
      else:
        return f(*args, **kwargs)

  wrapped.__name__ = f.__name__
  return wrapped

#---------------#
# Server Routes #
#---------------#

@flask_cas.login_required
@app.route('/')
def route_root():
  return flask.render_template(
    "main.html",
    username=cas.username
  )

@app.route("/list")
@returnJSON
def route_list():
  """
  This route returns a JSON dictionary that contains the file structure of the
  solutions folder.
  """
  struct = get_solutions_structure()
  return struct

@app.route("/solution/<path:target>")
def route_solution(target):
  """
  This route returns full file contents from the SOLUTIONS_DIRECTORY, subject
  to the permissions structure.
  """
  user = flask.session.get("CAS_USERNAME", None)
  if has_permission(target, user):
    sd = app.config.get("SOLUTIONS_DIRECTORY", "solutions")
    target = os.path.join(sd, target)
    if os.path.exists(target):
      # Follow symlink chains:
      while os.path.islink(target):
        target = os.readlink(target)
      # Read file (or error on directory)
      if os.path.isfile(target):
        # Open in binary mode as we don't know what kind of file it is...
        with open(target, 'rb') as fin:
          return fin.read()
      else:
        return ("Invalid solution file '{}' (isn't a file)", 400)
    else:
        return ("Invalid solution file '{}' (doesn't exist)", 400)
  else:
    reject = "You don't have permission to view solution '{}'.".format(
      target
    )
    if user == None:
      reject += " (You are not logged in.)"
    return (reject, 403)


#------------------#
# Helper Functions #
#------------------#

def get_default_timezone():
  """
  Get's Python's default timezone, determined somehow.
  """
  now = datetime.datetime.now()
  return now.astimezone().tzinfo.tzname(now)

def str__time(tstr):
  """
  Converts a string to a datetime object. Default format is:

    yyyy-mm-dd HH:MM:SS TZ
    
  The seconds and timezone are optional. Timezone must be given as +HH:SS or
  -HH:SS.
  """
  formats = [
    "%Y-%m-%d %H:%M:%S %z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M %z",
    "%Y-%m-%d %H:%M",
  ]
  result = None
  for f in formats:
    try:
      result = datetime.datetime.fromtimestamp(
        time.mktime(time.strptime(tstr, f))
      )
    except Exception as e:
      pass

    if result != None:
      break

  if result == None:
    raise ValueError("Couldn't parse time data: '{}'".format(tstr))

  return result

def is_in_past(moment):
  """
  Returns True if the given datetime object is in the past (compares against a
  new datetime.now result).
  """
  present = datetime.datetime.now()
  return moment < present


def get_solutions_structure():
  """
  Returns a dictionary with the same structure as the file tree in the
  solutions directory.
  """
  sd = app.config.get("SOLUTIONS_DIRECTORY", "solutions")
  return get_file_structure(sd)

def get_file_structure(path):
  """
  Returns a dictionary that enumerates the non-hidden files in the given path,
  with sub-dictionaries for sub-directories. If given the path to a file, just
  returns the string "F"; paths to files in directory dictionaries have the
  value "F" (instead of a dictionary value). So for example, the following
  directory structure: 

    a/
       b/
         1.txt
         2.txt
       c/
         3.txt
       4.txt
       .hidden

  would result in this dictionary (if 'a' is the argument):

    {
      "b": {
        "1.txt": "F",
        "2.txt": "F"
      },
      "c": {
        "3.txt": "F"
      },
      "4.txt": "F"
    }

  Symlinks will be followed, but other non-file non-directory entries (like
  named pipes) will be ignored.
  """
  if os.path.isfile(path) and not os.path.basename(path).startswith('.'):
    return "F"
  elif os.path.isdir(path):
    result = {}
    for sub in os.listdir(path):
      full = os.path.join(path, sub)
      struct = get_file_structure(full)
      if struct != None:
        result[sub] = struct
    return result
  else: # symlinks or the like
    if os.path.islink(path):
      # Follow symlink chain
      while os.path.islink(path):
        path = os.path.readlink(path)
      # Call ourselves on non-link destination (result will be put by parent
      # call into entry named after symlink, as appropraite)
      return get_file_structure(path)
    else:
      print("Invalid path: '{}'".format(path), file=sys.stderr)
      return None

#----------------#
# Info Functions #
#----------------#

def is_admin(user_id):
  """
  Retrieves a user's admin status from the permissions directory.
  """
  perms = get_current_permissions()
  return user_id in perms["admins"]

def get_roster():
  """
  Retrieves the roster of eligible users from the permissions directory. Mixes
  in admins so that both admins and explicit roster entries are returned.
  Result is a list of username strings.
  """
  perms = get_current_permissions()
  admins = perms.get("admins", [])
  return admins + perms.get("roster", [])

def get_student_list():
  """
  Works like get_roster but just returns a list of students; does not include
  admins.
  """
  perms = get_current_permissions()
  return perms.get("roster", [])

def get_controls(solution_path):
  """
  Retrieves and merges a solution's controls object from the permissions
  directory. Returns DEFAULT_CONTROLS for unlisted solutions. If controls are
  set both on a directory and a file within that directory, controls for the
  file will override controls for the directory, but any values not overridden
  in the file controls will persist from the directory settings.
  """
  # TODO: Custom merging of submitted/release_to/deny etc. lists?
  perms = get_current_permissions()
  pieces = os.path.split(solution_path)
  result = DEFAULT_CONTROLS
  for i in range(1, len(pieces)+1):
    sub = os.path.join(*pieces[:i])
    # More-specific control entries override less-specific ones:
    result.update(perms["controls"].get(sub, {}))
  return result

def has_permission(solution_path, user_id):
  """
  Retrieves a solution's controls object from the permissions directory, and
  checks whether the user has permission to view it. Returns True or
  False. Admin accounts have permission to view all solutions, and if the
  user_id is None, it always returns False unless the solution is released and
  the "release_to" control value is "world". The following control settings
  affect permission:

    1. If the controls list has a "deny" list, those users will not be able to
       see the solution, no matter what other rules would normally apply (even
       if they are admins, and even if the solution is released to the world,
       although those users could log out to view a solution that is released
       to the world).
    2. If "release" is set to false, or to a date/time in the future, only
       admins have permission to view the file. Only if "release" is set to
       true or a past date will the rest of these rules apply.
    3. If "release_to" is set to "nobody", only admins have permission.
    4. If "release_to" is set to a list of strings, only admins and usernames
       in that list have permission.
    5. If "release_to" is set to "roster", only admins and students on the
       roster have permission.
    6. If "release_to" is set to "submitted", only admins and students on the
       "submitted" list have permission.
    7. If "release_to" is set to "world", everyone, even unauthenticated users,
       will have access to the solution, as long as it is released (see #1).

  Here are a contradictory situations to watch out for:
    - Always check the "release" value: other values don't matter if this is
      false or a future date/time.
    - Even if the assignment is released, if it has "release_to": "nobody" it
      won't be visible to anyone besides admins.
    - A world-released file with a deny list: users on the deny list can log
      out to view the file.
    - Contradictory specifications of release_to or other variables within
      directory and file-level control settings. The file-level settings which
      are present override those at the directory level, but others are
      inherited.
    - It is possible to add a user ID to the release_to or submitted lists
      which is not on the roster. Unless release_to is "roster," the roster
      will not be checked.
    - TODO: As of now, deny lists for specific files overwrite rather than
      adding to deny lists of parent directories. So a deny list for a
      directory won't necessarily always apply if files in that directory have
      their own deny lists.
  """
  controls = get_controls(solution_path)

  deny_list = controls.get("deny", [])
  # Even admins can be denied:
  if user_id in deny_list:
    return False

  # But if they're not denied they're always allowed:
  if user_id != None and is_admin(user_id):
    return True

  release = controls.get("release", False)
  if release == False:
    return False
  elif isinstance(release, str):
    release_time = str__time(release)
    if not is_in_past(release_time):
      return False

  # If we get here, the assignment has been released, and we've already checked
  # for admin status and deny-list presence, so we just need to check
  # release_to and possible the roster/submitted lists.

  release_to = controls.get("release_to", "nobody")
  if isinstance(release_to, list):
    return user_id in release_to
  elif release_to == "nobody":
    return False
  elif release_to == "world":
    return True # don't even care if user is logged in...
  elif release_to == "roster":
    return user_id != None and user_id in get_roster()
  elif release_to == "submitted":
    return user_id != None and user_id in controls.get("submitted", [])


def get_current_permissions():
  """
  Reads all files in the permissions directory and merges them into one big
  permissions object that contains an admins list, a roster list, and a
  controls dictionary mapping individual solution paths to controls objects
  (seehas_permission for how those are used).

  Files in this directory can be updated without restarting the server because
  we read them on every web request (not terribly scalable, but flexible for
  changes). The DEFAULT_PERMISSIONS are used as a base even if there are no
  files in the PERMISSIONS_DIRECTORY.
  """
  pd = app.config.get("PERMISSIONS_DIRECTORY", "permissions")
  if not os.path.isdir(pd):
    print(
      "Warning: Permissions directory is not a directory! "
    + "Check your config file!"
    )
  try:
    return merge_permissions(DEFAULT_PERMISSIONS, slurp_permissions(pd))
  except Exception as e:
    if sys.version_info >= (3, 5):
      tbe = traceback.TracebackException.from_exception(e)
      print(
        "Error loading permissions from directory '{}':\n".format(pd)
      + '\n'.join(tbe.format()),
        file=sys.stderr
      )
    else:
      print(
        "Error loading permissions from directory '{}':".format(pd),
        file=sys.stderr
      )
      # TODO: Do this to stderr too!
      traceback.print_exception(*sys.exc_info())
    return DEFAULT_PERMISSIONS


def slurp_permissions(directory):
  """
  Recursively slurps in permissions files and merges them into one big
  dictionary. Each file should be a .json file, and any errors encountered
  cause that file to be ignored with a warning message. The merge also prints
  warnings if the same controls key exists in multiple files, although in those
  cases it attempts to merge those controls objects, letting settings in
  later-alphabetically and shallower-in-the-directory-structure files override
  settings in other files.
  """
  result = {}
  for entry in sorted(os.listdir(directory)):
    full = os.path.join(directory, entry)
    while os.path.islink(full):
      full = os.path.readlink(full)
    if os.path.isfile(full):
      try:
        with open(full, 'r') as fin:
          perms = json.load(fin)
      except:
        print(
          "Warning: file '{}' could not be interpreted as a JSON object."
          .format(
            full
          ),
          file=sys.stderr
        )
      result = merge_permissions(result, perms)
    elif os.path.isdir(full):
      result = merge_permissions(result, slurp_permissions(full), full)
    # else ignore this non-file non-directory entry.
  return result

def merge_unique_lists(a, b):
  """
  Merges two lists which are actually sets, returning a sorted result list.
  """
  return sorted(list(set(a) | set(b)))

def merge_permissions(sofar, novel, novel_src = "Unknown"):
  """
  Merges two permissions objects, letting new settings override old ones.
  Prints a warning if the same controls key exists in both.
  """
  combined = {}
  combined["admins"] = merge_unique_lists(
    sofar.get("admins", []),
    novel.get("admins", [])
  )
  combined["roster"] = merge_unique_lists(
    sofar.get("roster", []),
    novel.get("roster", [])
  )
  combined["controls"] = {}
  combined["controls"].update(sofar.get("controls", {}))
  for key in novel["controls"]:
    if key in combined["controls"]:
      print(
        (
          "Warning: permissions from '{}' contain duplicate controls for "
        + "solution path '{}'."
        ).format(novel_src, key),
        file=sys.stderr
      )
      # New controls settings override old ones individually, except deny and
      # submitted lists which accrete.
      for subkey in novel["controls"][key]:
        if subkey in ("submitted", "deny"):
          combined["controls"][key][subkey] = merge_unique_lists(
            combined["controls"][key][subkey],
            novel["controls"][key][subkey]
          )
        else:
          combined["controls"][key][subkey] = novel["controls"][key][subkey]
    else:
      combined["controls"][key] = novel["controls"][key]

  return combined


#--------------#
# Startup Code #
#--------------#

if __name__ == "__main__":
  #app.run('localhost', 1947, ssl_context=('cert.pem', 'key.pem'))
  #app.run('0.0.0.0', 1947, ssl_context=('cert.pem', 'key.pem'))
  app.run('localhost', 1947)
