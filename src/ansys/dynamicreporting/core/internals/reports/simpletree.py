#
# *************************************************************
#  Copyright 2021 ANSYS, Inc.
#  All Rights Reserved.
#
#  Restricted Rights Legend
#
#  Use, duplication, or disclosure of this
#  software and its documentation by the
#  Government is subject to restrictions as
#  set forth in subdivision [(b)(3)(ii)] of
#  the Rights in Technical Data and Computer
#  Software clause at 52.227-7013.
# *************************************************************
#
import copy


class SimpleTree:
    """
    Wrapper around the Python tree payload from an 'tree' Item.
    It holds the internal representation of the tree flattened
    out into a dense table format, a collection of rows with
    an external rowlist. The merging mechanism is included in
    this class.

    Note: a tree is a hierarchy of dictionaries.  Each dictionary has
    the following keys required:
        'name' -> string name of the item
        'key' -> string key for the item (think "hidden name")
        'value' -> a single value or a list of values for multiple columns

    Optional keys include:
        'children' -> a list of dictionaries in the same format
        'state' -> the initial display state of the item
        'header' -> a boolean marking this item as a header
    """

    def __init__(self, tree_data: list, match_by: str = 'both', fill: str = '', rules: str = 'all',
                 header: object = None):
        #  This algorithm works by flattening out the tree into rows.  Each row is given a name
        #  that is used when considering if two rows are to be considered the same.  The row names
        #  are formed using the name and or key item values and the name of the parent item.  The
        #  matching rules may be: 'key', 'name', 'both', see _build_name()
        self._match = match_by
        # fill is the value to be used to fill in any "cells" that are undefined during
        # the merge process:
        self._fill = fill
        # The merging rules can be:
        # 'all' - all rows from all trees in the output
        # 'common' - only the common rows in the output
        # 'first' - only the rows in the first tree are returned
        self._merge_rules = rules
        # If the header option has been selected, header will be a string value to use as the
        # header string for the data values of this tree.
        self._header_value = header
        self._header_list = None
        # This tracks the current total number of value columns in the tree.  This number is
        # recomputed as each additional trees are merged in.
        self._num_columns = 0
        # This is a copy of the input tree
        self._tree = list()
        # the names and items of the tree decomposed into rows
        self._rownames = list()
        self._rowdata = list()
        # used when evaluating 'common' merge rule to remove unmatched rows.
        self._untouched_rows = None
        # convert the input tree into the row format
        self._parse_tree(tree_data)

    def _build_name(self, name: str, key: str, parent: str):
        # Row names are used to see if a row in one tree matches
        # the name in another tree.  Every item in the tree has a rowname
        # row names have the format:  {parentitemname}|{itemname}
        # where the item name can be {name}, {key}, or {name/key}
        itemname = name
        if self._match == 'both':
            itemname = name + '/' + key
        elif self._match == 'key':
            itemname = key
        itemname = parent + '|' + itemname
        return itemname

    def _normalize_columns(self):
        # find the maximum number of columns
        self._num_columns = 0
        for item in self._rowdata:
            value = item['value']
            # convert singles into lists as we go
            if type(value) != list:
                value = [value]
                item['value'] = value
            self._num_columns = max(self._num_columns, len(value))
        # fill in the missing values
        for item in self._rowdata:
            value = item['value']
            if len(value) < self._num_columns:
                while len(value) < self._num_columns:
                    value.append(self._fill)
                item['value'] = value

    def _parse_walk_item(self, item: dict, parent_name: str):
        # we have a new row
        itemname = self._build_name(item['name'], item['key'], parent_name)
        self._rownames.append(itemname)
        self._rowdata.append(item)
        for child in item.get('children', list()):
            self._parse_walk_item(child, itemname)

    def _parse_tree(self, tree: list):
        self._rownames = list()
        self._rowdata = list()
        self._tree = copy.deepcopy(tree)
        for item in self._tree:
            self._parse_walk_item(item, '')
        self._normalize_columns()
        # if we have a header value, start with a collection of named values
        if self._header_value is not None:
            self._header_list = [self._header_value]
            self._header_list += (self._num_columns - 1) * ['']

    def to_payload_list(self, header: bool = True) -> list:
        tree = list()
        # do we have a header?
        if (self._header_list is not None) and header:
            header = dict(name='', key='generated_header', value=self._header_list, header=True)
            tree.append(header)
        # include all of the top level items (items with item names that have no parent string)
        for item, name in zip(self._rowdata, self._rownames):
            test_name = self._build_name(item['name'], item['key'], '')
            if test_name == name:
                tree.append(item)
        return tree

    def _find_item(self, name: str):
        if name in self._rownames:
            return self._rownames.index(name)
        return None

    def _append_values(self, idx: int, values: list):
        for v in values:
            self._rowdata[idx]['value'].append(v)

    def _build_new_item(self, item: dict, prepend: bool = True) -> dict:
        # build the new item to be inserted
        new_item = dict(name=item['name'], key=item['key'], value=item['value'])
        # if we plan to add this to a working tree, the initial columns are the fill value
        if prepend:
            new_item['value'] = self._num_columns * [self._fill] + item['value']
        # copy specific keys from the source dictionary
        for key in ['state', 'header']:
            if key in item:
                new_item[key] = item[key]
        return new_item

    def _merge_item(self, item: dict, parent_name: str):
        # build the name against the source tree
        itemname = self._build_name(item['name'], item['key'], parent_name)
        # match against the target tree
        # if there is a match, we can append the row
        idx = self._find_item(itemname)
        # Simplest case, if there is a match, simply append the values
        if idx is not None:
            self._append_values(idx, item['value'])
            # if a 'common' merge, we can remove this row from the untouched list
            if self._merge_rules == 'common':
                if idx in self._untouched_rows:  # technically, this should never be false, but just in case
                    self._untouched_rows.remove(idx)
        # If 'all', the new row needs to be inserted somewhere
        elif self._merge_rules == 'all':
            # Note, in all cases we are walking the tree top-down, if we are in a child of the tree
            # being merged in, the parent must exist in the output tree as we would have inserted
            # it in the root case.  Thus, we can check on the location of the parent row.  If there
            # is no parent row, simply append to the root, otherwise we will append to the parent item.
            parent_idx = self._find_item(parent_name)
            # build the new item to be inserted
            new_item = self._build_new_item(item)
            if parent_idx is None:
                # Append the item to the list, the top of the tree basically, see comments above
                self._rownames.append(itemname)
                self._rowdata.append(new_item)
            else:
                # Append the item to the parent item
                # Make sure the parent item has 'children'
                if 'children' not in self._rowdata[parent_idx]:
                    self._rowdata[parent_idx]['children'] = list()
                # next n items in the list are the children
                num_children = len(self._rowdata[parent_idx]['children'])
                # insert the new item into the list at the end of the child list
                self._rownames.insert(parent_idx + 1 + num_children, itemname)
                self._rowdata.insert(parent_idx + 1 + num_children, new_item)
                # add the item to the children list
                self._rowdata[parent_idx]['children'].append(new_item)
        # now, handle the children
        for child in item.get('children', list()):
            self._merge_item(child, itemname)

    def _count_children(self, item: dict) -> int:
        count = 0
        for child in item.get('children', list()):
            count += self._count_children(child)
            count += 1
        return count

    def merge_payload(self, tree: 'SimpleTree'):
        # track if a row was not referenced, start with them all
        if self._merge_rules == 'common':
            self._untouched_rows = list(range(len(self._rownames)))
        # Merge the input tree into the current tree
        for item in tree.to_payload_list(header=False):
            self._merge_item(item, '')
        # if 'common', remove the untouched rows from the tree
        if self._merge_rules == 'common':
            # Walk from the highest index to the lowest index to keep the
            # indices valid
            self._untouched_rows.sort(reverse=True)
            for idx in self._untouched_rows:
                # Remove this row because it is not in common
                # Remove any references to this item in the children lists
                item = self._rowdata[idx]
                for target in self._rowdata:
                    if item in target.get('children', list()):
                        target['children'].remove(item)
                # Should this remove all the children as well?  yes for now
                num_items = 1 + self._count_children(item)
                self._rowdata = self._rowdata[:idx] + self._rowdata[idx + num_items:]
                self._rownames = self._rownames[:idx] + self._rownames[idx + num_items:]
            self._untouched_rows = None
        # Fix up the column fill and count
        original_column_count = self._num_columns
        self._normalize_columns()
        # If we have a header, add the incoming tree header value (if any).  Once for
        # each added column.
        if self._header_list is not None:
            header_value = tree._header_value
            if header_value is None:
                header_value = ''
            # We will use the 'header_value' for the first new column and then empty column headers
            # for subsequent columns added with this merge. For example: ['Name', '', ''] for three columns.
            if self._num_columns > original_column_count:
                # We can at least add one...
                self._header_list.append(header_value)
                original_column_count += 1    # we will add only less '' header column
            self._header_list += (self._num_columns - original_column_count) * ['']


