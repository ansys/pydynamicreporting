import glob
import os
import shutil

dir_list = [
    "tests/test_data/ami",
    "tests/test_data/dam_break",
    "tests/test_data/query_db/nginx",
    "tests/test_data/scenes/scene",
    "tests/test_data/viewer_test/",
]
dir_list.extend(
    ["tests/test_data/ansys", "tests/test_data/media", "tests/test_data/webfonts/", "htmltest/"]
)
dir_list.append("tests/test_data/create_delete/")
dir_list.append("tests/test_data/create_twice/")
dir_list.append("tests/test_data/newcopytemp/")
dir_list.append("tests/test_data/newcopy/")
for i_dir in dir_list:
    try:
        shutil.rmtree(i_dir)
    except Exception:
        pass


file_list = glob.glob("tests/test_data/*.txt")
file_list.append("tests/test_data/query_db/nexus.log")
file_list.append("tests/test_data/query_db/nexus.status")
file_list.append("tests/test_data/query_db/shutdown")
file_list.append("tests/test_data/index.html")
file_list.append("tests/test_data/index.raw")
file_list.extend(glob.glob("tests/outfile*.txt"))
file_list.append("mypresentation")
file_list.append("mytest.pdf")
for i_file in file_list:
    try:
        os.remove(i_file)
    except Exception:
        pass
