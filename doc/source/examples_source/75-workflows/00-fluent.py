"""
.. _fluent_workflow:
.. _inputfile: https://github.com/ansys/pydynamicreporting/tree/main/doc/source/_data

Create a report from Fluent
===========================

The following example shows how to combine Ansys Fluent, Ansys
EnSight and Ansys Dynamic Reporting into a single script to drive
the automation of a parameter study all the way from the initial
set up through simulation and postprocessing and finally to a
report.

.. note::
   This example assumes that you have a local Ansys installation. It
   also assumes that the input and output files are in the directory
   you are running the script from.

"""

###############################################################################
# Set up the environment
# ----------------------
#
# As a first step, let's load the pyansys modules needed for Ansys Fluent,
# Ansys EnSight and Ansys Dynamic Reporting, and let's set the script to
# point to a local Ansys Installation. Please provide also the path
# to an empty directory where to store the Ansys Dynamic Reporting database.
#

import ansys.fluent.core as pyfluent
from ansys.pyensight.core import LocalLauncher
import ansys.dynamicreporting.core as adr
import os

os.environ["AWP_ROOT241"]=r"""C:\Program Files\ANSYS Inc\v241"""

ansys_loc = r"""C:\Program Files\ANSYS Inc\v241"""
db_dir = r"""C:\fluent_workflow\db_dir"""


###############################################################################
# Start the applications
# ----------------------
#
# Let's start an instance for each of the Ansys applications we want to use.
# Fluent will be launched with Beta features enabled. We also create a
# sample.dvs file where to store the output from the parameter study. 
#

flsession = pyfluent.launch_fluent(product_version="24.1.0", version="3d", mode="solver", processor_count=4)
enlauncher = LocalLauncher(ansys_installation = ansys_loc)
ensession = enlauncher.start()
adr_session = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir)
session_guid = adr_session.start(create_db=True)
port = 12345
try:
    os.remove("sample.dvs")
except (FileNotFoundError, OSError):
    pass
with open("sample.dvs", "w") as dvsfile:
    dvsfile.write('#!DVS_CASE 1.0\n')
    dvsfile.write('SERVER_PORT_BASE={}\n'.format(port))
    dvsfile.write('SERVER_PORT_MULT=1\n')


###############################################################################
# Run the Fluent job
# ------------------
#
# We are now ready to run a parameter study with Ansys Fluent. This section
# assumes you have an input stairmand_mphase_v19.cas file. You can download
# a copy of the example file `here <_inputfile>`_.
#

flsession.read_case("stairmand_mphase_v19.cas")
flsession.execute_tui("def beta yes yes")
settings = [
    "'cyclone'",
    "yes",
    '"localhost"',
    f"{port}",
    "4",
    "*",
    "()",
    "cell-element-type",
    "cell-id", 
    "cell-type", 
    "pressure",
    "gas-skin-friction-coef",
    "gas-viscosity-lam", 
    "gas-velocity-magnitude", 
    "gas-wall-shear", 
    "gas-x-velocity",
    "gas-wall-shear", 
    "gas-y-velocity",
    "gas-y-wall-shear", 
    "gas-z-velocity",
    "gas-z-wall-shear",
    "gas-vof",
    "solid-skin-friction-coef",
    "solid-viscosity-lam", 
    "solid-velocity-magnitude", 
    "solid-wall-shear", 
    "solid-x-velocity",
    "solid-wall-shear", 
    "solid-y-velocity",
    "solid-y-wall-shear", 
    "solid-z-velocity",
    "solid-z-wall-shear",
    "solid-vof",
    "mass-imbalance",
    "quit", 
    "no",
    '"export-1"',
    '"time-step"',
    "1"
]
flsession.tui.file.transient_export.ensight_dvs_volume(*settings)
flsession.solution.initialization.hybrid_initialize()
flsession.tui.solve.set.transient_controls.time_step_size(0.005)
flsession.tui.solve.set.transient_controls.number_of_time_steps(250)


###############################################################################
# Multiple Threads
# ----------------
#
# Set up multiple threads to allow Ansys Fluent to run while still issuing
# python commands. Make sure Ansys EnSight receives the data as it's been
# generated.
#

from threading import Thread
load_dvs = lambda: ensession.load_data(os.path.join(os.getcwd(), "sample.dvs"), monitor_new_timesteps=ensession.MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT)
solve_fluent = lambda: flsession.solution.run_calculation.calculate()
threads = []
for process in [solve_fluent, load_dvs]:
    threads.append(Thread(target=process))
threads[1].start()
threads[0].start()

###############################################################################
# Postprocessing
# --------------
#
# Load a context file in Ansys EnSight to automatically postprocess the results
# of the parameter study that is Ansys Fluent. You can find the context1a.ctx
# and associated files `here <_inputfile>`_.
#

ctx_file = r"""C:\fluent_workflow\context1a.ctx"""
ensession.ensight.file.restore_context(ctx_file)


###############################################################################
# Generate items for the report
# -----------------------------
#
# Generate the items for the report - both text items and from within Ansys
# EnSight.
#

my_text = adr_session.create_item()
my_text.item_text = "<h1>Example PyFluent PyEnSight PyADR Working Test</h1>This is the first of many items"
ensession.ensight.utils.export.animation("export.mp4",width=1920,height=1080,frames_per_second=10)
my_animation = adr_session.create_item()
my_animation.item_animation = "export.mp4"
ensession.ensight.utils.export.image("export.png",width=1920,height=1080)
my_image = adr_session.create_item()
my_image.item_image = "export.png"
taglist = " part_type=Clip " + " partColorby=Pressure"
my_image.set_tags(taglist)
ensession.ensight.part.select_all()
ensession.ensight.savegeom.format("avz")
ensession.ensight.savegeom.select_all_steps()
ensession.ensight.savegeom.save_geometric_entities(r"""C:\fluent_workflow\export_avz""")
my_scene = adr_session.create_item()
my_scene.item_scene = r"""C:\fluent_workflow\export_avz.avz"""


###############################################################################
#
# Visualize the report
# --------------------
#
# Visualize the report. Note that since we are not using any report template,
# the items will show in the order they have been generated.
#

# sphinx_gallery_thumbnail_path = '_static/default_thumb.png'
adr_session.visualize_report()
