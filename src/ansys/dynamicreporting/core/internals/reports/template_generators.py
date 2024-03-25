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
import datetime
import pickle
import platform
from dateutil import parser
import fnmatch
import re
import string
import numpy
import uuid

from django.utils import timezone
from .engine import GeneratorEngine, TemplateEngine
from ..data.templatetags.data_tags import split_quoted_string_list, time_base
from ..data.extremely_ugly_hacks import safe_unpickle
from .simpletree import SimpleTree


def is_simple_number(s, negative=True, decimal=False):
    '''Given a string, are all the characters legal digits'''
    if s == '':
        return False
    start = 0
    if negative and (s[0] == '-'):
        start = 1
    allowed_chars = string.digits
    if decimal:
        allowed_chars += '.'
        if s.count('.') > 1:
            return False
    for c in s[start:]:
        if c not in allowed_chars:
            return False
    return True


class SimpleTable:
    '''Simplified representation of a table item capable of basic manipulations'''

    def __init__(self):
        self.array = numpy.zeros((2, 2), dtype=numpy.double)
        self.row_ids = ['0', '1']
        self.col_ids = ['0', '1']
        self.row_lbls = self.row_ids
        self.col_lbls = self.col_ids
        self.row_map = {}  # row_map[row_index] = output_object_row_index
        self.col_map = {}  # col_map[col_index] = output_object_col_index
        self.row_collision_tag = ""
        self.macro_expansion = False
        self.tags = ""
        self.row_tags = None
        self.col_tags = None

    def resize(self, rows, cols, string_size=0,
               row_lbls=None, col_lbls=None,
               row_tags=None, col_tags=None,
               row_ids=None, col_ids=None, init_value=None):
        if string_size > 0:
            new_type = "|S{}".format(string_size)
        else:
            new_type = numpy.double
        self.array = numpy.zeros((rows, cols), dtype=new_type)
        if init_value is not None:
            try:
                self.array.fill(init_value)
            except:
                pass
        self.row_lbls = row_lbls
        self.col_lbls = col_lbls
        self.row_ids = row_ids
        self.col_ids = col_ids
        self.row_tags = row_tags
        self.col_tags = col_tags

    def rows(self):
        return self.row_ids

    def columns(self):
        return self.col_ids

    @staticmethod
    def find_match(matches, values):
        out = []
        for match in matches:
            # Check for a special case.  If the match is a natural integer, match the index instead
            if is_simple_number(match, negative=False):
                idx = int(match)
                if idx < len(values):
                    out.append(idx)
            else:
                for i in range(len(values)):
                    if fnmatch.fnmatch(str(values[i]), match):
                        out.append(i)
        return out

    def find_rows_match(self, match):
        return self.find_match(match, self.rows())

    def find_columns_match(self, match):
        return self.find_match(match, self.columns())

    def find_row(self, id):
        if id in self.row_ids:
            return self.row_ids.index(id)
        return None

    def find_column(self, id):
        if id in self.col_ids:
            return self.col_ids.index(id)
        return None

    def reorder(self, rows=None, columns=None):
        if (columns is not None) and (len(columns) == len(self.col_ids)):
            ids = []
            lbls = []
            tags = []
            tmp = copy.deepcopy(self.array)
            out = 0
            for i in columns:
                ids.append(self.col_ids[i])
                if self.col_lbls:
                    lbls.append(self.col_lbls[i])
                if self.col_tags:
                    tags.append(self.col_tags[i])
                self.array[:, out] = tmp[:, i]
                out += 1
            self.col_ids = ids
            if lbls:
                self.col_lbls = lbls
            if tags:
                self.col_tags = tags
        if (rows is not None) and (len(rows) == len(self.row_ids)):
            ids = []
            lbls = []
            tags = []
            tmp = copy.deepcopy(self.array)
            out = 0
            for i in rows:
                ids.append(self.row_ids[i])
                if self.row_lbls:
                    lbls.append(self.row_lbls[i])
                if self.row_tags:
                    tags.append(self.row_tags[i])
                self.array[out, :] = tmp[i, :]
                out += 1
            self.row_ids = ids
            if lbls:
                self.row_lbls = lbls
            if tags:
                self.row_tags = tags
        return

    def remove_rows_columns(self, rows=None, columns=None):
        rows = rows or []
        columns = columns or []
        if rows:
            self.array = numpy.delete(self.array, rows, 0)
            ids = []
            lbls = []
            tags = []
            for i in range(len(self.row_ids)):
                if i not in rows:
                    ids.append(self.row_ids[i])
                    if self.row_lbls:
                        lbls.append(self.row_lbls[i])
                    if self.row_tags:
                        tags.append(self.row_tags[i])
            self.row_ids = ids
            if lbls:
                self.row_lbls = lbls
            if tags:
                self.row_tags = tags
        if columns:
            self.array = numpy.delete(self.array, columns, 1)
            ids = []
            lbls = []
            tags = []
            for i in range(len(self.col_ids)):
                if i not in columns:
                    ids.append(self.col_ids[i])
                    if self.col_lbls:
                        lbls.append(self.col_lbls[i])
                    if self.col_tags:
                        tags.append(self.col_tags[i])
            self.col_ids = ids
            if lbls:
                self.col_lbls = lbls
            if tags:
                self.col_tags = tags

    def from_item(self, item, column_labels_as_ids, column_id_row, initial_transpose, index=0, params=None):
        if params is None:
            params = {}
        collision_tag = params.get("collision_tag", '')  # tag to use on row merges that need tag-base names
        from ..data.models import Item
        data = safe_unpickle(item.payloaddata)
        self.array = data['array']
        row_lbls = Item.get_row_labels(data)
        col_lbls = Item.get_column_labels(data)
        num_rows, num_cols = self.array.shape
        self.row_ids = row_lbls
        if self.row_ids is None:
            self.row_ids = [str(i) for i in range(num_rows)]
        self.col_ids = col_lbls
        if self.col_ids is None:
            self.col_ids = [str(i) for i in range(num_cols)]
        self.row_lbls = row_lbls
        self.col_lbls = col_lbls
        # copy over tags
        self.tags = item.tags
        self.row_tags = Item.get_row_tags(data, default=[item.tags] * num_rows)
        self.col_tags = Item.get_column_tags(data, default=[item.tags] * num_cols)
        # rotate the inputs if needed
        if initial_transpose:
            self.transpose()
        # fix up the column ids
        if column_labels_as_ids == 0:
            row = self.find_row(str(column_id_row))
            if row is not None:
                self.col_ids = [str(i) for i in self.array[row]]
        # what tag should be used for row renaming...
        if '{{' in collision_tag and '}}' in collision_tag:
            # Starting from 24.1, support macro expansions for renaming rows
            self.macro_expansion = True
            # Do not modify the context. Work on a deep copy of it.
            local_ctx = copy.deepcopy(params)
            # A few built-in tags that access item fields. We can safly assume here
            # that params contains a non-empty "collision_tag field"
            builtintags = dict()
            builtintags['{{_index_}}'] = str(index)
            builtintags['{{_guid_}}'] = str(item.guid)
            builtintags['{{_name_}}'] = str(item.name)
            builtintags['{{_source_}}'] = str(item.source)
            # rowname will be substitute later. Need to remove the {{ }} syntax or the expansion will fail
            builtintags['{{_rowname_}}'] = '_ROWNAME_'
            for key in builtintags.keys():
                local_ctx["collision_tag"] = local_ctx["collision_tag"].replace(key, builtintags[key])
            tmp = item.get_indexed_default(data, ctx=local_ctx, idx=0, key='collision_tag', default=None, wildcard='*')
            # if still some {{}} that has not been found, simply remove it from the string. Might be a missing wildcarded tag
            re.sub(r'\{{.*?}\}', '', tmp)
            self.row_collision_tag = tmp
        else:
            # Backward compatibility for versions prior to 24.1 In those versions, 
            # only a single string corresponding to the tag name or one of the 
            # built-in tags are supported
            self.macro_expansion = False
            try:
                tag_value = item.search_tag(collision_tag)
                # A few built-in tags that access item fields
                if tag_value is None:
                    if collision_tag == '_index_':
                        tag_value = str(index)
                    elif collision_tag == '_guid_':
                        tag_value = str(item.guid)
                    elif collision_tag == '_name_':
                        tag_value = str(item.name)
                    elif collision_tag == '_source_':
                        tag_value = str(item.source)
            except:
                tag_value = None
            if tag_value is not None:
                self.row_collision_tag = tag_value

    def transpose(self):
        self.row_ids, self.col_ids = (self.col_ids, self.row_ids)
        self.row_lbls, self.col_lbls = (self.col_lbls, self.row_lbls)
        self.row_tags, self.col_tags = (self.col_tags, self.row_tags)
        self.array = self.array.transpose()

    def sort_rows(self, sorting):
        # for each column, what direction
        directions = []
        for col_name in sorting:
            directions.append(col_name[0] == '-')
        # build rows: [row index, primary column, secondary column, ...]
        data = []
        # for each row
        for row_idx in range(len(self.row_ids)):
            columns = [row_idx]  # start with the index
            for col_name in sorting:
                v = ""
                # special case for the row/column labels
                if col_name[1:] == 'Labels':
                    v = self.row_ids[row_idx]
                else:
                    if col_name[1:] in self.col_ids:
                        col_idx = self.col_ids.index(col_name[1:])
                        v = self.array[row_idx, col_idx]
                columns.append(v)
            data.append(columns)
        # sort the row indices in inverse order
        for i in reversed(range(len(directions))):
            data.sort(key=lambda row: row[i + 1], reverse=directions[i])
        # Apply the sort using the new indices...
        new_rows = []
        new_ids = []
        new_lbls = []
        new_row_tags = []
        for row in data:
            row_idx = row[0]
            new_rows.append(self.array[row_idx])
            new_ids.append(self.row_ids[row_idx])
            if self.row_lbls:
                new_lbls.append(self.row_lbls[row_idx])
            if self.row_tags:
                new_row_tags.append(self.row_tags[row_idx])
        self.array = numpy.vstack(new_rows)
        self.row_ids = new_ids
        if new_lbls:
            self.row_lbls = new_lbls
        if new_row_tags:
            self.row_tags = new_row_tags
        return

    def is_numeric(self):
        # numpy.string_ is an alias for numpy.bytes_
        # to refer to actual strings, use numpy.str_
        # in our case, the array was created with '|S', which is bytes.
        return self.array.dtype.type != numpy.string_

    def string_size(self):
        if self.is_numeric():
            return 0
        return self.array.dtype.itemsize

    def make_numeric(self, undefined_value=numpy.nan):
        if self.is_numeric():
            return
        tmp = numpy.zeros(self.array.shape, dtype=numpy.double)
        for i in range(tmp.shape[0]):
            for j in range(tmp.shape[1]):
                v = self.array[i, j]
                if v == 'nan':
                    v = numpy.nan
                else:
                    try:
                        v = float(v)
                    except Exception:
                        # We would like to try handling it as date/time string as well
                        try:
                            dt = parser.parse(v)
                            # We might need to add a timezone...
                            if dt.tzinfo is None:
                                dt = timezone.make_aware(dt, timezone=timezone.get_current_timezone())
                            v = (dt - time_base).total_seconds()
                        except Exception:
                            v = undefined_value
                tmp[i, j] = v
        self.array = tmp

    def to_item(self, name, dataset=None, session=None):
        from ..data.models import Item, Session, Dataset
        item = Item()
        item.guid = uuid.uuid4()
        if session:
            item.session = session
        else:
            # Need to create a default session
            item.session = Session()
            item.session.tags = ""
            item.session.date = timezone.now()
            item.session.hostname = ""
            item.session.platform = platform.system()
            item.session.application = "Nexus"
            item.session.version = "1.0"
            item.session.guid = uuid.uuid4()
        if dataset:
            item.dataset = dataset
        else:
            # Need to create a default dataset
            item.dataset = Dataset()
            item.dataset.tags = ""
            item.dataset.filename = "None"
            item.dataset.dirname = ""
            item.dataset.format = "Internal"
            item.dataset.numparts = 0
            item.dataset.numelements = 0
            item.dataset.guid = uuid.uuid4()
        item.sequence = 0
        item.tags = self.tags
        item.source = 'Generator:tablemerge'
        item.name = name
        item.type = 'table'
        item.date = timezone.now()
        d = dict(array=self.array)
        if self.col_lbls:
            d['collbls'] = self.col_lbls
        if self.row_lbls:
            d['rowlbls'] = self.row_lbls
        if self.row_tags:
            d['row_tags'] = self.row_tags
        if self.col_tags:
            d['col_tags'] = self.col_tags
        # in py3, it pickles using protocol 3 by default,
        # we let this use protocol 3 because these are temporarily generated items and
        # are not saved to the db. Otherwise we have to use protocol 0 due to issues with Django's.save()
        item.payloaddata = pickle.dumps(d)
        return item