if __name__ == "__main__":
    def print_tree(tree: list, indent: str = '', full: bool = False):
        for item in tree:
            if full:
                print("{}{}: key:{} value:{} state:'{}' header:{}".format(indent, item['name'], item['key'],
                                                                          item['value'], item.get('state', ''),
                                                                          item.get('header', False)))
            else:
                print("{}{}:{} {}".format(indent, item['name'], item['key'], item['value']))
            if 'children' in item:
                print_tree(item['children'], indent + '  ', full=full)


    def build_item(name: str, key: str, value: object = '', children=None) -> dict:
        item = dict(name=name, key=key, value=value)
        if children is not None:
            item['children'] = children
        return item


    leaves_a1 = list()
    leaves_a1.append(build_item('leaf 1 1', 'leaf 1 1', 1.0))
    leaves_a1.append(build_item('leaf 1 2', 'leaf 1 2', 2.0))
    leaves_a1.append(build_item('leaf 1 3', 'leaf 1 3', 3.0))
    leaves_a2 = list()
    leaves_a2.append(build_item('leaf 2 1', 'leaf 2 1', ['', 'Hello']))
    leaves_a2.append(build_item('leaf 2 2', 'leaf 2 2', ['', 'Bye']))
    leaves_a2.append(build_item('leaf 2 3', 'leaf 2 3', ['', 'Foo']))
    top_a1 = build_item("top 1", 'top 1', ['Numbers', 'strings'], children=leaves_a1)
    top_a2 = build_item("top 2", 'top 2', ['Numbers', 'strings'], children=leaves_a2)
    top_a3 = build_item("top 3", 'top 3', [100, 200])
    tree_a = [top_a1, top_a2, top_a3]
    print_tree(tree_a)

    print("Simple tree (merge) smoke test")
    print("\nTree test I: both")
    print(20 * '-')
    tgt = SimpleTree(tree_a)
    tree_b = copy.deepcopy(tree_a)
    tree_b[1]['name'] = 'Fish'
    src = SimpleTree(tree_b)
    tgt.merge_payload(src)
    print_tree(tgt.to_payload_list())
    print("\nTree test II: common")
    print(20 * '-')
    tgt = SimpleTree(tree_a, rules='common')
    tree_b = copy.deepcopy(tree_a)
    tree_b[1]['name'] = 'Fish'
    src = SimpleTree(tree_b)
    tgt.merge_payload(src)
    print_tree(tgt.to_payload_list())
    print("\nTree test III: first")
    print(20 * '-')
    tgt = SimpleTree(tree_a, rules='first', fill='N/A')
    tree_b = copy.deepcopy(tree_a)
    tree_b[1]['name'] = 'Fish'
    src = SimpleTree(tree_b, fill='N/A')
    tgt.merge_payload(src)
    print_tree(tgt.to_payload_list())
    print("\nTree test IV: keys and headers")
    print(20 * '-')
    tgt = SimpleTree(tree_a, match_by='key', header="Tree A")
    tree_b = copy.deepcopy(tree_a)
    tree_b[1]['name'] = 'Fish'
    src = SimpleTree(tree_b, header="Tree B")
    tgt.merge_payload(src)
    print_tree(tgt.to_payload_list())
