"""
.. _customized_report_embed:

Embed report and overwrite styles
=====================================

Applying the new custom web component ``<adr-report></adr-report>`` as an alternative of
using ``<iframe></iframe>`` to fetch and embed a report in the external web application.

.. note::
   This example assumes that you have a local Ansys installation with a version v251 or
   beyond. For this feature, as of **25R1**, **Panel** and **Tabs** are the only layout
   templates available for style overwrite, more templates will be included in the
   future release.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service using an existing database that has
# at least 1 report template being defined.

###############################################################################
# .. note::
#   The code here to start an ADR service and the following Python code to initiate
#   a **Flask** server should all be put together in the ``app.py`` file. The
#   file structure of this example is demonstrated at the end of the tutorial.


from random import random as r

import numpy as np

import ansys.dynamicreporting.core as adr
from ansys.dynamicreporting.core.utils import report_utils

# Find a random open port for the ADR service & define the ADR root domain
adr_port = report_utils.find_unused_ports(1)[0]
root = f"http://127.0.0.1:{adr_port}/"

# start an ADR server
adr_service = adr.Service(
    # (installation version should be >= v251)
    ansys_installation=r"C:\Program Files\ANSYS Inc\v251",
    # Unlike previous examples, the db_directory MUST have an existing database in it
    db_directory=r"D:\tmp\new_db",
    port=adr_port,
)

adr_service.start()

# Select report based upon the matched report name
my_report = adr_service.get_report(report_name="Top Level Report")

###############################################################################
# Set up proxy server
# -------------------
#
# Applying the custom web component to tunnel the report over to the external web
# app requires additional server settings to bypass potential **cross-origin
# resource sharing (CORS) error**. See below diagram illustrating the CORS error
# process:

###############################################################################
# .. figure:: /_static/02_customized_report_embed_0.png
#
#    *By default, browsers will block requests from the client side towards the server side of a different domain*

###############################################################################
# To resolve the CORS error, instead of sending requests from the client side,
# using the server that powers the external web app to proxy the requests.
# Adding **3 types of REST calls** reroute settings to set up the proxy server:

###############################################################################
# * Reroute **GET** Request to the main ADR report page (for HTML content)
# * Reroute **GET** Request to access the ADR report's **static** files
# * Reroute **GET** Request to access the ADR report's **media** files

###############################################################################
# The below diagram illustrates the proxy server concept to bypass CORS error:

###############################################################################
# .. figure:: /_static/02_customized_report_embed_1.png
#
#    *Bypass the CORS error by using the app server to proxy the request*

###############################################################################
# This example is using **Flask** as the backend framework, but the same concept
# is applicable to other backend structures such as Node.js.

###############################################################################
# .. note::
#   Using **Flask** as the backend framework to set up proxy will serve the static
#   assets like CSS, JS files in its "static" directory, the GET request to ADR's
#   static assets may cause request conflicts (same for requesting "media" files).
#
#   Therefore, the below code example includes rewriting request for "static" files
#   and "media" files to avoid such conflicts, please refer to the **highlighted
#   code block**.

###############################################################################
#  .. code-block:: python
#     :emphasize-lines: 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
#
#      from flask import Flask, Response, redirect, request  # noqa: F811, E402
#      from requests import get  # noqa: F811, E402
#
#       # init Flask app
#       app = Flask(__name__)
#
#       # Flask serves its own static files from "/static/"" directory by default, to avoid conflicts occur while getting
#       # report's "static" files, intercept the GET request and rewrite the route from "/static/" to "/adr_static/"...
#       # if the given patterns match (*Do the route rewrite for media files too)
#       @app.before_request
#       def intercept_request():
#           # rewrite GET request path to ADR "static" files if the given pattern(s) match(es)
#           if (
#               request.path.startswith("/static/website/content")
#               or request.path.startswith("/static/website/scripts")
#               or request.path.startswith("/static/ansys")
#           ):
#               static_path = request.path.replace("/static/", "/adr_static/", 1)
#               return redirect(static_path)
#
#           # rewrite GET request path to ADR "media" files if the given pattern(s) match(es)
#           if request.path.startswith("/media/"):
#               static_path = request.path.replace("/media/", "/adr_media/", 1)
#               return redirect(static_path)
#
#       # reroute GET request path with a pattern of "/report/..." to main report HTML page
#       @app.route("/report/<path:subpath>", methods=["GET"])
#       def proxy_core(subpath):
#           subpath = subpath.split("/")
#           # Construct the target URL for request reroute to get the report page HTML
#           target_url = f"{root}/reports/report_display/?report_table_length=10&view={subpath[0]}&usemenus=on&dpi=120&pwidth=12.80&query={subpath[1]}"
#           resp = get(target_url)
#           return Response(resp.content, content_type=resp.headers["Content-Type"])
#
#       # reroute GET request path with a pattern of "/adr_static/..." to access report "static" files
#       @app.route("/adr_static/<path:subpath>", methods=["GET"])
#       def proxy_static(subpath):
#           # Construct the target URL for request reroute to get the report static files
#           static_url = f"{root}/static/{subpath}"
#           resp = get(static_url)
#           return Response(resp.content, content_type=resp.headers["Content-Type"])
#
#       # reroute GET request path with a pattern of "/adr_media/..." to access report "media" files
#       @app.route("/adr_media/<path:subpath>", methods=["GET"])
#       def proxy_media(subpath):
#           # Construct the target URL for request reroute to get the report media files
#           media_url = f"{root}/media/{subpath}"
#           resp = get(media_url)
#           return Response(resp.content, content_type=resp.headers["Content-Type"])
#


###############################################################################
# HTML structure and report style overwrite
# ------------------------------------------
#
# The following code snippet is a basic HTML structure in the ``index.html``
# file to serve the web component, its script, and the style sheet for style
# overwrite (if any). For reference, here is the file structure of this example:

###############################################################################
#  .. code::
#
#     example_root /
#        ├── app.py (start an ADR service & initi Flask proxy server)
#        ├── static / style.css
#        ├── templates / index.html
#

###############################################################################
# .. note::
#   The CSS stylesheet to overwrite report styles should be added as a ``<link>`` tag
#   inside the ``<head></head>`` section of the HTML file. The ``href`` attribute
#   of the ``<link>`` tag displays the CSS file path, which should then be passed as
#   the value of the ``style_path`` argument in the
#   :func:`get_report_component(style_path="...")<ansys.dynamicreporting.core.Report.get_report_component>`
#   in order to overwrite the styles.


###############################################################################
# .. code-block:: html
#    :emphasize-lines: 8
#
#      <!DOCTYPE html>
#      <html lang="en">
#        <head>
#          <meta charset="UTF-8">
#          <meta name="viewport" content="width=device-width, initial-scale=1.0">
#          <title>Document</title>
#          <!-- external CSS file for style overwrite -->
#          <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
#        </head>
#        <body>
#          <!-- <adr-report> web component generated by PyADR API from the backend -->
#          <main id="dash-container">
#             {{ custom_html_element | safe }}
#          </main>
#
#          <!-- <adr-report> web component <script> define generated by PyADR API from the backend -->
#          <script type="text/javascript">
#             {{ inline_js | safe }}
#          </script>
#        </body>
#      </html>
#
#


###############################################################################
# Initiate web component to embed the report
# ------------------------------------------
#
# At this point, all the essential server settings have been included, now it's time
# to add the custom web component and its script in the external web app by PyADR
# method :func:`get_report_component<ansys.dynamicreporting.core.Report.get_report_component>`
# and :func:`get_report_script<ansys.dynamicreporting.core.Report.get_report_script>`.
# As mentioned above, if a CSS file has been included for style overwrite, the file path
# should be passed in the ``style_path`` argument of the ``get_report_component`` method.

###############################################################################
#  .. code-block:: python
#     :emphasize-lines: 13
#
#      from flask import render_template, url_for  # noqa: F811, E402
#
#      # root domain
#      @app.route("/")
#      def index():
#          return render_template(
#              "index.html",
#              # inject the report fetch web component html
#              custom_html_element = my_report.get_report_component(
#                  # Prefix of the proxy request to main report HTML content
#                  prefix = "report",
#                  # Optional argument for style overwrite (Using external CSS file)
#                  style_path = url_for("static", filename = "style.css"),
#              ),
#              # inject the report fetch web component script logic
#              inline_js = my_report.get_report_script(),
#      )
#
#      # Run the Flask server at port 5000
#      if __name__ == "__main__":
#          app.run(host = "127.0.0.1", port = 5000)
#

################################################################################
# The below screenshot demonstrates the simple style overwrite result for report's
# **panel** layouts.

###############################################################################
# .. figure:: /_static/02_customized_report_embed_2.png
#
#    *A screenshot of report style overwrite for the Panel layouts*

###############################################################################
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk. To stop the Flask server in this example,
# a ``Keyboardinterrupt`` like (Ctrl + C) will shut down the server.

# sphinx_gallery_thumbnail_path = '_static/00_complete_report_0.png'
adr_service.stop()