class TableMergeGeneratorEngine(GeneratorEngine):
    '''Generator capable of merging multiple table items into a single, ephemeral table item'''

    @classmethod
    def report_type(cls):
        return "Generator:tablemerge"

    def process(self, items, context, **kwargs):
        # get the parameters
        params = self._params.get("merge_params", {})
        merge_type = params.get("merge_type", 'row')  # merging 'row' or 'column'
        source_rows = params.get("source_rows", "'*|duplicate'")  # rowname globs & merge option e.g. 'foo*|duplicate'
        source_rows = split_quoted_string_list(source_rows)
        column_labels_as_ids = params.get("column_labels_as_ids",
                                          1)  # 1=use column labels as columns ids, else use a specific row
        column_id_row = params.get("column_id_row",
                                   '0')  # if not using labels as columns ids, use this row as column ids
        column_merge = params.get("column_merge", 1)  # how to merge columns: 'all', 'intersect' ids, 'select' ids
        selected_column_ids = params.get("selected_column_ids", '')  # Specific column ids to use with 'select'
        selected_column_ids = split_quoted_string_list(selected_column_ids)
        unknown_value = params.get("unknown_value", 'nan')  # the 'fill-in' value
        if params.get("transpose_output", 0):  # 1=transpose the final output
            transpose_output = True
        else:
            transpose_output = False
        force_numeric = params.get("force_numeric", 0)  # 1=force the resulting table to be numeric
        # extract the table objects (numpy array +  row/column ids) we will work on
        input_tables = []
        any_text_tables = False
        any_row_labels = False
        any_col_labels = False
        initial_transpose = (merge_type == 'column')  # we handle the "column" case by transposing the inputs
        first_table = None
        n = 0
        for item in items:
            if item.type != 'table':
                continue
            if first_table is None:
                first_table = item
            # build simple table objects from the data item
            st = SimpleTable()
            st.from_item(item, column_labels_as_ids, column_id_row, initial_transpose, index=n, params=params)
            if not st.is_numeric():
                any_text_tables = True
            if st.row_lbls:
                any_row_labels = True
            if st.col_lbls:
                any_col_labels = True
            input_tables.append(st)
            n += 1
        # is there anything to do???
        if first_table is None:
            return []
        # time to do the actual work
        # start by picking the output rows from each of the source tables
        num_rows = 0
        output_row_lbls = []
        output_row_tags = []
        string_size = 0
        for item in input_tables:
            rows = item.rows()
            row_tags = item.row_tags
            if any_text_tables and not item.is_numeric():
                string_size = max(string_size, item.array.dtype.itemsize)
            source_to_dest_row_map = {}
            for row_idx in range(len(rows)):
                row = rows[row_idx]
                row_tag = row_tags[row_idx]
                # check to see if this row matches any of the row matching rules...
                found = False
                row_merge = 'duplicate'
                for v in source_rows:
                    tmp = v.split("|")
                    if len(tmp) > 1:
                        row_merge = tmp[1]
                    if fnmatch.fnmatch(row, tmp[0]):
                        found = True
                        break
                if not found:
                    continue
                # how to merge rows: 'duplicate', 'merge', 'rename_tag' (deprecated from 2024 R1), 'rename_nametag'
                if row_merge == 'duplicate':  # rows can be duplicated, just add a new row...
                    source_to_dest_row_map[row_idx] = num_rows
                    num_rows += 1
                    output_row_lbls.append(row)
                    output_row_tags.append(row_tag)
                elif row_merge == 'merge':  # merge with other rows with the same name (may or not create a new row)
                    if row not in output_row_lbls:
                        source_to_dest_row_map[row_idx] = num_rows
                        num_rows += 1
                        output_row_lbls.append(row)
                        output_row_tags.append(row_tag)
                    else:
                        source_to_dest_row_map[row_idx] = output_row_lbls.index(row)
                elif row_merge == 'rename_tag':  # new row name is '{tag}'  Just here for backward compatibility < 2024R1
                    source_to_dest_row_map[row_idx] = num_rows
                    num_rows += 1
                    output_row_lbls.append(str(item.row_collision_tag).replace("_ROWNAME_", str(row)))
                    output_row_tags.append(row_tag)
                elif row_merge == 'rename_nametag':  # new row name is '{name} {tag}'
                    source_to_dest_row_map[row_idx] = num_rows
                    num_rows += 1
                    if item.macro_expansion:
                        output_row_lbls.append(str(item.row_collision_tag).replace("_ROWNAME_", str(row)))
                    else:
                        # Needed for backward compatibility with versions prior to 24.1
                        output_row_lbls.append(str(row) + ' ' + str(item.row_collision_tag))
                    output_row_tags.append(row_tag)
            item.row_map = source_to_dest_row_map

        # get a list of the common columns...
        common_columns = None
        if column_merge == 'intersect':
            for item in input_tables:
                cols = item.columns()
                if common_columns is None:
                    common_columns = []
                    for col in cols:
                        if col not in common_columns:  # make sure they are unique
                            common_columns.append(col)
                else:
                    rem_list = []
                    for col in common_columns:
                        if col not in cols:  # if the column in the common list is not in the item list, remove it...
                            rem_list.append(col)
                    for col in rem_list:
                        if col in common_columns:
                            common_columns.remove(col)
        # pick the output columns
        num_columns = 0
        output_column_lbls = []
        output_col_tags = []
        # select/map the columns...
        for item in input_tables:
            cols = item.columns()
            col_tags = item.col_tags
            source_to_dest_col_map = {}
            for col_idx in range(len(cols)):
                col = cols[col_idx]
                col_tag = col_tags[col_idx]
                add_column = False
                # Should the column be merged???
                if column_merge == 'all':  # all columns are included in the output
                    add_column = True
                elif column_merge == 'intersect':  # only take the columns that are in common to all tables
                    if col in common_columns:
                        add_column = True
                elif column_merge == 'select':  # Only select the column if it is in the list
                    if col in selected_column_ids:
                        add_column = True
                if add_column:
                    if col in output_column_lbls:  # is the column already in the output???
                        source_to_dest_col_map[col_idx] = output_column_lbls.index(col)
                    else:
                        source_to_dest_col_map[col_idx] = num_columns
                        num_columns += 1
                        output_column_lbls.append(col)
                        output_col_tags.append(col_tag)
            item.col_map = source_to_dest_col_map

        # init the output table (numeric or string) to a new numpy array (of zeros or empty strings)
        output_row_ids = output_row_lbls
        output_column_ids = output_column_lbls
        if not any_col_labels:
            output_column_lbls = None
        if not any_row_labels:
            output_row_lbls = None
        # Let's build an output table!
        out_table = SimpleTable()
        out_table.resize(num_rows, num_columns, string_size=string_size,
                         row_ids=output_row_ids, col_ids=output_column_ids,
                         row_lbls=output_row_lbls, col_lbls=output_column_lbls,
                         row_tags=output_row_tags, col_tags=output_col_tags,
                         init_value=unknown_value)
        # copy (&merge) the inputs...
        for item in input_tables:
            src_to_dst_row_map = item.row_map
            src_to_dst_col_map = item.col_map
            array = item.array
            row_tags = item.row_tags
            col_tags = item.col_tags
            for row in range(num_rows):
                dst_row = src_to_dst_row_map.get(row, None)
                if dst_row is None:
                    continue
                for col in range(num_columns):
                    dst_col = src_to_dst_col_map.get(col, None)
                    if dst_col is None:
                        continue
                    # TODO: handle "merge" conflicts Average? for now, last table wins...
                    out_table.array[dst_row, dst_col] = array[row, col]

        # transpose the output: we might need to undo the initial transpose or add a final transpose
        if transpose_output != initial_transpose:
            out_table.transpose()
        # convert numpy array to doubles...
        if force_numeric and any_text_tables:
            out_table.make_numeric()

        # build an item from out_table and return it
        name = params.get("table_name", "merged table")
        name = self.context_expansion(str(name), context)
        tmp = out_table.to_item(name, session=first_table.session, dataset=first_table.dataset)
        tmp.tags += " generator_item_count={}".format(len(input_tables))
        return [tmp]


