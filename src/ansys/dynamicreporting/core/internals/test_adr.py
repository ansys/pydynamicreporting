from random import random as r

import numpy as np
from ansys.dynamicreporting.core import ADR, Table

opts = {"CEI_NEXUS_DEBUG": "0", "CEI_NEXUS_SECRET_KEY": "h1kuvl)j#e6_7rbhr&f@_3%)$nle*b8t$82wta*e3wu-(5v$$o",
        "CEI_NEXUS_LOCAL_DB_DIR": r"C:\cygwin64\home\vrajendr\ogdocex"}
adr = ADR(r"C:\Program Files (x86)\ANSYSv231",
          opts=opts,
          session="4ee905f0-f611-11e6-8901-ae3af682bb6a",
          dataset="fa473009-deee-34eb-b6b8-8326236ca9a6")
adr.configure()

ics = []
ips = []
zet = []
for i in range(30):
    ics.append(i / 5.0)
    ips.append(np.sin((i + 6 * 0) * np.pi / 10.0) + r() * 0.1)
    zet.append(np.cos((i + 6 * 0) * np.pi / 10.0) + r() * 0.1)

data_table = adr.create_item(Table, name="table1", content=np.array([ics, ips, zet], dtype="|S20"),
                             tags="dp=0 type=hex8")
print(data_table.saved)
data_table.labels_row = ["X", "Sin", "Cos"]
data_table.set_tags("dp=dp0 section=data")
data_table.plot = "line"
data_table.xaxis = "X"
data_table.yaxis = ["Sin", "Cos"]
data_table.xaxis_format = "floatdot0"
data_table.yaxis_format = "floatdot1"
data_table.ytitle = "Values"
data_table.xtitle = "X"

data_table.save()

print(data_table.render({}))

# template_1 = adr.create_template(
#     BasicLayout, name="Simulation Report", parent=None
# )
# template_1.params = '{"HTML": "<h1>Simulation Report</h1>"}'
# template_1.set_filter("A|i_tags|cont|dp=0;")
# template_1.save()
#
# print(template_1.render())
