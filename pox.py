#!/bin/bash -

# If you have PyPy 1.6+ in a directory called pypy alongside pox.py, we
# use it.
# Otherwise, we try to use a Python interpreter called python2.7, which
# is a good idea if you're using Python from MacPorts, for example.
# We fall back to just "python" and hope that works.

''''echo -n
if [ -x pypy/bin/pypy ]; then
  exec pypy/bin/pypy -O "$0" "$@"
fi

if [ "$(type -P python2.7)" != "" ]; then
  exec python2.7 -O "$0" "$@"
fi
exec python -O "$0" "$@"
'''

# Set default log level
import logging
logging.basicConfig(level=logging.DEBUG)

from pox.core import core
import pox.openflow.openflow
import pox.openflow.of_01

# Turn on extra info for event exceptions
import pox.lib.revent.revent as revent
revent.showEventExceptions = True

import sys

options = None

def doImport (name):
  if name in sys.modules:
    return name

  def showFail ():
    import traceback
    traceback.print_exc()
    print "Could not import module:",name

  try:
    __import__(name, globals(), locals())
    return name
  except ImportError:
    # This can be because the one we tried to import wasn't found OR
    # because one IT tried to import wasn't found.  Try to sort this...
    s = str(sys.exc_info()[1]).rsplit(" ", 1)[1]
    if name.endswith(s):
      #print s,"|",name
      return True
    else:
      showFail()
      return False
  except:
    showFail()
    return False

def doLaunch ():
  import sys, os
  # Add pox directory to path
  sys.path.append(os.path.abspath('pox'))
  sys.path.append(os.path.abspath('ext'))

  component_order = []
  components = {}
  #curargs = None

  curargs = {}
  global options
  options = curargs

  for arg in sys.argv[1:]:
    if not arg.startswith("--"):
      if arg not in components:
        components[arg] = []
      curargs = {}
      components[arg].append(curargs)
      component_order.append(arg)
    else:
      arg = arg[2:].split("=", 1)
      if len(arg) == 1: arg.append(True)
      curargs[arg[0]] = arg[1]

  inst = {}
  for name in component_order:
    cname = name
    inst[name] = inst.get(name, -1) + 1
    params = components[name][inst[name]]
    name = name.split(":", 1)
    launch = name[1] if len(name) == 2 else "launch"
    name = name[0]

    r = doImport("pox." + name)
    if r is False: return False
    if r is True:
      r = doImport(name)
      if r is False: return False
      if r is True:
        print "Module", name, "not found"
        return False
    name = r
    #print ">>",name

    if launch in sys.modules[name].__dict__:
      f = sys.modules[name].__dict__[launch]
      if f.__class__ is not doLaunch.__class__:
        print launch, "in", name, "isn't a function!"
        return False
      multi = False
      if f.func_code.co_argcount > 0:
        if f.func_code.co_varnames[f.func_code.co_argcount-1] == '__INSTANCE__':
          multi = True
          params['__INSTANCE__'] = (inst[cname], len(components[cname]),
                                    inst[cname] + 1 == len(components[cname]))

      if multi == False and len(components[cname]) != 1:
        print name, "does not accept multiple instances"
        return False

      f(**params)
    elif len(params) > 0 or launch is not "launch":
      print ("Module %s has no %s(), but it was specified or passed arguments"
             % (name, launch))
      return False

  return True

cli = True

def process_options ():
  for k,v in options.iteritems():
    #print k,"=",v
    if k == "no-cli":
      if str(v).lower() == "true":
        global cli
        cli = False
    else:
      print "Unknown option: ", k
      import sys
      sys.exit(1)

def pre_startup ():
  pox.openflow.openflow.launch() # Always launch OpenFlow

def post_startup ():
  #core.register("openflow_topology", pox.openflow.openflowtopology.OpenFlowTopology())
  #core.register("topology", pox.topology.topology.Topology())
  #core.register("openflow_discovery", pox.openflow.discovery.Discovery())
  #core.register("switch", pox.dumb_l3_switch.dumb_l3_switch.dumb_l3_switch())

  pox.openflow.of_01.launch() # Always launch of_01

def _monkeypatch_console ():
  """
  The readline in pypy (which is the readline from pyrepl) turns off output
  postprocessing, which disables normal NL->CRLF translation.  An effect of
  this is that output *from other threads* (like log messages) which try to
  print newlines end up just getting linefeeds and the output is all stair-
  stepped.  We monkeypatch the function in pyrepl which disables OPOST to turn
  OPOST back on again.  This doesn't immediately seem to break anything in the
  simple cases, and makes the console reasonable to use in pypy.
  """
  try:
    import termios
    import sys
    import pyrepl.unix_console
    uc = pyrepl.unix_console.UnixConsole
    old = uc.prepare
    def prep (self):
      old(self)
      f = sys.stdin.fileno()
      a = termios.tcgetattr(f)
      a[1] |= 1 # Turn on postprocessing (OPOST)
      termios.tcsetattr(f, termios.TCSANOW, a)
    uc.prepare = prep
  except:
    pass

if __name__ == '__main__':
  _monkeypatch_console()
  launchOK = False
  try:
    pre_startup()
    launchOK = doLaunch()
    if launchOK:
      process_options()
      post_startup()
      core.goUp()
  except:
    import traceback
    traceback.print_exc()
    launchOK = False

  if not launchOK:
    import sys
    sys.exit(1)

  if cli:
    import time
    time.sleep(1)
    import code
    import sys
    sys.ps1 = "POX> "
    sys.ps2 = " ... "
    code.interact('Ready.', local=locals())
  else:
    try:
      import time
      while True:
        time.sleep(5)
    except:
      pass
    #core.scheduler._thread.join() # Sleazy

  pox.core.core.quit()