# register it with the core
TemplateEngine.register(TableMergeGeneratorEngine)


class TableReductionGeneratorEngine(GeneratorEngine):
    '''Generator capable of reducing rows/columns in a table into derivative tables'''

    @classmethod
    def report_type(cls):
        return "Generator:tablereduce"

    def process(self, items, context, **kwargs):
        # get the parameters
        params = self._params.get("reduce_params", {})
        reduce_type = params.get("reduce_type", 'row')  # merging 'row' or 'column'
        operations = params.get('operations', [])
        if params.get("transpose_output", 0):  # 1=transpose the final output
            transpose_output = True
        else:
            transpose_output = False
        force_numeric = params.get("force_numeric", 0)  # 1=force the resulting table to be numeric
        initial_transpose = (reduce_type == 'column')  # we handle the "column" case by transposing the inputs

        # Apply the reduction to each of the input tables...
        output_tables = []
        n = 0
        for i in items:
            if i.type != 'table':
                continue
            # make a simplified input table
            src_table = SimpleTable()
            src_table.from_item(i, 1, '', initial_transpose, index=n)
            # Let's build an output table
            dst_table = SimpleTable()
            dst_table.tags = src_table.tags
            # Each pass through an operation generates a collection of output cells
            # start by walking the row selections to generate a map from source rows
            # to output row ids.  For each row id, these are the source rows...
            # Next, walk the columns selection (by unique values or preserve existing).
            # This can generate new columns or re-use old ones.  We produce the list(s) of
            # values at this point and reduce them to one value.
            # As we go, generate the final list of row/column ids and names.
            # After all the operations are done, we can build the final table, filling in values
            # as needed.
            # Output row/col names
            row_names = []
            col_names = []
            col_tags = []
            col_indices = []
            # Output values
            output_values = {}  # output_values[(row, col)] = value
            # do an operation
            for op in operations:
                source_rows = op.get('source_rows', "'*'")
                output_row_name = op.get('output_rows', 'output_row')
                output_rows_from_values = op.get('output_rows_from_values', False)
                output_columns = op.get('output_columns', '')
                output_columns_select = op.get('output_columns_select', '*')
                output_columns_from_values = op.get('output_columns_from_values', False)
                operation = op.get('operation', 'count')
                # grab the indices of the source rows, we will limit our search to them
                source_rows = split_quoted_string_list(source_rows)
                source_row_indices = src_table.find_rows_match(source_rows)
                # Note: the output rows are always "new" row(s) (one or more based on values)
                # find the output rows, two modes
                # 1) rows named using the unique values in a specific column
                # 2) output one row using the name the user specified
                dst_table.row_map = {}  # clear the row map
                if output_rows_from_values:
                    # find the column to get the unique row names from
                    the_column = src_table.find_columns_match([output_row_name])
                    if len(the_column):
                        the_column = the_column[0]  # the column index to look for unique values in..
                        # get the unique values in column indexed by the_column for all selected rows
                        unique = {}
                        out_row = len(row_names)
                        # the row map notes that for a given output row, these source rows will apply...
                        # dst_table.row_map[output_row] = [src_rows]
                        for idx in source_row_indices:
                            v = src_table.array[idx, the_column]
                            if v in unique:
                                # already exists...
                                dst_table.row_map[unique[v]].append(idx)
                            else:
                                dst_table.row_map[out_row] = []
                                dst_table.row_map[out_row].append(idx)
                                unique[v] = out_row
                                row_names.append(v)
                                out_row += 1
                else:
                    # in this case, we output one (new) row, named using the user provided template
                    out_row = len(row_names)
                    dst_table.row_map[out_row] = copy.deepcopy(source_row_indices)
                    row_names.append(self.context_expansion(output_row_name, context, i))

                # ok, we have the named output rows, together with their dst row to src rows map
                # time to walk the columns and generate the values
                # find the output column names, two cases
                # 1) columns names from unique values in a specific column
                # 2) retain a subset of original columns
                if output_columns_from_values:
                    # find the column the user wants to use the unique values from
                    value_to_column_map = {}
                    the_column = src_table.find_columns_match([output_columns])
                    if len(the_column):
                        the_column = the_column[0]
                        # get the unique values from the requested column and add new columns if needed
                        for src_row in source_row_indices:
                            v = src_table.array[src_row, the_column]
                            if v not in col_names:
                                col_names.append(v)
                            value_to_column_map[v] = col_names.index(v)
                        # ok, we can now resolve all of the values in this column for all of the rows in the
                        # row map..
                        for value, dst_col in value_to_column_map.items():
                            for dst_row in dst_table.row_map:
                                values = []
                                for src_row in dst_table.row_map[dst_row]:
                                    v = src_table.array[src_row, the_column]
                                    if value == v:
                                        values.append(v)
                                output_values[(dst_row, dst_col)] = self.reduce_list(values, src_table, operation)
                else:
                    # retain a subset of original columns
                    # search the columns for matches...
                    source_columns = src_table.find_columns_match([output_columns_select])
                    for src_col in source_columns:
                        if src_col in col_indices:  # existing column
                            dst_col = col_indices.index(src_col)
                        else:  # new column
                            dst_col = len(col_indices)
                            col_indices.append(src_col)
                            col_names.append(src_table.columns()[src_col])
                            # if we are retaining a subset of columns, we pick
                            # from existing column tags, or else we just use the
                            # item's tags later
                            col_tags.append(src_table.col_tags[src_col])
                        # ok, we can now resolve all of the values in this column for all of the rows in the
                        # row map..
                        for dst_row in dst_table.row_map:
                            values = []
                            for src_row in dst_table.row_map[dst_row]:
                                v = src_table.array[src_row, src_col]
                                values.append(v)
                            output_values[(dst_row, dst_col)] = self.reduce_list(values, src_table, operation)

            # any data to output?  if not, skip this table...
            if not row_names or not col_names:
                continue

            # build the output table
            num_rows = len(row_names)
            num_cols = len(col_names)
            dst_table.resize(num_rows, num_cols, string_size=src_table.string_size(),
                             row_lbls=row_names, col_lbls=col_names,
                             row_tags=[src_table.tags] * num_rows,
                             col_tags=col_tags or [src_table.tags] * num_cols)
            for rc, v in output_values.items():
                dst_table.array[rc[0], rc[1]] = v

            # transpose the output: we might need to undo the initial transpose or add a final transpose
            if transpose_output != initial_transpose:
                dst_table.transpose()
            # convert numpy array to doubles...
            if force_numeric:
                dst_table.make_numeric()
            # build an item from out_table and return it
            name = params.get("table_name", "reduced table")
            name = self.context_expansion(name, context, item=i)
            tmp = dst_table.to_item(name, session=i.session, dataset=i.dataset)
            output_tables.append(tmp)
            n += 1

        return output_tables

    @staticmethod
    def calc_result(values, op):
        v = numpy.nan
        if op == 'count':
            v = len(values)
        elif len(values) == 1:
            v = values[0]
        elif op == 'min':
            v = numpy.min(values)
        elif op == 'max':
            v = numpy.max(values)
        elif op == 'sum':
            v = numpy.sum(values)
        elif op == 'diff':
            v = values[0]
            for tmp in values[1:]:
                v -= tmp
        elif op == 'mean':
            v = numpy.mean(values)
        elif op == 'stdev':
            v = numpy.std(values)
        elif op == 'skew':
            v = numpy.var(values)
            m = numpy.mean(values)
            v = numpy.sum(((values - m) / v) ** 3) / float(len(values))  # pylint: disable=W1619
        elif op == 'kurtosis':
            v = numpy.var(values)
            m = numpy.mean(values)
            v = (numpy.sum(((values - m) / v) ** 4) / float(len(values))) - 3.  # pylint: disable=W1619
        return v

    def reduce_list(self, values, src_table, operation):
        # compute the resulting value
        if src_table.is_numeric():
            v = self.calc_result(values, operation)
        else:
            tmp = []
            for v in values:
                try:
                    v2 = float(v)
                except:
                    v2 = numpy.nan
                tmp.append(v2)
            v = self.calc_result(tmp, operation)
            v = str(v)
        return v


