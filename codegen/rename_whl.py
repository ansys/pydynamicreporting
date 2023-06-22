import datetime
import glob
import os

date_tag = datetime.datetime.now().strftime("%Y%m%d%H%M")
for name in glob.glob("dist/*.whl"):
    chunks = name.split("-")
    if len(chunks) == 5:
        chunks.insert(2, date_tag)
        new_name = "-".join(chunks)
        os.rename(name, new_name)
