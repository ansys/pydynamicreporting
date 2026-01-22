import xml.etree.ElementTree as eT


def generate() -> None:
    data = eT.Element("Properties")
    data.set("version", "1.0")

    count_parenthesis = 0
    in_prop = False
    got_prop = False
    prop_explanation = False
    tmp_explanation = ""
    str_remove = ["[", "]", "self.tr(", ")", '"', "\n", "\t", "'"]

    tmp_item_type = ""

    in_deep = False
    i_line = 0

    tmp_highlevel = ""
    deep_level = ""
    first_time = True
    in_deep_level = False

    with open("property_dialog.py") as prop_file:
        for line in prop_file:
            i_line += 1
            if "def prop_list(self):" in line:
                in_prop = True
            elif "def handleMenuHovered" in line:
                in_prop = False
            if in_prop:
                for ch in line:
                    if "[" == ch:
                        count_parenthesis += 1
                    elif "]" == ch:
                        count_parenthesis -= 1
                    if count_parenthesis == 3:
                        tmp_item_type += ch
                        got_prop = True
                    if count_parenthesis >= 7 and in_deep is False:
                        in_deep = True
                    if count_parenthesis == 4:
                        if got_prop:
                            for i_str in str_remove:
                                tmp_item_type = tmp_item_type.replace(i_str, "")
                            tmp_item_type = tmp_item_type.replace(",", "")
                            origin_item = eT.SubElement(data, "ItemType")
                            origin_item.set("Type", str(tmp_item_type[:-1]))
                            origin_item.text = str(tmp_item_type)
                            got_prop = False
                            in_deep = False
                        else:
                            tmp_item_type = ""
                        if prop_explanation:
                            for i_str in ["\n", "\t"]:
                                tmp_explanation = tmp_explanation.replace(i_str, "")
                            prop_name = tmp_explanation.split("self.tr(")[1].split(")")[0][1:-1]
                            prop_attr = tmp_explanation.split("self.tr(")[1].split(")")[1]
                            for i_str in str_remove:
                                prop_attr = prop_attr.replace(i_str, "")
                                prop_name = prop_name.replace(i_str, "")
                            prop_attr = prop_attr.replace(" ", "")
                            prop_attr = prop_attr.replace(",", "")
                            if len(tmp_explanation.split("self.tr(")) > 2:
                                prop_desc = tmp_explanation.split("self.tr(")[2]
                                for i_str in ["\n", '"', ")", "                         "]:
                                    prop_desc = prop_desc.replace(i_str, "")
                            else:
                                prop_desc = "No options"
                            if count_parenthesis == 4:
                                if in_deep is False:
                                    if prop_name:
                                        if len(prop_attr) > 1:
                                            expl_item = eT.SubElement(origin_item, str(prop_attr))
                                            expl_item.set("attribute", str(prop_attr))
                                            expl_item.set("attrname", prop_name)
                                            expl_item.text = str(prop_desc)
                                        prop_explanation = False
                                        tmp_explanation = ""
                    if count_parenthesis >= 5:
                        prop_explanation = True
                        tmp_explanation += ch
                    # Section for scraping properties that are one layer deeper
                    if count_parenthesis > 3 and in_deep:
                        if first_time:
                            prop_name = tmp_highlevel
                            for i_str in str_remove:
                                prop_name = prop_name.replace(i_str, "")
                            prop_name = prop_name.replace(",", "")
                            tmp_highlevel = ""
                            first_time = False
                        if count_parenthesis >= 7:
                            deep_level += ch
                            in_deep_level = True
                        if count_parenthesis == 6:
                            if in_deep_level:
                                the_split = deep_level.split("self.tr(")[1].split(")")
                                prop_name = the_split[0][1:-1]
                                prop_attr = the_split[1]
                                for i_str in str_remove:
                                    prop_attr = prop_attr.replace(i_str, "")
                                    prop_name = prop_name.replace(i_str, "")
                                prop_attr = prop_attr.replace(" ", "")
                                prop_attr = prop_attr.replace(",", "")
                                if len(deep_level.split("self.tr(")) > 2:
                                    prop_desc = deep_level.split("self.tr(")[2]
                                    prop_desc = prop_desc.replace('"', "")
                                    prop_desc = prop_desc.replace("\n", "")
                                    prop_desc = prop_desc.replace("                         ", "")
                                    prop_desc = prop_desc.rsplit(")", 1)[0]
                                else:
                                    prop_desc = "No options"
                                expl_item = eT.SubElement(origin_item, str(prop_attr))
                                expl_item.set("attribute", str(prop_attr))
                                expl_item.set("attrname", prop_name)
                                expl_item.text = str(prop_desc)
                                deep_level = ""
                                in_deep_level = False

    mydata = eT.tostring(data)
    myfile = open("all_test_prop.txt", "wb")
    myfile.write(mydata)
    myfile.flush()
    myfile.close()


if __name__ == "__main__":
    generate()