# register it with the core
TemplateEngine.register(TableReductionGeneratorEngine)


class TableMergeRowColumnFilterGeneratorEngine(GeneratorEngine):
    '''Generator that selects specific rows/columns from a table and returns the result as a new table'''

    @classmethod
    def report_type(cls):
        return "Generator:tablerowcolumnfilter"

    ''' Parameters:
        'table_name' - output table name
        'select_rows' - list of wildcards for the saved rows
        'select_columns' - list of wildcards for the saved columns
        'transpose' - if true, transpose the output after filtering
        'invert' - if true, remove the selected rows/columns
        'reorder' - if true, re-order the rows/columns based on selections
    '''

    def process(self, items, context, **kwargs):
        # get the parameters
        table_name = self._params.get("table_name", 'row/column filtered table')
        transpose = self._params.get("transpose", False)
        invert = self._params.get("invert", False)
        select_rows = self._params.get("select_rows", "'*'")
        select_rows = split_quoted_string_list(select_rows)
        select_columns = self._params.get("select_columns", "'*'")
        select_columns = split_quoted_string_list(select_columns)
        reorder_rc = self._params.get("reorder", False)
        # we will not re-order rows/columns if we are selecting what to remove
        if invert:
            reorder_rc = False
        # the output tables
        output_tables = []
        # Walk all of the items, find the tables and process them
        n = 0
        for i in items:
            if i.type != 'table':
                continue
            # make a simplified input table
            src_table = SimpleTable()
            src_table.from_item(i, 1, '', False, index=n)
            # find the source row/column indices (in order) to keep
            the_rows = src_table.find_rows_match(select_rows)
            the_rows.sort()
            the_columns = src_table.find_columns_match(select_columns)
            the_columns.sort()
            # convert these into rows/columns to be removed
            if invert:
                rem_rows = the_rows
                rem_columns = the_columns
            else:
                rem_rows = [idx for idx in range(len(src_table.rows())) if idx not in the_rows]
                rem_columns = [idx for idx in range(len(src_table.columns())) if idx not in the_columns]
            # Are we removing all of the rows or columns?  if so, skip this table as there is nothing left.
            if (len(rem_rows) == len(src_table.rows())) or (len(rem_columns) == len(src_table.columns())):
                continue
            src_table.remove_rows_columns(rows=rem_rows, columns=rem_columns)
            # ok, we would like to re-order the rows/columns
            if reorder_rc:
                the_rows = src_table.find_rows_match(select_rows)
                the_columns = src_table.find_columns_match(select_columns)
                src_table.reorder(rows=the_rows, columns=the_columns)
            # transpose the output if requested
            if transpose:
                src_table.transpose()
            # build an item from out_table and return it
            name = self.context_expansion(table_name, context, item=i)
            tmp = src_table.to_item(name, session=i.session, dataset=i.dataset)
            output_tables.append(tmp)
            n += 1

        return output_tables


