import copy
import numpy
import math
import fnmatch
import warnings


class QuotedSplit:
    """
        This class will split a string at a specific character, provided it is not in a quoted string

        The class is meant to serve as an indirect interface to this functionality that is
        not fully provided by str.split or shlex.

        The current implementation is regular expression based and caches compiled expressions.
        The expression basically breaks down to: break up the input at the separator, but
        treat quoted blocks as opaque blocks of text.  The return value will include the
        separator and will have leading/trailing empty strings, hence the use of [1::2].

    """
    compiled = dict()

    @classmethod
    def split(cls, string, sep=','):
        import re
        if sep not in cls.compiled:
            cls.compiled[sep] = re.compile(r'''((?:[^''' + sep + r'''"']|"[^"]*"|'[^']*')+)''')
        return cls.compiled[sep].split(string)[1::2]


class ConditionalFormatting:
    """
        Compute conditional formatting HTML style specifications for a table

        This class computes a table of styling dictionaries by applying a set of
        rules to the values in an input numpy array.  The output is a numpy array
        of Python objects.  The objects can be None or dict instances.  The
        dictionary keys include:

            'forecolor' - [red, green, blue] list of floats, [0., 1.]
            'backcolor' - [red, green, blue] list of floats, [0., 1.]
            'bold' - True if bold() was called

        Formatting consists of a set of rules.  Each rule contains a 'scope'
        that selects some rows or columns as a target for the 'stanza's of the
        rule.  Each rule may contain multiple stanzas which are composed of a
        comparison expression and a format expression.  If the comparison expression
        evaluates as True, the format expression will generate the style dictionary.
        These stanzas are applied for every value in the row/column selected
        by the scope function.  Note, once a stanza comparison expression
        returns True, no additional stanzas will be evaluated for that value.

        Rules are specified as a UTF8 string in the general format:

        {scope}:{comparison}|{format};{comparison}|{format};&{scope}:...

        Each section is evaluated in a constrained Python environment.  Each section has
        a limited number of functions that are legal in that section.  These include:

         scope:
            This expression must evaluate either the row() or col() functions.

            row(name) - format the row(s) that match the name, using fnmatch if name is a string.
                 If name is an integer, it is the index of the row to target.
            col(name) - format the column(s) that match the name, using fnmatch if name is a string
                 If name is an integer, it is the index of the column to target.

            If the name is a string, the use of "glob" wildcards is allowed.  If a glob string matches
            multiple rows/columns, all of those rows/columns will be processed.

         comparison:
            A Python expression that must evaluate to True or False if it evaluates as True, the
            "format" expresion will be evaluated.  If False, it is not.  An empty comparison expression
            evaluates as True.

            The following variables and functions are allowed in the expressions:
                Direct cell value access:
                    value - the value currently being processed as a float
                    svalue - the value currently being processed as a string
                    neighbor(name), before(), after() - the "neighboring" value in the table.  neighbor() allows
                            for the explict specification of the other row/column, before() and after()
                            select the row/column before or after in the table.  Note that if the table/tree are
                            string-based, the value returned by neighbor(), before() an after() will be strings.

                Mathematical reduction operations on rows/columns:
                    min({rc}{,use_row=True|False}) - the minimum value of a specific row/column
                    max({rc}{,use_row=True|False})- the maximum value of a specific row/column
                    avg({rc}{,use_row=True|False}) - the average of a specific row/column
                    var({rc}{,use_row=True|False}) - the variance of a specific row/column
                    std({rc}{,use_row=True|False}) - the standard deviation of a specific row/column
                    count({rc}{,use_row=True|False}) - the number of values in a specific row/column

                    The {rc} parameter is optional.  If present, it specifies a row/column name using the
                    same expressions available to the row() and col() "scope" section functions (e.g.
                    strings with glob wildcards or 0-based index numbers).  If no {rc} parameter is passed,
                    the same row/column selected in the "scope" section will be used.

                    By default, these functions will be applied to rows if the "scope" function is row() and
                    columns if the "scope" function is col().  The use_row= keyword allows the caller to
                    specify that the function be applied specifically to a row or column respectively, overriding
                    the default set by the "scope" function.  For example:  row(2):value>min(use_row=False)|... would
                    apply the formatting to the cells of row 2, but in the comparison function, compute the minimum
                    of the column of the cell instead of the (default) row of the cell.

                    The min, max, avg, var, std and count function ignore NaN values.  All but count may return NaN.

                Other functions:
                    clamp(value, lower, upper) - return value clamped to the range [lower, upper]
                    Functions from the math and str modules are allowed.

         format:
            A Python expression that must evaluate to the sum of the pal(), rgb() and/or bold()
            functions.  Each of those functions will add a key to the dictionary for the table
            cell being evaluated.

            All of the values and functions from the comparison section are allowed, but it must
            evaluate to the return value of one or the sum of the return value of these additional
            functions.

            pal(name, min, max, num_levels=None, forecolor=False) - sample the palette selected by 'name'.
                  Scale the endpoints of the palette to the min and max expressions and then interpolate the
                  cell value into the palette to generate the color.  If n_levels is specified as an integer,
                  the palette will be quantized to that number of colors before interpolation is performed.
                  The function sets the 'backcolor' or 'forecolor' keys of the formatting dictionary,
                  based on the value of the forecolor keyword, to the interpolated color.
            rgb(r, g, b, forecolor=False) - This function sets the 'backcolor' or 'forecolor' keys of the formatting
                  dictionary, based on the value of the forecolor keyword, to the specified color. r,g,b are
                  in the range [0., 1.].
            contrast() - This function sets 'forecolor' to [0, 0, 0] or [1, 1, 1] based on what best
                  contrasts the 'backcolor'.  This should be the last function in the format expression.
            bold() - This function sets the 'bold' key of the formatting dictionary to True.
            openparent() - This function sets the 'openparent' key of the formatting dictionary to 'parent'.
            openparents() - This function sets the 'openparent' key of the formatting dictionary to 'tree'.

         Example formatting string with one rule applied to columns with names ending in "Temperature":
              col(“* Temperature”):value != -1|bold()+pal(‘warm’, min(), max(), num_levels=7)&

         If the nexus_palettes_only keyword is True, the available palettes will match those
         documented as available in Nexus.  If False, a more complete list of plotly palettes
         are available.
    """
    def __init__(self, nexus_palettes_only=False):
        self._rows = list()
        self._cols = list()
        self._table = None
        self._rules = ""
        self._output = None
        self._tgt_is_row = False
        self._tgt_row = None
        self._tgt_col = None
        self._tgt_rows = list()
        self._tgt_cols = list()
        self._nexus_palettes_only = nexus_palettes_only
        self._palettes = dict()
        self._init_palettes()
        self._split = QuotedSplit()

    @property
    def palettes(self):
        """ get the palette dict """
        return self._palettes

    def validate_indices(self, indices, rows=True):
        """ Ensure that the row/col indices are valid for the current target """
        max_idx = self._table.shape[1]
        if rows:
            max_idx = self._table.shape[0]
        indices = [idx for idx in indices if (idx >=0) and (idx < max_idx)]
        return indices

    def find_col_indices(self, col):
        """ Given a column selection string or integer, return the list of column indices it matches """
        indices = list()
        if issubclass(type(col), int):
            indices.append(col)
            return self.validate_indices(indices, rows=False)
        if not issubclass(type(col), str):
            col = str(col)
        for i in range(len(self._cols)):
            if fnmatch.fnmatch(str(self._cols[i]), col):
                indices.append(i)
        return self.validate_indices(indices, rows=False)

    def find_row_indices(self, row):
        """ Given a row selection string or integer, return the list of row indices it matches """
        indices = list()
        if issubclass(type(row), int):
            indices.append(row)
            return self.validate_indices(indices, rows=True)
        if not issubclass(type(row), str):
            row = str(row)
        for i in range(len(self._rows)):
            if fnmatch.fnmatch(str(self._rows[i]), row):
                indices.append(i)
        return self.validate_indices(indices, rows=True)

    def palette_names(self):
        """ get the valid palette names """
        return list(self._palettes.keys())

    def find_palette(self, name):
        """ Return the list representation of a palette (handle '_r' for reversal)

        Palette names are case insensitive and we support two forms of palette reversal:
           (1) prefix with '-' - this is Nexus style reversal
           (2) suffix with '_r' - this is the internal plotly.js style
        """
        name = name.lower()
        reverse = False
        if name.endswith("_r"):
            name = name[:-2]
            reverse = True
        if name.startswith("-"):
            name = name[1:]
            reverse = True
        if name in self._palettes:
            palette = copy.deepcopy(self._palettes[name])
        else:
            return None
        if reverse:
            # first reverse the order of the colors (the interpolation code requires values to be
            # monotonically increasing).
            palette.reverse()
            # invert the normalized value
            for i in range(len(palette)):
                palette[i][0] = 1. - palette[i][0]
        return palette

    def interp_palette(self, pal, min_value, max_value, num_levels=None):
        """ Interpolate the current cell value into the named palette

        Convert the value of the current cell into normalized space using the min_value and
        max_value arguments.  If steps is specified, the palette will be quantized (in normalized
        data space) to that number of levels before the final color is interpolated from the
        palette.
        """
        try:
            v = float(self._table[self._tgt_row, self._tgt_col])
        except ValueError:
            return None
        # we have a requirement that the min be less than the max
        if max_value < min_value:
            min_value, max_value = max_value, min_value
        if (max_value - min_value) == 0.:
            min_value = max_value - 1.
        # normalize
        v = v - min_value
        v = v / (max_value - min_value)
        # quantize
        if num_levels is not None:
            # In concept, we take 'steps' samples (0.0 and 1.0 are at the min/max points)
            # The far right and far left are "half width" the others are full width
            # For the three step case, 0.0, 0.5, and 1.0 are the bucket centers
            half_width = 1./((num_levels-1)*2.)
            bucket = 0
            while (v > half_width) and (bucket < num_levels-1):
                bucket += 1
                v -= 2.0*half_width
            v = bucket*2.0*half_width
        v = min(1., max(v, 0.))
        return self.interpolate_palette_norm(pal, v)

    @classmethod
    def interpolate_palette_norm(cls, pal, v, undefined=None):
        """ Interpolate a single value in a color palette

        Given a normalized location in a color palette [0., 1.], interpolate the
        RGB color at that value.  The output is a list of 3 floats in the range [0., 1.]
        representing the red, green and blue components of the color.  This method can
        return None if the normalized location is undefined by the color palette
        """
        for i in range(len(pal) - 1):
            if (v >= pal[i][0]) and (v <= pal[i + 1][0]):
                t = (v - pal[i][0]) / (pal[i + 1][0] - pal[i][0])
                color = list()
                color.append((1. - t) * pal[i][1] / 255. + t * pal[i + 1][1] / 255.)
                color.append((1. - t) * pal[i][2] / 255. + t * pal[i + 1][2] / 255.)
                color.append((1. - t) * pal[i][3] / 255. + t * pal[i + 1][3] / 255.)
                return color
        return undefined

    @classmethod
    def _clamp(cls, v, lower, upper):
        v = min(upper, max(lower, v))
        return v

    # handle the format string evaluation
    def _format_rgb(self, r, g, b, forecolor=False):
        r = self._clamp(r, 0., 1.)
        g = self._clamp(g, 0., 1.)
        b = self._clamp(b, 0., 1.)
        if forecolor:
            self._new_format['forecolor'] = [r, g, b]
        else:
            self._new_format['backcolor'] = [r, g, b]
        return True

    def _format_pal(self, name, min_value, max_value, num_levels=None, forecolor=False):
        palette = self.find_palette(name)
        if palette is not None:
            color = self.interp_palette(palette, min_value, max_value, num_levels)
            if color is not None:
                if forecolor:
                    self._new_format['forecolor'] = color
                else:
                    self._new_format['backcolor'] = color
        return True

    def _format_contrast(self):
        if 'backcolor' not in self._new_format:
            return True
        color = self._new_format['backcolor']
        gray = (color[0] * 0.30) + (color[1] * 0.59) + (color[2] * 0.11)
        if gray >= 0.5:
            self._new_format['forecolor'] = [0., 0., 0.]
        else:
            self._new_format['forecolor'] = [1., 1., 1.]
        return True

    def _format_bold(self):
        self._new_format['bold'] = True
        return True

    def _format_openparent(self):
        self._new_format['openparent'] = 'parent'
        return True

    def _format_openparents(self):
        self._new_format['openparent'] = 'tree'
        return True

    def find_data_vector(self, rc, force_numeric=True, force_dtype='d', use_row=None):
        """ For a given row/column specification, return the table vector

        The various min/max/avg/var functions allow the caller to specify the
        name for the desired row/column to compute for.  This function extracts
        the target row or column of data based on that name.
        """
        if use_row is None:
            is_row = self._tgt_is_row
        else:
            if use_row:
                is_row = True
            else:
                is_row = False
        if is_row:
            the_row = self._tgt_row
            if rc is not None:
                rows = self.find_row_indices(rc)
                if len(rows):
                    the_row = rows[0]
            data = self._table[the_row, :]
        else:
            the_col = self._tgt_col
            if rc is not None:
                cols = self.find_col_indices(rc)
                if len(cols):
                    the_col = cols[0]
            data = self._table[:, the_col]
        # if we want to maintain the array type
        if not force_numeric:
            return data
        # If the data type is numeric, we can just return it
        if numpy.issubdtype(data.dtype, numpy.number):
            return data
        # We have been asked to convert the data to numeric
        number_data = numpy.ndarray(data.shape, dtype=force_dtype)
        # Unfortunately, there is no good numpy mechanism for this so
        # we will convert the input element by element into Python
        # float values (and then the requested numpy dtype) using NaN
        # values when the conversion fails.
        for index, value in numpy.ndenumerate(data):
            try:
                if self._table.dtype.char == 'S':
                    value = value.decode("utf-8")
                float_value = float(value)
            except ValueError:
                float_value = numpy.nan
            number_data[index] = float_value
        return number_data

    def _comp_numpy_func(self, numpy_function, rc, use_row):
        data = self.find_data_vector(rc, use_row=use_row)
        # Under various conditions, the numpy methods will generate Python warnings.
        # we suppress them here, following Matlab semantics.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return numpy_function(data)

    # Note: these functions could potentially cache their results
    # if per-cell evaluation is demonstrated to be a performance
    # bottleneck.
    def _comp_min(self, rc=None, use_row=None):
        return self._comp_numpy_func(numpy.nanmin, rc, use_row)

    def _comp_max(self, rc=None, use_row=None):
        return self._comp_numpy_func(numpy.nanmax, rc, use_row)

    def _comp_avg(self, rc=None, use_row=None):
        return self._comp_numpy_func(numpy.nanmean, rc, use_row)

    def _comp_var(self, rc=None, use_row=None):
        return self._comp_numpy_func(numpy.nanvar, rc, use_row)

    def _comp_std(self, rc=None, use_row=None):
        return self._comp_numpy_func(numpy.nanstd, rc, use_row)

    def _comp_count(self, rc=None, use_row=None):
        data = self.find_data_vector(rc, use_row=use_row)
        return numpy.count_nonzero(~numpy.isnan(data))

    def _comp_neighbor(self, rc):
        v = None
        if self._tgt_is_row:
            rows = self.find_row_indices(rc)
            if len(rows):
                v =  self._table[rows[0], self._tgt_col]
        else:
            cols = self.find_col_indices(rc)
            if len(cols):
                v = self._table[self._tgt_row, cols[0]]
        if v is None:
            raise ValueError("invalid table neighbor")
        if self._table.dtype.char == 'S':
            return v.decode("utf8")
        return v

    def _comp_after(self):
        if self._tgt_is_row:
            v = self._table[self._tgt_row + 1, self._tgt_col]
        else:
            v = self._table[self._tgt_row, self._tgt_col + 1]
        if self._table.dtype.char == 'S':
            return v.decode("utf8")
        return v

    def _comp_before(self):
        if self._tgt_is_row:
            v = self._table[self._tgt_row - 1, self._tgt_col]
        else:
            v = self._table[self._tgt_row, self._tgt_col - 1]
        if self._table.dtype.char == 'S':
            return v.decode("utf8")
        return v

    @staticmethod
    def soft_float(s):
        blocks = s.strip().split(' ')
        if len(blocks) > 0:
            value_string = blocks[0]
            while len(value_string):
                try:
                    return float(value_string)
                except ValueError:
                    value_string = value_string[:-1]
        return math.nan

    def _eval_comparison(self, compare, format_functions=False):
        # set up available functions/variables
        allowed = dict(float=float, int=int)
        # add 'math' module functions and variables
        for k, v in math.__dict__.items():
            if k.startswith("__"):
                continue
            allowed[k] = v
        # add 'str' module functions (with some restrictions)
        bad_str_functions = ['translate', 'maketrans', 'zfill', 'format', 'format_map', 'encode']
        for k, v in str.__dict__.items():
            if k.startswith("__"):
                continue
            if k in bad_str_functions:
                continue
            allowed[k] = v
        # local variables and functions
        try:
            if self._table.dtype.char == 'S':
                allowed['value'] = self.soft_float(self._table[self._tgt_row, self._tgt_col].decode("utf-8"))
            else:
                allowed['value'] = float(self._table[self._tgt_row, self._tgt_col])
        except ValueError:
            allowed['value'] = math.nan
        if self._table.dtype.char == 'S':
            allowed['svalue'] = self._table[self._tgt_row, self._tgt_col].decode("utf-8")
        else:
            allowed['svalue'] = str(self._table[self._tgt_row, self._tgt_col])
        allowed['min'] = self._comp_min
        allowed['max'] = self._comp_max
        allowed['avg'] = self._comp_avg
        allowed['var'] = self._comp_var
        allowed['std'] = self._comp_std
        allowed['count'] = self._comp_count
        allowed['neighbor'] = self._comp_neighbor
        allowed['before'] = self._comp_before
        allowed['after'] = self._comp_after
        allowed['clamp'] = self._clamp
        # if formatting, add rgb() and pal()
        if format_functions:
            allowed['rgb'] = self._format_rgb
            allowed['pal'] = self._format_pal
            allowed['bold'] = self._format_bold
            allowed['contrast'] = self._format_contrast
            allowed['openparent'] = self._format_openparent
            allowed['openparents'] = self._format_openparents
        # compile the string
        code = compile(compare, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed:
                raise ValueError("function not allowed")
        # evaluate the string
        return eval(code, {"__builtins__": {}}, allowed)

    # Handle the "scope" portion of the execution string
    def _scope_row(self, row):
        self._tgt_is_row = True
        self._tgt_rows = self.find_row_indices(row)
        return len(self._tgt_rows) > 0

    def _scope_col(self, col):
        self._tgt_is_row = False
        self._tgt_cols = self.find_col_indices(col)
        return len(self._tgt_cols) > 0

    def _eval_scope(self, scope):
        # set up available functions/variables
        allowed = dict()
        allowed['row'] = self._scope_row
        allowed['col'] = self._scope_col
        # initial conditions
        self._tgt_is_row = None
        # compile the string
        code = compile(scope, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed:
                raise ValueError("function not allowed")
        # evaluate the string
        return eval(code, {"__builtins__": {}}, allowed)

    def _handle_stanza(self, stanza):
        """ A stanza has a comparison function and (if true) a format function

        Test the comparison expression.  If it evaluates True, evaluate the formatting
        expression and fill out the style array cell.  If the format function has been
        evaluated, this function returns True.  An empty comparison expression
        evaluates as True.
        Note: if the target cell has previously been filled with any value, this
        method will return False.
        """
        stanza_blocks = self._split.split(stanza, sep='|')
        if len(stanza_blocks) != 2:
            return False
        # do not replace anything previously set
        if self._output[self._tgt_row, self._tgt_col] is not None:
            return False
        # evaluate the comparison function (empty string == True)
        if stanza_blocks[0] == '':
            result = True
        else:
            result = self._eval_comparison(stanza_blocks[0])
        if result:
            # evaluate the formatting scheme
            self._new_format = dict()
            # this is for the formatting block, not the comparison block
            count = self._eval_comparison(stanza_blocks[1], format_functions=True)
            # map the formatting dictionary to table styling
            if count:
                # set the dictionary as the cell table output
                self._output[self._tgt_row, self._tgt_col] = self._new_format
        return result

    def _handle_rule(self, rule, debug):
        """ Parse and evaluate an individual rule

        A rule starts with the scope specification.
        It is followed by (comparison, format) tuples called stanzas
        """
        rule_blocks = self._split.split(rule, sep=':')
        if len(rule_blocks) != 2:
            return
        # Set up the target if any
        self._tgt_is_row = None
        # the current item being worked on
        self._tgt_row = None
        self._tgt_col = None
        # the scope row/column lists
        self._tgt_rows = list()
        self._tgt_cols = list()
        # if the scope returns true, we have a list of rows/cols to walk
        try:
            if not self._eval_scope(rule_blocks[0]):
                return
        except Exception as e:
            if debug:
                print("Scope evaluation error: {}".format(str(e)))
            return
        # walk the target rows/columns:   a[row,col]  nrows = a.shape[0]
        if self._tgt_is_row:
            for row in self._tgt_rows:
                self._tgt_row = row
                for col in range(self._table.shape[1]):
                    self._tgt_col = col
                    # if we have a target, walk the stanzas
                    for stanza in self._split.split(rule_blocks[1], sep=';'):
                        try:
                            # if a stanza completes, we are done with this cell
                            if self._handle_stanza(stanza):
                                break
                        except Exception as e:
                            # if a stanza throws, we need to keep going
                            if debug:
                                print("Error: {}".format(str(e)))
                                # record the error for help in debugging
                                if self._output[self._tgt_row, self._tgt_col] is None:
                                    self._output[self._tgt_row, self._tgt_col] = dict()
                                self._output[self._tgt_row, self._tgt_col]['error'] = str(e)
        else:
            for col in self._tgt_cols:
                self._tgt_col = col
                for row in range(self._table.shape[0]):
                    self._tgt_row = row
                    # if we have a target, walk the stanzas
                    for stanza in self._split.split(rule_blocks[1], sep=';'):
                        try:
                            # if a stanza completes, we are done with this cell
                            if self._handle_stanza(stanza):
                                break
                        except Exception as e:
                            # if a stanza throws, we need to keep going
                            if debug:
                                print("Error: {}".format(str(e)))
                                # record the error for help in debugging
                                if self._output[self._tgt_row, self._tgt_col] is None:
                                    self._output[self._tgt_row, self._tgt_col] = dict()
                                self._output[self._tgt_row, self._tgt_col]['error'] = str(e)

    def compute_style_array(self, table, rule_string, row_names=None, col_names=None, debug=False):
        """ Compute a numpy array of the per-cell styling

        This method will walk a NumPy array and apply the formatting rule_string to
        every cell.  The return value will be an identically shaped numpy array of
        Python objects.  If the object in the cell is a dictionary, it will be the
        selected formatting for the cell.  This method breaks up the input
        string into rules and passes them to handle_rule()
        """
        self._rows = row_names
        self._cols = col_names
        self._table = table
        self._rules = rule_string
        self._output = numpy.ndarray(self._table.shape, dtype="object")
        self._tgt_is_row = None
        self._tgt_row = None
        self._tgt_col = None
        self._tgt_rows = None
        self._tgt_cols = None
        if self._rows is None:
            self._rows = range(self._table.shape[0])
        if self._cols is None:
            self._cols = range(self._table.shape[1])
        # Walk the rules
        for rule in self._split.split(self._rules, sep='&'):
            self._handle_rule(rule, debug)
        return self._output

    def _init_palettes(self):
        """ Palettes extracted from plotly.js, MIT licensed

        Each palette is a list of [value, red, green, blue] where value is a normalized float from [0., 1.]
        and red, green, blue are integers in the range [0, 255]
        """
        # These are the palettes documented for Nexus already
        self._palettes['greys'] = [[0, 0, 0, 0], [1, 255, 255, 255]]
        self._palettes['ylgnbu'] = [[0, 8, 29, 88], [0.125, 37, 52, 148], [0.25, 34, 94, 168], [0.375, 29, 145, 192],
                                    [0.5, 65, 182, 196], [0.625, 127, 205, 187], [0.75, 199, 233, 180],
                                    [0.875, 237, 248, 217], [1, 255, 255, 217]]
        self._palettes['greens'] = [[0, 0, 68, 27], [0.125, 0, 109, 44], [0.25, 35, 139, 69], [0.375, 65, 171, 93],
                                    [0.5, 116, 196, 118], [0.625, 161, 217, 155], [0.75, 199, 233, 192],
                                    [0.875, 229, 245, 224], [1, 247, 252, 245]]
        self._palettes['ylorrd'] = [[0, 128, 0, 38], [0.125, 189, 0, 38], [0.25, 227, 26, 28], [0.375, 252, 78, 42],
                                    [0.5, 253, 141, 60], [0.625, 254, 178, 76], [0.75, 254, 217, 118],
                                    [0.875, 255, 237, 160], [1, 255, 255, 204]]
        self._palettes['bluered'] = [[0, 0, 0, 255], [1, 255, 0, 0]]
        self._palettes['rdbu'] = [[0, 5, 10, 172], [0.35, 106, 137, 247], [0.5, 190, 190, 190], [0.6, 220, 170, 132],
                                  [0.7, 230, 145, 90], [1, 178, 10, 28]]
        self._palettes['picnic'] = [[0, 0, 0, 255], [0.1, 51, 153, 255], [0.2, 102, 204, 255], [0.3, 153, 204, 255],
                                    [0.4, 204, 204, 255], [0.5, 255, 255, 255], [0.6, 255, 204, 255],
                                    [0.7, 255, 153, 255], [0.8, 255, 102, 204], [0.9, 255, 102, 102], [1, 255, 0, 0]]
        self._palettes['rainbow'] = [[0, 150, 0, 90], [0.125, 0, 0, 200], [0.25, 0, 25, 255], [0.375, 0, 152, 255],
                                     [0.5, 44, 255, 150], [0.625, 151, 255, 0], [0.75, 255, 234, 0],
                                     [0.875, 255, 111, 0], [1, 255, 0, 0]]
        self._palettes['portland'] = [[0, 12, 51, 131], [0.25, 10, 136, 186], [0.5, 242, 211, 56], [0.75, 242, 143, 56],
                                      [1, 217, 30, 30]]
        self._palettes['jet'] = [[0, 0, 0, 131], [0.125, 0, 60, 170], [0.375, 5, 255, 255], [0.625, 255, 255, 0],
                                 [0.875, 250, 0, 0], [1, 128, 0, 0]]
        self._palettes['hot'] = [[0, 0, 0, 0], [0.3, 230, 0, 0], [0.6, 255, 210, 0], [1, 255, 255, 255]]
        self._palettes['blackbody'] = [[0, 0, 0, 0], [0.2, 230, 0, 0], [0.4, 230, 210, 0], [0.7, 255, 255, 255],
                                       [1, 160, 200, 255]]
        self._palettes['earth'] = [[0, 0, 0, 130], [0.1, 0, 180, 180], [0.2, 40, 210, 40], [0.4, 230, 230, 50],
                                   [0.6, 120, 70, 20], [1, 255, 255, 255]]
        self._palettes['electric'] = [[0, 0, 0, 0], [0.15, 30, 0, 100], [0.4, 120, 0, 100], [0.6, 160, 90, 0],
                                      [0.8, 230, 200, 0], [1, 255, 250, 220]]
        self._palettes['viridis'] = [[0, 68, 1, 84], [0.13, 71, 44, 122], [0.25, 59, 81, 139], [0.38, 44, 113, 142],
                                     [0.5, 33, 144, 141], [0.63, 39, 173, 129], [0.75, 92, 200, 99],
                                     [0.88, 170, 220, 50], [1, 253, 231, 37]]
        self._palettes['reds'] = [[0, 220, 220, 220], [0.2, 245, 195, 157], [0.4, 245, 160, 105], [1, 178, 10, 28]]
        self._palettes['blues'] = [[0, 5, 10, 172], [0.35, 40, 60, 190], [0.5, 70, 100, 245], [0.6, 90, 120, 245],
                                   [0.7, 106, 137, 247], [1, 220, 220, 220]]

        if self._nexus_palettes_only:
            return

        # These are additional, optional palettes
        self._palettes['ensight-rainbow'] = [[0,0,0,255], [0.25,0,255,255], [0.5,0,255,0], [0.75,255,255,0], [1, 255, 0, 0]]
        self._palettes['hsv'] = [[0, 255, 0, 0], [0.169, 253, 255, 2], [0.173, 247, 255, 2], [0.337, 0, 252, 4],
                                 [0.341, 0, 252, 10], [0.506, 1, 249, 255], [0.671, 2, 0, 253], [0.675, 8, 0, 253],
                                 [0.839, 255, 0, 251], [0.843, 255, 0, 245], [1, 255, 0, 6]]
        self._palettes['cool'] = [[0, 125, 0, 179], [0.13, 116, 0, 218], [0.25, 98, 74, 237], [0.38, 68, 146, 231],
                                  [0.5, 0, 204, 197], [0.63, 0, 247, 146], [0.75, 0, 255, 88], [0.88, 40, 255, 8],
                                  [1, 147, 255, 0]]
        self._palettes['spring'] = [[0, 255, 0, 255], [1, 255, 255, 0]]
        self._palettes['summer'] = [[0, 0, 128, 102], [1, 255, 255, 102]]
        self._palettes['autumn'] = [[0, 255, 0, 0], [1, 255, 255, 0]]
        self._palettes['winter'] = [[0, 0, 0, 255], [1, 0, 255, 128]]
        self._palettes['bone'] = [[0, 0, 0, 0], [0.376, 84, 84, 116], [0.753, 169, 200, 200], [1, 255, 255, 255]]
        self._palettes['copper'] = [[0, 0, 0, 0], [0.804, 255, 160, 102], [1, 255, 199, 127]]
        self._palettes['alpha'] = [[0, 255, 255, 255], [1, 255, 255, 255]]
        self._palettes['inferno'] = [[0, 0, 0, 4], [0.13, 31, 12, 72], [0.25, 85, 15, 109], [0.38, 136, 34, 106],
                                     [0.5, 186, 54, 85], [0.63, 227, 89, 51], [0.75, 249, 140, 10],
                                     [0.88, 249, 201, 50], [1, 252, 255, 164]]
        self._palettes['magma'] = [[0, 0, 0, 4], [0.13, 28, 16, 68], [0.25, 79, 18, 123], [0.38, 129, 37, 129],
                                   [0.5, 181, 54, 122], [0.63, 229, 80, 100], [0.75, 251, 135, 97],
                                   [0.88, 254, 194, 135], [1, 252, 253, 191]]
        self._palettes['plasma'] = [[0, 13, 8, 135], [0.13, 75, 3, 161], [0.25, 125, 3, 168], [0.38, 168, 34, 150],
                                    [0.5, 203, 70, 121], [0.63, 229, 107, 93], [0.75, 248, 148, 65],
                                    [0.88, 253, 195, 40], [1, 240, 249, 33]]
        self._palettes['warm'] = [[0, 125, 0, 179], [0.13, 172, 0, 187], [0.25, 219, 0, 170], [0.38, 255, 0, 130],
                                  [0.5, 255, 63, 74], [0.63, 255, 123, 0], [0.75, 234, 176, 0], [0.88, 190, 228, 0],
                                  [1, 147, 255, 0]]
        self._palettes['rainbow-soft'] = [[0, 125, 0, 179], [0.1, 199, 0, 180], [0.2, 255, 0, 121], [0.3, 255, 108, 0],
                                          [0.4, 222, 194, 0], [0.5, 150, 255, 0], [0.6, 0, 255, 55], [0.7, 0, 246, 150],
                                          [0.8, 50, 167, 222], [0.9, 103, 51, 235], [1, 124, 0, 186]]
        self._palettes['bathymetry'] = [[0, 40, 26, 44], [0.13, 59, 49, 90], [0.25, 64, 76, 139], [0.38, 63, 110, 151],
                                        [0.5, 72, 142, 158], [0.63, 85, 174, 163], [0.75, 120, 206, 163],
                                        [0.88, 187, 230, 172], [1, 253, 254, 204]]
        self._palettes['cdom'] = [[0, 47, 15, 62], [0.13, 87, 23, 86], [0.25, 130, 28, 99], [0.38, 171, 41, 96],
                                  [0.5, 206, 67, 86], [0.63, 230, 106, 84], [0.75, 242, 149, 103],
                                  [0.88, 249, 193, 135], [1, 254, 237, 176]]
        self._palettes['chlorophyll'] = [[0, 18, 36, 20], [0.13, 25, 63, 41], [0.25, 24, 91, 59], [0.38, 13, 119, 72],
                                         [0.5, 18, 148, 80], [0.63, 80, 173, 89], [0.75, 132, 196, 122],
                                         [0.88, 175, 221, 162], [1, 215, 249, 208]]
        self._palettes['density'] = [[0, 54, 14, 36], [0.13, 89, 23, 80], [0.25, 110, 45, 132], [0.38, 120, 77, 178],
                                     [0.5, 120, 113, 213], [0.63, 115, 151, 228], [0.75, 134, 185, 227],
                                     [0.88, 177, 214, 227], [1, 230, 241, 241]]
        self._palettes['freesurface-blue'] = [[0, 30, 4, 110], [0.13, 47, 14, 176], [0.25, 41, 45, 236],
                                              [0.38, 25, 99, 212], [0.5, 68, 131, 200], [0.63, 114, 156, 197],
                                              [0.75, 157, 181, 203], [0.88, 200, 208, 216], [1, 241, 237, 236]]
        self._palettes['freesurface-red'] = [[0, 60, 9, 18], [0.13, 100, 17, 27], [0.25, 142, 20, 29],
                                             [0.38, 177, 43, 27], [0.5, 192, 87, 63], [0.63, 205, 125, 105],
                                             [0.75, 216, 162, 148], [0.88, 227, 199, 193], [1, 241, 237, 236]]
        self._palettes['oxygen'] = [[0, 64, 5, 5], [0.13, 106, 6, 15], [0.25, 144, 26, 7], [0.38, 168, 64, 3],
                                    [0.5, 188, 100, 4], [0.63, 206, 136, 11], [0.75, 220, 174, 25],
                                    [0.88, 231, 215, 44], [1, 248, 254, 105]]
        self._palettes['par'] = [[0, 51, 20, 24], [0.13, 90, 32, 35], [0.25, 129, 44, 34], [0.38, 159, 68, 25],
                                 [0.5, 182, 99, 19], [0.63, 199, 134, 22], [0.75, 212, 171, 35], [0.88, 221, 210, 54],
                                 [1, 225, 253, 75]]
        self._palettes['phase'] = [[0, 145, 105, 18], [0.13, 184, 71, 38], [0.25, 186, 58, 115], [0.38, 160, 71, 185],
                                   [0.5, 110, 97, 218], [0.63, 50, 123, 164], [0.75, 31, 131, 110], [0.88, 77, 129, 34],
                                   [1, 145, 105, 18]]
        self._palettes['salinity'] = [[0, 42, 24, 108], [0.13, 33, 50, 162], [0.25, 15, 90, 145], [0.38, 40, 118, 137],
                                      [0.5, 59, 146, 135], [0.63, 79, 175, 126], [0.75, 120, 203, 104],
                                      [0.88, 193, 221, 100], [1, 253, 239, 154]]
        self._palettes['temperature'] = [[0, 4, 35, 51], [0.13, 23, 51, 122], [0.25, 85, 59, 157], [0.38, 129, 79, 143],
                                         [0.5, 175, 95, 130], [0.63, 222, 112, 101], [0.75, 249, 146, 66],
                                         [0.88, 249, 196, 65], [1, 232, 250, 91]]
        self._palettes['turbidity'] = [[0, 34, 31, 27], [0.13, 65, 50, 41], [0.25, 98, 69, 52], [0.38, 131, 89, 57],
                                       [0.5, 161, 112, 59], [0.63, 185, 140, 66], [0.75, 202, 174, 88],
                                       [0.88, 216, 209, 126], [1, 233, 246, 171]]
        self._palettes['velocity-blue'] = [[0, 17, 32, 64], [0.13, 35, 52, 116], [0.25, 29, 81, 156],
                                           [0.38, 31, 113, 162], [0.5, 50, 144, 169], [0.63, 87, 173, 176],
                                           [0.75, 149, 196, 189], [0.88, 203, 221, 211], [1, 254, 251, 230]]
        self._palettes['velocity-green'] = [[0, 23, 35, 19], [0.13, 24, 64, 38], [0.25, 11, 95, 45],
                                            [0.38, 39, 123, 35], [0.5, 95, 146, 12], [0.63, 152, 165, 18],
                                            [0.75, 201, 186, 69], [0.88, 233, 216, 137], [1, 255, 253, 205]]
        self._palettes['cubehelix'] = [[0, 0, 0, 0], [0.07, 22, 5, 59], [0.13, 60, 4, 105], [0.2, 109, 1, 135],
                                       [0.27, 161, 0, 147], [0.33, 210, 2, 142], [0.4, 251, 11, 123],
                                       [0.47, 255, 29, 97], [0.53, 255, 54, 69], [0.6, 255, 85, 46],
                                       [0.67, 255, 120, 34], [0.73, 255, 157, 37], [0.8, 241, 191, 57],
                                       [0.87, 224, 220, 93], [0.93, 218, 241, 142], [1, 227, 253, 198]]


class ConditionalFormattingHTMLStyle(ConditionalFormatting):
    """ Subclass of ConditionalFormatting that produces HTML style strings

    This subclass walks the output array generated by the ConditionalFormatting
    class and converts the cells containing dictionaries into HTML style strings,
    replacing the dictionaries.
    """
    @staticmethod
    def format_dictionary_html_style(value):
        s = ""
        if 'backcolor' in value:
            color = value['backcolor']
            # map color to "style" string
            s += "background-color: #%0.2x%0.2x%0.2x !important;" % (int(color[0] * 255),
                                                                     int(color[1] * 255), int(color[2] * 255))
        if 'forecolor' in value:
            color = value['forecolor']
            # map color to "style" string
            s += "color: #%0.2x%0.2x%0.2x !important;" % (int(color[0] * 255),
                                                          int(color[1] * 255), int(color[2] * 255))
        if 'bold' in value:
            if value['bold']:
                s += "font-weight: bold !important;"
        if 'error' in value:
            err_str = value['error']
            # it is already bad enough that we have to quote things, so we use
            err_str = err_str.replace('"', "\u201F").replace("'", "\u201F")
            s += "title='{}';".format(err_str)
        return s

    def compute_style_array(self, table, rule_string, **kwargs):
        formatting = super().compute_style_array(table, rule_string, **kwargs)
        for idx, value in numpy.ndenumerate(formatting):
            if value is None:
                continue
            formatting[idx] = self.format_dictionary_html_style(value)
        return formatting


class TreeConditionalFormattingHTMLStyle(ConditionalFormattingHTMLStyle):
    """ Subclass of ConditionalFormatting that produces HTML style strings for Nexus Tree structures

    This subclass applies conditional formatting to a Nexus 'Tree' object.
    A Nexus tree object is rooted at a dictionary with 'name', 'key' and 'value'
    keys.  There can be other keys, but 'children' is also used by this class.
    Basically, this class works by creating a numpy string array of the values
    in the tree.  The row labels are generated by concatenating 'name' and 'key'
    for the current dictionary and all of the parents.  The result is passed to
    the table formatter.  The original tree objects will have a 'htmlstyle' key
    added to it.  It will be a list strings, at least one per value.

    For this tree:

    c0 = dict(name='Child' key='leaf0', value='C')
    c1 = dict(name='Child' key='leaf1', value=['D', 'E'])
    dict(name='Top', key='root', value=['A', 'B'], children=[c0, c1])

    The table generated from this tree will look like this:

    Row name                column 0    column 1
    'Top/root'                'A'         'B'
    'Top/root|Child/leaf0'    'C'         ''
    'Top/root|Child/leaf1'    'D'         'E'

    """

    def _add_tree_row(self, entity, parent, parent_row_name, row_entities, row_parents, computed_row_names):
        # compute the numpy table parameters
        value = entity.get('value', '')
        if type(value) == list:
            num_columns = len(value)
            max_string_len = 0
            for v in value:
                size = len(str(v).encode("utf-8"))
                if size > max_string_len:
                    max_string_len = size
        else:
            num_columns = 1
            max_string_len = len(str(value))
        # generate the row name and add it in
        name = parent_row_name + entity.get('name', '') + '/' + entity.get('key', '')
        computed_row_names.append(name)
        row_entities.append(entity)
        row_parents.append(parent)
        # if there are children, recurse
        if 'children' in entity:
            name += '|'
            for child in entity['children']:
                child_columns, child_str_len = self._add_tree_row(child, entity, name, row_entities, row_parents,
                                                                  computed_row_names)
                if child_columns > num_columns:
                    num_columns = child_columns
                if child_str_len > max_string_len:
                    max_string_len = child_str_len
        return num_columns, max_string_len

    def compute_style_array(self, tree, rule_string, **kwargs):
        computed_row_names = list()
        row_entities = list()
        row_parents = list()
        # build a table from the tree
        num_columns, max_string_len = self._add_tree_row(tree, None, "", row_entities, row_parents, computed_row_names)
        table = numpy.ndarray((len(row_entities), num_columns), dtype='|S{}'.format(max_string_len+1))
        table.fill('')
        row_idx = 0
        for entity in row_entities:
            values = entity.get('value', '')
            if type(values) != list:
                values = [values]
            while len(values) < num_columns:
                values.append(None)
            for col_idx in range(num_columns):
                if values[col_idx] is not None:
                    table[row_idx][col_idx] = str(values[col_idx]).encode("utf-8")
            row_idx += 1
        # compute the formatting table
        formatting = ConditionalFormatting.compute_style_array(self, table, rule_string,
                                                               row_names=computed_row_names, **kwargs)
        # add the 'htmlstyle' and potentially update 'state'
        row_idx = 0
        for entity in row_entities:
            format_list = list()
            parent_open = None
            for col_idx in range(num_columns):
                format_dictionary = formatting[row_idx][col_idx]
                if format_dictionary is None:
                    format_list.append(None)
                else:
                    format_list.append(self.format_dictionary_html_style(format_dictionary))
                    if 'openparent' in format_dictionary:
                        parent_open = format_dictionary['openparent']
            entity['htmlstyle'] = format_list
            # If a child has the 'openparent' key, we will force the state of the parent to 'expanded'
            if parent_open is not None:
                entity = row_parents[row_idx]
                while entity is not None:
                    entity['state'] = 'expanded'
                    if parent_open == 'parent':
                        break
                    try:
                        # get the parent entity
                        entity = row_parents[row_entities.index(entity)]
                    except ValueError:
                        break
            row_idx += 1
        return tree


if __name__ == "__main__":
    import datetime
    import random
    random.seed(12345)

    def print_tree(item, indent=''):
        print("{}{}:{}:{} state:'{}' style:{}".format(indent, item['name'], item['key'], item['value'],
                                                    item.get('state', ''), item.get('htmlstyle', '')))
        if 'children' in item:
            for child in item['children']:
                print_tree(child, indent + '  ')

    print("Conditional formatting smoke test")
    print("\nTable test I")
    print(20*'-')
    # Table test case
    array = numpy.ndarray((10, 5), dtype="f")
    for row in range(10):
        array[row, 0] = row
        array[row, 1] = row*200 - 1003
        array[row, 2] = 1.2*row**3.4 + 3.5*row + 123.
        array[row, 3] = (10 - row) ** 2.3
        array[row, 4] = random.uniform(-2000, 6000)
        print("%12.5f %12.5f %12.5f %12.5f %12.5f" % tuple(array[row, :]))
    col_names = ["Linear", "Shift", "Polynomial", "Invert Poly", "Random"]
    row_names = list(range(10))
    rule = 'col(1):before()>=5.0|bold()+rgb(0.,1.,0.)&'
    rule += 'col("*Poly*"):True|bold()+pal("hot", min(), max())&'
    rule += 'col("Linear"):value>5.5|rgb(0.5,0.5,0.5);value>=3.|bold()+rgb(0.7,0.7,0.5)&'
    rule += 'col("Random"):fabs(value)>500.|pal("-Picnic", -2500, 2500, num_levels=3)+pal("picnic", -2500, 2500, num_levels=5, forecolor=True)&'
    rule += 'row(0):value<=0.0|bold()&'
    c = ConditionalFormattingHTMLStyle()
    out = c.compute_style_array(array, rule, col_names=col_names, debug=True)
    for col in range(5):
        print("Column: {}".format(col_names[col]))
        for row in range(10):
            print("%4s %12.5f %s" % (row_names[row], array[row, col], out[row, col]))
        print()
    print("Rules:", rule)

    print("\nTable test II")
    print(20*'-')
    # Table test case #2 (same data, different rule)
    rule = 'row(5):value>avg(use_row=False)|bold()&'
    rule += 'col("*Poly*"):value>avg(use_row=True)|rgb(1,0,0)&'
    rule += 'col("Shift"):value>avg(5,use_row=True)|rgb(1,1,1,forecolor=True)&'
    c = ConditionalFormattingHTMLStyle()
    # Test the case of the table being in string format '|S20'
    string_array = array.astype("|S20")
    # exercise the 'soft_float()' function.  The 'value' of this cell would be NaN w/o soft_float() handling
    string_array[7][1] = str(array[7][1]) + '[mm]'
    out = c.compute_style_array(string_array, rule, col_names=col_names, debug=True)
    for col in range(5):
        print("Column: {}".format(col_names[col]))
        for row in range(10):
            print("%4s %12s %s" % (row_names[row], string_array[row, col].decode("utf-8"), out[row, col]))
        print()
    print("Rules:", rule)

    print("\nTree test I")
    print(20*'-')
    # Tree test case
    random.seed(12345)
    c = TreeConditionalFormattingHTMLStyle()
    name = u"Simple \u4e14 string"
    value = u"Hello \u4e14 world!!"
    children = list()
    children.append(dict(key='child', name='Integer example', value=[10, 30, 3]))
    children.append(dict(key='child', name='Float example', value=[random.uniform(0, 1), "", random.uniform(0, 1)]))
    children.append(dict(key='child', name=name, value=value))
    children.append(dict(key='child', name='The current date', value=datetime.datetime.now()))
    variable = dict(name='Variable items', key='var', value='', children=children, state='collapsed')
    children = list()
    for i in range(10):
        values = [random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1)]
        children.append(dict(key='row', name='value {}'.format(i), value=values))
    table = dict(name='A Table', key='table', value=['col1', 'col2', 'col3', 'col4'], children=children,
                 state='collapsed')
    tree = dict(name='Top level', key='root', value='', children=[variable, table], state='collapsed')
    print_tree(tree)
    rule = 'row("*/table*"):value>0.5|pal("Picnic",0.,1.)&'
    rule += 'row("*|A Table*"):svalue=="col2"|bold()&'
    rule += 'row("*|Float example*"):value<0.4|rgb(0.1,0.4,0.1)+contrast()+openparents()&'
    rule += 'row("*"):int(value)==10|rgb(100.,-1.,clamp(-100.,0.,1.))+bold()&'
    tree = c.compute_style_array(tree, rule, debug=True)
    print_tree(tree)
    print("Rules:", rule)
