"""
.. _complete_report:

Create a report from scratch
============================

To use PyDynamicReporting to build a report from scratch, you start
a new Ansys Dynamic Reporting instance on a new database, populate it,
amd generate a report template. As a result, you get a report.

.. note::
   This example assumes that you have a local Ansys installation.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service with a new database. The path for the
# database directory must be to an empty directory.

import numpy as np

import ansys.dynamicreporting.core as adr

ansys_loc = r"C:\Program Files\ANSYS Inc\v232"
db_dir = r"C:\tmp\new_database"
port = 8080
adr_service = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir, port=port)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create a report template
# ------------------------
#
# Create a report template using the low-level API for Ansys Dynamic Reporting.
#

adr_service = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir)
adr_service.connect(url=f"http://localhost:{port}")
server = adr_service.serverobj

template_003 = server.create_template(
    name="Solution Analysis from Multiphysics simulation", parent=None, report_type="Layout:basic"
)
template_003.params = '{"HTML": "<h1>Solution Report</h1>"}'
template_003.set_filter("A|i_tags|cont|solution=solverA;")
server.put_objects(template_003)

template_011 = server.create_template(
    name="Project Details", parent=template_003, report_type="Layout:basic"
)
template_011.params = (
    '{"TOCitems": 1, "HTML": "<h2>Project Details</h2>", "properties": {"justification": "left"}}'
)
template_011.set_filter("A|i_type|cont|html,string;A|i_tags|cont|text=project_details;")
server.put_objects(template_011)
server.put_objects(template_003)

template_000 = server.create_template(name="TOC", parent=template_003, report_type="Layout:toc")
template_000.params = '{"TOCitems": 1, "HTML": "<h2>Table of Contents</h2>"}'
template_000.set_filter("A|i_name|eq|__NonexistantName__;")
server.put_objects(template_000)
server.put_objects(template_003)

template_004 = server.create_template(
    name="TOC Figures", parent=template_003, report_type="Layout:toc"
)
template_004.params = (
    '{"TOCitems": 0, "TOCfigures": 1, "HTML": "<h2>List of Figures</h2>", "TOCtables": 0}'
)
template_004.set_filter("A|i_name|eq|__NonexistantName__;")
server.put_objects(template_004)
server.put_objects(template_003)

template_014 = server.create_template(
    name="Introduction", parent=template_003, report_type="Layout:panel"
)
template_014.params = '{"TOCitems": 1, "HTML": "<h2>Introduction</h2>", "properties": {"TOCItem": "1", "TOCLevel": "0"}}'
template_014.set_filter("A|i_tags|cont|section=intro;")
server.put_objects(template_014)
server.put_objects(template_003)

template_015 = server.create_template(name="text", parent=template_014, report_type="Layout:basic")
template_015.params = '{"properties": {"TOCItem": "0", "justification": "left"}}'
template_015.set_filter("A|i_type|cont|html,string;")
server.put_objects(template_015)
server.put_objects(template_014)
server.put_objects(template_003)

template_016 = server.create_template(name="img", parent=template_014, report_type="Layout:basic")
template_016.params = (
    '{"properties": {"TOCName": "Multiphysics Workflow", "TOCItem": "", "TOCFigure": "1"}}'
)
template_016.set_filter("A|i_type|cont|image;")
server.put_objects(template_016)
server.put_objects(template_014)
server.put_objects(template_003)

template_005 = server.create_template(
    name="CAD Model Summary", parent=template_003, report_type="Layout:panel"
)
template_005.params = '{"TOCitems": 1, "HTML": "<h2>CAD Model Summary</h2>", "properties": {"TOCItem": "1", "TOCLevel": "0"}}'
template_005.set_filter("A|i_tags|cont|section=cad_summary;")
server.put_objects(template_005)
server.put_objects(template_003)

template_010 = server.create_template(
    name="Summary of the Design Analysis", parent=template_005, report_type="Layout:basic"
)
template_010.params = (
    '{"HTML": "<h3>Summary of the Design Analysis</h3>", "properties": {"TOCLevel": "1"}}'
)
server.put_objects(template_010)
server.put_objects(template_005)
server.put_objects(template_003)

template_018 = server.create_template(
    name="table_params", parent=template_010, report_type="Layout:basic"
)
template_018.params = '{"properties": {"TOCItem": "2"}}'
template_018.set_filter("A|i_type|cont|table;")
server.put_objects(template_018)
server.put_objects(template_010)
server.put_objects(template_005)
server.put_objects(template_003)

template_017 = server.create_template(name="img", parent=template_010, report_type="Layout:basic")
template_017.params = (
    '{"properties": {"TOCItem": "0", "TOCName": "CAD Configuration", "TOCFigure": "1"}}'
)
template_017.set_filter("A|i_type|cont|image;")
server.put_objects(template_017)
server.put_objects(template_010)
server.put_objects(template_005)
server.put_objects(template_003)

template_006 = server.create_template(
    name="Preliminary Analysis Summary", parent=template_003, report_type="Layout:panel"
)
template_006.params = '{"TOCitems": 1, "HTML": "<h2>Preliminary Analysis Summary</h2>", "properties": {"TOCItem": "1", "TOCLevel": "0"}}'
template_006.set_filter("A|i_tags|cont|section=preliminar_summary;")
server.put_objects(template_006)
server.put_objects(template_003)

template_012 = server.create_template(
    name="Results Summary for Preliminary Analysis", parent=template_006, report_type="Layout:basic"
)
template_012.params = (
    '{"HTML": "<h3>Result summary for Preliminar Analysis</h3>", "properties": {"TOCLevel": "1"}}'
)
server.put_objects(template_012)
server.put_objects(template_006)
server.put_objects(template_003)

template_019 = server.create_template(name="img", parent=template_012, report_type="Layout:basic")
template_019.params = (
    '{"properties": {"TOCItem": "0", "TOCName": "Discovery CAD", "TOCFigure": "1"}}'
)
template_019.set_filter("A|i_type|cont|image;")
server.put_objects(template_019)
server.put_objects(template_012)
server.put_objects(template_006)
server.put_objects(template_003)

template_002 = server.create_template(
    name="table_params", parent=template_012, report_type="Layout:basic"
)
template_002.params = '{"properties": {"TOCItem": "2"}}'
template_002.set_filter("A|i_type|cont|table;")
server.put_objects(template_002)
server.put_objects(template_012)
server.put_objects(template_006)
server.put_objects(template_003)

template_007 = server.create_template(
    name="Detailed Analysis Summary", parent=template_003, report_type="Layout:panel"
)
template_007.params = '{"TOCitems": 1, "HTML": "<h2>Detailedy Analysis Summary</h2>\\nDetailed analysis constitutes detailed CFD (Computational Fluid Dynamics) analysis workflow with fluid solver and required data is transferred back to the CAD calibration.", "properties": {"TOCItem": "1", "TOCLevel": "0"}}'
template_007.set_filter("A|i_tags|cont|section=detailed_summary;")
server.put_objects(template_007)
server.put_objects(template_003)

template_020 = server.create_template(name="img", parent=template_007, report_type="Layout:basic")
template_020.params = '{"properties": {"TOCItem": "0", "TOCName": "Mesh Review", "TOCFigure": "1"}}'
template_020.set_filter("A|i_type|cont|image;")
server.put_objects(template_020)
server.put_objects(template_007)
server.put_objects(template_003)

template_013 = server.create_template(
    name="Mesh Summary", parent=template_007, report_type="Layout:basic"
)
template_013.params = (
    '{"properties": {"TOCItem": "1", "TOCLevel": "1"}, "HTML": "<h3>Mesh Summary</h3>"}'
)
template_013.set_filter("A|i_type|cont|table;A|i_tags|cont|table=meshsummary;")
server.put_objects(template_013)
server.put_objects(template_007)
server.put_objects(template_003)

template_021 = server.create_template(
    name="Results Summary of Detailed Analysis", parent=template_007, report_type="Layout:basic"
)
template_021.params = '{"properties": {"TOCItem": "1", "TOCLevel": "1"}, "HTML": "<h3>Results Summary of Detailed Analysis</h3>", "column_count": 1, "column_widths": [1.0]}'
template_021.set_filter("A|i_type|cont|table;A|i_tags|cont|table=results;")
server.put_objects(template_021)
server.put_objects(template_007)
server.put_objects(template_003)

template_001 = server.create_template(name="table", parent=template_021, report_type="Layout:basic")
template_001.params = '{"properties": {"TOCItem": ""}}'
template_001.set_filter("A|i_tags|cont|show=table;")
server.put_objects(template_001)
server.put_objects(template_021)
server.put_objects(template_007)
server.put_objects(template_003)

template_022 = server.create_template(name="plots", parent=template_021, report_type="Layout:basic")
template_022.params = '{"properties": {"TOCItem": "0", "plot": "line", "TOCFigure": "2", "xaxis": "0", "format": "floatdot0"}, "column_count": 2, "column_widths": [1.0, 1.0]}'
template_022.set_filter("A|i_tags|cont|show=plot;")
server.put_objects(template_022)
server.put_objects(template_021)
server.put_objects(template_007)
server.put_objects(template_003)

template_008 = server.create_template(
    name="Results & Conclusion", parent=template_003, report_type="Layout:panel"
)
template_008.params = '{"TOCitems": 1, "HTML": "<h2>Results & Conclusion</h2>", "properties": {"TOCItem": "1", "TOCLevel": "0"}}'
template_008.set_filter("A|i_tags|cont|section=results;")
server.put_objects(template_008)
server.put_objects(template_003)

template_009 = server.create_template(
    name="Results", parent=template_008, report_type="Layout:basic"
)
template_009.params = '{"properties": {"TOCItem": "1", "TOCLevel": "1"}, "HTML": "<h3>Results</h3>\\nResults are feedback for model calibrarion and detailed summary of results as below."}'
template_009.set_filter("A|i_type|cont|image;")
server.put_objects(template_009)
server.put_objects(template_008)
server.put_objects(template_003)

template_023 = server.create_template(
    name="References", parent=template_003, report_type="Layout:basic"
)
template_023.params = '{"TOCitems": 1, "HTML": "<h3>References</h3>", "properties": {"TOCItem": "1", "TOCLevel": "0", "justification": "left"}}'
template_023.set_filter("A|i_tags|cont|section=references;")
server.put_objects(template_023)
server.put_objects(template_003)

###############################################################################
# Verify the report
# -----------------
#
# Use the :func:`get_list_reports<ansys.dynamicreporting.core.Service.get_list_reports>`
# method on the Ansys Dynamic Reporting object to verify that there is one
# top-level report in the database now. This call returns a list of the names
# of the top-level reports.

adr_service.get_list_reports()

###############################################################################
# Create items
# ------------
#
# Now that the report template is set, populate the database with items having
# proper tags and names.
#

a = adr_service.create_item(obj_name="introduction")
a.item_text = "Project Name: Multiphysics Solution<p></p><p></p>\r\n\r\nNote:  <p></p>\r\n\r\n[Images/Json data/plots/tables etc., are getting generated on the fly at each step and getting saved to Ansys Dynamic Reporting database with appropriate tags, based on the report requirement. The report will be generated with pre-defined template] \r\n"
a.set_tags("solution=solverA text=project_details")
b = adr_service.create_item(obj_name="Description")
b.item_text = "[some static content] <p></p>\r\nThe workflow provides calibrarion of the CAD model by high-fidelity 3D physics based solution. \r\nThis workflow ensures model consistency through design cycle - from CAD via Discovery to advanced Electronic-Fluid multi-physics.\r\n"
b.set_tags("solution=solverA section=intro")
b.get_tags()
c = adr_service.create_item(obj_name="Schema")
c.item_image = r"C:\tmp\schema.png"
c.set_tags("solution=solverA section=intro")
d = adr_service.create_item(obj_name="Schema")
d.item_image = r"C:\tmp\sections.png"
d.set_tags("solution=solverA section=cad_summary")
e = adr_service.create_item(obj_name="Schema")
e.item_image = r"C:\tmp\preliminary.png"
e.set_tags("solution=solverA section=preliminar_summary")
f = adr_service.create_item(obj_name="Schema")
f.item_image = r"C:\tmp\solution.png"
f.set_tags("solution=solverA section=detailed_summary")
g = adr_service.create_item(obj_name="param_input")
g.table_dict["rowlbls"] = [
    "Inlet Temperature",
    "Total Losses",
    "Inlet Flow Rate",
    "Shaft Temperature",
    "Shaft Flow Rate",
]
g.item_table = np.array([["67"], ["1.25"], ["4.2"], ["67"], ["4.2"]], dtype="|S20")
g.set_tags("solution=solverA section=cad_summary")
h = adr_service.create_item(obj_name="preliminary_table")
h.table_dict["rowlbls"] = [
    "Max Domain Temp [Celsius]",
    "Water Pressure [Pa]",
    "Water Outlet Temp [Celsius]",
]
h.item_table = np.array([["177"], ["400"], ["67"]], dtype="|S20")
h.set_tags("solution=solverA section=preliminar_summary")
i = adr_service.create_item(obj_name="detailed_mesh_table")
i.table_dict["rowlbls"] = ["Total Cell Count", "Min Orthogal Quality", "Max aspect ratio", "Wrap"]
i.item_table = np.array([["626037"], ["0.2"], ["17.59"], ["0.4"]], dtype="|S20")
i.set_tags("solution=solverA section=detailed_summary table=meshsummary")
table = adr_service.create_item(obj_name="detailed_res_table")
table.table_dict["rowlbls"] = [
    "Max Domain Temp [Celsius]",
    "Water Pressure Drop [Pa]",
    "Water Outlet Temperature [Celsius]",
]
table.item_table = np.array([["177"], ["500"], ["67"]], dtype="|S20")
table.set_tags("show=table table=results section=detailed_summary solution=solverA")
m = adr_service.create_item(obj_name="monitors")
m.table_dict["rowlbls"] = ["Iteration", "Monitor Parameter"]
m.item_table = np.array(
    [
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        ["100", "90", "93", "88", "76", "71", "66", "60", "55", "53", "52"],
    ],
    dtype="|S20",
)
m.set_tags("show=plot table=results section=detailed_summary solution=solverA")
n = adr_service.create_item(obj_name="Convergence")
n.table_dict["rowlbls"] = ["Iteration", "Val 1", "Val 2", "Val 3"]
n.item_table = np.array(
    [
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        ["100", "90", "70", "60", "30", "20", "15", "15", "14", "13", "15"],
        ["87", "85", "81", "80", "73", "60", "46", "20", "18", "17", "10"],
        ["77", "73", "55", "53", "51", "47", "44", "30", "32", "20", "18"],
    ],
    dtype="|S20",
)
n.set_tags("show=plot table=results section=detailed_summary solution=solverA")
o = adr_service.create_item(obj_name="references")
o.item_text = "<ul>\r\n  <li>Author, A. B. C., Author D. E., ... , Publication Year, Book, title, Publisher.</li>\r\n  <li>Author, F. G. H., Author I. J., ... , Publication Year, Book, title, Publisher.</li>\r\n</ul>"
o.set_tags("solution=solverA section=references")

###############################################################################
# Visualize the report
# --------------------
#
# Visualize the report.
#

adr_service.visualize_report(report_name="Solution Analysis from Multiphysics simulation")

###############################################################################
# .. image:: /_static/00_complete_report_0.png
#
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/00_complete_report_0.png'
adr_service.stop()