# register it with the core
TemplateEngine.register(TableMergeRowColumnFilterGeneratorEngine)


class TableMergeValueFilterGeneratorEngine(GeneratorEngine):
    '''Generator selects specific rows/columns by applying filter to table values, returns result as new table'''

    @classmethod
    def report_type(cls):
        return "Generator:tablevaluefilter"

    ''' Parameters:
        'table_name' - output table name
        'row_column' - filtering either rows or columns: 'row', 'column'
        'column_name' - column name to filter by the values of
        'filter' - the filtering operation: 'range', 'specific', 'top_percent', 'top_count', 'bot_percent', 'bot_count'
        'values_as_dates' - treat the column values as dates (allow use of dates for filtering???)
        'range_min' - min value, can be empty string for "none"
        'range_max' - max value, can be empty string for "none"
        'specific_values' - list of specific values to allow through
        'count' - number to preserve
        'percent' - % of values to preserve
        'invert' - if true, invert the sense of the validity check (e.g. not between these values for 'range')
    '''

    def process(self, items, context, **kwargs):
        # get the parameters
        table_name = self._params.get("table_name", 'value filtered table')
        row_column = self._params.get("row_column", 'row')  # by default, filter rows by looking at values in a column
        column_name = self._params.get("column_name", "0")
        filter_op = self._params.get("filter", "range")
        values_as_dates = self._params.get("values_as_dates", False)
        invert = self._params.get("invert", False)
        range_min = self._params.get("range_min", "")
        range_max = self._params.get("range_max", "")
        specific_values = self._params.get("specific_values", "'*'")
        specific_values = split_quoted_string_list(specific_values)
        count = self._params.get("count", "10")
        percent = self._params.get("percent", "10.0")
        transpose = row_column == "column"

        # condition some inputs: to floats, convert dates, clamp to limits
        try:
            count = max(int(count), 0)
        except:
            count = 10
        try:
            percent = float(percent) / 100.0
            percent = max(min(percent, 1.), 0.)
        except:
            percent = 0.1
        try:
            if values_as_dates:
                dt = parser.parse(range_min)
                # No timezone, assume server timezone
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt, timezone=timezone.get_current_timezone())
                range_min = (dt - time_base).total_seconds()
            else:
                range_min = float(range_min)
        except:
            range_min = None
        try:
            if values_as_dates:
                dt = parser.parse(range_max)
                # No timezone, assume server timezone
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt, timezone=timezone.get_current_timezone())
                range_max = (dt - time_base).total_seconds()
            else:
                range_max = float(range_max)
        except:
            range_max = None
        # rework the specific_values list if numeric
        specific_numbers = []
        for v in specific_values:
            try:
                tmp = self.value_to_float(v)
            except:
                tmp = numpy.nan
            specific_numbers.append(tmp)

        # if the user specified an inverted range, handle it
        if (range_min is not None) and (range_max is not None):
            if range_min > range_max:
                tmp = range_min
                range_min = range_max
                range_max = tmp

        # the output tables
        output_tables = []
        # Walk all of the items, find the tables and process them
        n = 0
        for i in items:
            if i.type != 'table':
                continue
            # make a simplified input table
            src_table = SimpleTable()
            src_table.from_item(i, 1, '', False, index=n)
            # transpose if requested
            if transpose:
                src_table.transpose()
            # does the column to filer on exist?  if not, skip this one
            the_column = src_table.find_columns_match([column_name])
            if len(the_column) == 0:
                continue
            col_idx = the_column[0]
            # Walk the values in the column and select the ones that are valid
            values = []
            num_values = len(src_table.rows())
            # first grab all of the values in the column
            for row_idx in range(num_values):
                values.append(src_table.array[row_idx, col_idx])
            # are all of the values numeric?
            all_numeric = True
            tmp_values = []
            for v in values:
                try:
                    dummy = self.value_to_float(v)
                    tmp_values.append(dummy)
                except:
                    all_numeric = False
                    break
            if all_numeric:
                values = tmp_values
            # we need to preserve the index mapping for each value.  so, pad out the array, sort it and extract
            # the preserved index order...
            tmp = []
            for row_idx in range(len(values)):
                tmp.append([values[row_idx], row_idx])
            tmp.sort()
            values_sort = []
            index_sort = []
            for v in tmp:
                values_sort.append(v[0])
                index_sort.append(v[1])
            # we have a sorted list of values and their associated row indices...
            # now, make a list of the rows that are to be filtered out...
            rem_rows = []
            for row_idx in range(num_values):
                v = src_table.array[row_idx, col_idx]
                tmp = (specific_values, False)
                if all_numeric:
                    tmp = (specific_numbers, True)
                    v = self.value_to_float(v)
                if not self.value_valid(v, row_idx, values_sort, index_sort, filter_op,
                                        range_min, range_max, count, percent, tmp, invert):
                    rem_rows.append(row_idx)
            # remove them
            src_table.remove_rows_columns(rows=rem_rows)
            # undo the transpose
            if transpose:
                src_table.transpose()
            # build an item from out_table and return it
            name = self.context_expansion(table_name, context, item=i)
            tmp = src_table.to_item(name, session=i.session, dataset=i.dataset)
            output_tables.append(tmp)
            n += 1

        return output_tables

    @staticmethod
    def value_to_float(v):
        try:
            tmp = float(v)
        except:
            dt = parser.parse(v)
            # No timezone, assume server timezone
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt, timezone=timezone.get_current_timezone())
            tmp = (dt - time_base).total_seconds()
        return tmp

    @staticmethod
    def value_valid(v, idx, values, indices, filter_op, range_min, range_max, count, percent, specific, invert):
        ok = True
        if isinstance(v, bytes):
            v = v.decode("utf-8")
        if filter_op == 'range':
            if range_min is not None:
                if v < range_min:
                    ok = False
            if range_max is not None:
                if v > range_max:
                    ok = False
        elif filter_op == 'specific':
            if specific[1]:  # Numeric case
                if v not in specific[0]:
                    ok = False
            else:  # String case
                found = False
                for pattern in specific[0]:
                    if fnmatch.fnmatch(v, pattern):
                        found = True
                        break
                if not found:
                    ok = False
        else:
            top = filter_op.startswith("top")
            num = filter_op.endswith("count")
            try:
                idx = indices.index(idx)
                if top:  # if looking for the top, invert the position
                    idx = (len(indices) - 1) - idx
                if num:
                    if idx >= count:
                        ok = False
                else:
                    if idx >= len(indices) * percent:
                        ok = False
            except:
                ok = False
        if invert:
            ok = not ok
        return ok


