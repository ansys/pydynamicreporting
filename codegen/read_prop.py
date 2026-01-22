# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os.path
import xml.etree.ElementTree as eT


def generate() -> None:
    root = os.path.dirname(__file__)
    os.chdir(root)

    parser = eT.XMLParser(encoding="utf-8")
    all_prop_file = os.path.join("all_test_prop.xml")
    tree = eT.parse(all_prop_file, parser=parser)
    root = tree.getroot()

    orig_file = os.path.join("adr_utils.txt")
    new_filename = os.path.join("..", "src", "ansys", "dynamicreporting", "core", "adr_utils.py")
    new_file = open(new_filename, "w")
    with open(orig_file) as prop_file:
        for line in prop_file:
            if "table_attr = (" not in line:
                new_file.write(line)
            else:
                new_file.write(line)
                for elem in root:
                    if "TABLE" == elem.attrib["Type"].upper():
                        list_table_attr = []
                        for subelem in elem:
                            list_table_attr.append(subelem.attrib["attribute"])
                        for i_attr, name_attr in enumerate(list_table_attr):
                            if i_attr == (len(list_table_attr) - 1):
                                # row_tags and col_tags are not exposed in the template editor
                                new_file.write(
                                    '    "' + name_attr + '",\n    "row_tags",\n    "col_tags"\n'
                                )
                            else:
                                new_file.write('    "' + name_attr + '",\n')

    new_file.flush()
    new_file.close()

    orig_itemfile = os.path.join("pyadritem.txt")
    new_itemfile = os.path.join("..", "src", "ansys", "dynamicreporting", "core", "adr_item.py")
    new_file = open(new_itemfile, "w")

    with open(orig_itemfile) as prop_file:
        for line in prop_file:
            if "self.table_dict = {}" not in line:
                new_file.write(line)
            else:
                new_file.write(line)
                for elem in root:
                    if "TABLE" == elem.attrib["Type"].upper():
                        for subelem in elem:
                            new_file.write(
                                "        self." + subelem.attrib["attribute"] + " = None\n"
                            )
                            comment_str = '        """' + subelem.attrib["attrname"] + "\n"
                            if subelem.text:
                                desc_str = subelem.text.replace("'", "")
                            else:
                                desc_str = ""
                            if len(desc_str) > 92:
                                idx = desc_str[: (92 - len(desc_str))].rfind(" ")
                                desc_str = desc_str[0:idx] + "\n        " + desc_str[idx + 1 :]
                            comment_str += "\n        " + desc_str + '"""\n'
                            new_file.write(comment_str)

    new_file.flush()
    new_file.close()


if __name__ == "__main__":
    generate()