# register it with the core
TemplateEngine.register(TableMergeValueFilterGeneratorEngine)


class TableSortFilterGeneratorEngine(GeneratorEngine):
    '''Generator that sorts rows/columns from a table by values in columns/rows or their associated labels'''

    @classmethod
    def report_type(cls):
        return "Generator:tablesortfilter"

    ''' Parameters:
        'table_name' - output table name
        'sort_rows' - list of columns to use to sort rows
        'sort_columns' - list of rows to use to sort columns
    '''

    def process(self, items, context, **kwargs):
        # get the parameters
        table_name = self._params.get("table_name", 'sorted table')
        sort_rows = self._params.get("sort_rows", [])
        sort_columns = self._params.get("sort_columns", [])

        # the output tables
        output_tables = []
        # Walk all of the items, find the tables and process them
        n = 0
        for i in items:
            if i.type != 'table':
                continue
            # make a simplified input table
            src_table = SimpleTable()
            src_table.from_item(i, 1, '', False, index=n)
            # sort the rows
            if len(sort_rows):
                src_table.sort_rows(sort_rows)
            # we can only sort rows, so if we are asked to sort columns, transpose and revert
            if len(sort_columns):
                src_table.transpose()
                src_table.sort_rows(sort_columns)
                src_table.transpose()
            # build an item from out_table and return it
            name = self.context_expansion(table_name, context, item=i)
            tmp = src_table.to_item(name, session=i.session, dataset=i.dataset)
            output_tables.append(tmp)
            n += 1

        return output_tables


# register it with the core
TemplateEngine.register(TableSortFilterGeneratorEngine)


class TreeMergeGeneratorEngine(GeneratorEngine):
    """
    Generator that merges a collection of trees into a single tree item.

    Operations:
    1) Include all rows, use fill value for undefined cells
    2) Include common rows (if the row does not exist in all items, it is dropped)
    3) Rows defined by first item
    """

    @classmethod
    def report_type(cls):
        return "Generator:treemerge"

    ''' Parameters:
        'rows' - 'all', 'common', 'first'
        'fillvalue' - value to fill in empty cells with
        'headertag' - if a non-empty string, add a header row with tag value
        'mergedname' - name for the merged tree item
        'matchby' - 'key', 'name', 'both'  row match using the row name the row key or both values
    '''

    def process(self, items, context, **kwargs):
        # get the parameters
        rows = self._params.get("rows", "all")
        fill = self._params.get("fillvalue", "")
        header_tag = self._params.get("headertag", '')
        merged_name = self._params.get("mergedname", "treemerge")
        match_by = self._params.get("matchby", "both")
        output_item = None
        working_tree = None
        for item in items:
            if item.type != 'tree':
                continue
            # evaluate the header value (via tag) for this item
            header_value = None
            if header_tag:
                header_value = item.search_tag(header_tag)
            # if we have found the first tree item, create the output items
            if output_item is None:
                from ..data.models import Item
                output_item = Item()
                output_item.guid = uuid.uuid4()
                # We will use the session/dataset for the initial tree item
                output_item.session = item.session
                output_item.dataset = item.dataset
                output_item.sequence = 0
                output_item.tags = item.tags
                output_item.source = self.report_type()
                output_item.name = self.context_expansion(merged_name, context, item=item)
                output_item.type = 'tree'
                output_item.date = timezone.now()
                # start with a copy of the first tree in table form
                working_tree = SimpleTree(safe_unpickle(item.payloaddata), match_by=match_by,
                                          fill=fill, rules=rows, header=header_value)
            else:
                # merge in the next tree
                temp_simple_tree = SimpleTree(safe_unpickle(item.payloaddata), match_by=match_by,
                                              fill=fill, rules=rows, header=header_value)
                working_tree.merge_payload(temp_simple_tree)
        # we might have output
        if output_item is not None:
            # convert the merged table into tree form
            output_item.payloaddata = pickle.dumps(working_tree.to_payload_list())
            return [output_item]
        return []


# register it with the core
TemplateEngine.register(TreeMergeGeneratorEngine)


class SQLQueryGeneratorEngine(GeneratorEngine):
    '''Generator that runs a SQL Query manually entered by the user'''

    @classmethod
    def report_type(cls):
        return "Generator:sqlqueries"

    ''' Parameters:
        'typedb'   - type of database - 'SQLite' or 'PostgreSQL'
        'sqlquery' - query to run
        'sqldb'    - sql database to connect to
        'hostsqldb'- PostgreSQL database hostname
        'portsqldb'- PostgreSQL database port
        'usrsqldb' - user name for PostgreSQL database
        'pswsqldb' - password for PostgreSQL database
    '''

    def create_error_table(self, typedb, error_str):
        """Creation error message

        Method that takes the error string (from an exception most likely) and 
        turns it into a one row/column data table so it can be displayed in the
        report instead of an empty table. Not really ideal, but better than an
        empty table for the user receiving the error

        Parameters
        ----------
        typedb    : str
            The type of database (SQLite / PostgreSQL)
        error_str : str
            The error string to display

        Returns
        -------
        list
            table to display

        """
        msg = error_str.encode("utf-8")
        out_table = SimpleTable()
        out_table.resize(rows=1, cols=1, string_size=len(msg))
        out_table.col_lbls = ["Error message"]
        # '|S' is type 'numpy.bytes_' or a byte string. Use '|U' for unicode strings(str in py3)
        utf8_array = []
        utf8_row = []
        utf8_row.append(msg)
        utf8_array.append(utf8_row)
        out_table.array = numpy.array(utf8_array).astype('|S' + str(len(msg) + 1))
        tmp = out_table.to_item(name=typedb + " Query")
        return [tmp]

    def process(self, items, context, **kwargs):
        # get the parameters
        typedb = self._params.get("typedb", "SQLite")
        sqlquery = self._params.get("sqlquery", "")
        sqldb = self._params.get("sqldb", "")
        # hostsqldb = self._params.get("hostsqldb", "")
        # portsqldb = self._params.get("portsqldb", "")
        # usrsqldb = self._params.get("usrsqldb", "")
        # pswsqldb = self._params.get("pswsqldb", "")
        # print("Input: {} {} {} {} {} {} {} ".format(typedb, sqlquery, sqldb, hostsqldb, portsqldb, usrsqldb, pswsqldb))
        if 'SQLite' == typedb:
            try:
                import sqlite3
            except Exception as e:
                return []
            db = sqlite3.connect(sqldb)
        elif 'PostgreSQL' == typedb:
            attrs = dict(sqldb='dbname', hostsqldb='host', portsqldb='port', usrsqldb='user', pswsqldb='password')
            conn_string = ""
            for key in attrs:
                tmp = str(self._params.get(key, ""))
                if len(tmp):
                    conn_string += "{}={} ".format(attrs[key], tmp)
            try:
                import psycopg
                db = psycopg.connect(conn_string.strip())
            except Exception as e:
                return self.create_error_table(typedb, "The database connection could not be validated.")
        else:
            return []
        cursor = db.cursor()
        # If you're passing aware datetime parameters to 'cursor' queries,
        # you should turn them into naive datetimes in UTC
        # Ref: docs.djangoproject.com/en/2.2/releases/1.9
        # /#removal-of-time-zone-aware-global-adapters-and-converters-for-datetimes
        try:
            cursor.execute(sqlquery)
            tmp_array = cursor.fetchall()
        except Exception as e:
            return self.create_error_table(typedb, str(e))
        cursor.close()
        db.close()
        mycol = [desc[0] for desc in cursor.description]
        utf8_array = []
        for row in tmp_array:
            utf8_row = []
            for value in row:
                try:
                    if isinstance(value, str):
                        utf8_row.append(value.encode("utf-8"))
                    elif isinstance(value, datetime.datetime):
                        utf8_row.append(value.isoformat().encode("utf-8"))
                    else:
                        utf8_row.append(str(value).encode("utf-8"))
                except Exception as e:
                    utf8_row.append("Invalid conversion: {}".format(str(e)).encode("utf-8"))
            utf8_array.append(utf8_row)
        max_size = -1
        for i in range(len(utf8_array)):
            max_size = max(max_size, len(max(utf8_array[i], key=len)))
        # Let's build an output table!
        out_table = SimpleTable()
        out_table.resize(rows=len(utf8_array), cols=len(mycol), string_size=max_size, col_lbls=mycol)
        # '|S' is type 'numpy.bytes_' or a byte string. Use '|U' for unicode strings(str in py3)
        out_table.array = numpy.array(utf8_array).astype('|S' + str(max_size))
        tmp = out_table.to_item(name=typedb + " Query")
        return [tmp]


# register it with the core
TemplateEngine.register(SQLQueryGeneratorEngine)
