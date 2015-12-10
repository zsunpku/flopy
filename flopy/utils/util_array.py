"""
util_array module.  Contains the util_2d, util_3d and transient_2d classes.
 These classes encapsulate modflow-style array inputs away
 from the individual packages.  The end-user should not need to
 instantiate these classes directly.

"""
from __future__ import division, print_function
# from future.utils import with_metaclass

import os
import shutil
import copy
import numbers
import numpy as np
from flopy.utils.binaryfile import BinaryHeader


class ArrayFormat(object):
    """
    ArrayFormat class for handling various output format types for both
    MODFLOW and flopy

    Parameters
    ----------
    u2d : Util2d instance

    python : str (optional)
        python-style output format descriptor e.g. {0:15.6e}
    fortran : str (optional)
        fortran style output format descriptor e.g. (2E15.6)


    Attributes
    ----------
    fortran : str
        fortran format output descriptor (e.g. (100G15.6)
    py : str
        python format output descriptor (e.g. "{0:15.6E}")
    numpy : str
        numpy format output descriptor (e.g. "%15.6e")
    npl : int
        number if items per line of output
    width : int
        the width of the formatted numeric output
    decimal : int
        the number of decimal digits in the numeric output
    format : str
        the output format type e.g. I, G, E, etc
    free : bool
        free format flag
    binary : bool
        binary format flag


    Methods
    -------
    get_default_numpy_fmt : (dtype : [np.int,np.float32])
        a static method to get a default numpy dtype - used for loading
    decode_fortran_descriptor : (fd : str)
        a static method to decode fortran descriptors into npl, format,
        width, decimal.

    See Also
    --------

    Notes
    -----

    Examples
    --------

    """
    def __init__(self, u2d, python=None, fortran=None):

        assert isinstance(u2d,Util2d),"ArrayFormat only supports Util2d," +\
                                      "not {0}".format(type(u2d))
        if len(u2d.shape) == 1:
            self._npl_full = u2d.shape[0]
        else:
            self._npl_full = u2d.shape[1]
        self.dtype = u2d.dtype
        self._npl = None
        self._format = None
        self._width = None
        self._decimal = None
        self._freeformat_model = u2d.model.free_format

        self.default_float_width = 15
        self.default_int_width = 10
        self.default_float_format = "G"
        self.default_int_format = "I"
        self.default_float_decimal = 6
        self.default_int_decimal = 0

        self._fmts = ['I', 'G', 'E', 'F']

        self._isbinary = False
        self._isfree = False

        if python is not None and fortran is not None:
            raise Exception("only one of [python,fortran] can be passed" +
                            "to ArrayFormat constructor")

        if python is not None:
            self._parse_python_format(python)

        elif fortran is not None:
            self._parse_fortran_format(fortran)

        else:
            self._set_defaults()

    def _set_defaults(self):
        if self.dtype in [int,np.int,np.int32]:
            self._npl = self._npl_full
            self._format = self.default_int_format
            self._width = self.default_int_width
            self._decimal = None

        elif self.dtype in [np.float32,bool]:
            self._npl = self._npl_full
            self._format = self.default_float_format
            self._width = self.default_float_width
            self._decimal = self.default_float_decimal
        else:
            raise Exception("ArrayFormat._set_defaults() error: " +
                            "unsupported dtype: {0}".format(str(self.dtype)))
    def __str__(self):
        s = "ArrayFormat: npl:{0},format:{1},width:{2},decimal{3}"\
            .format(self.npl, self.format, self.width, self.decimal)
        s += ",isfree:{0},isbinary:{1}".format(self._isfree, self._isbinary)
        return s

    @staticmethod
    def get_default_numpy_fmt(dtype):
        if dtype == np.int:
            return "%10d"
        elif dtype == np.float32:
            return "%15.6E"
        else:
            raise Exception("ArrayFormat.get_default_numpy_fmt(): unrecognized " + \
                            "dtype, must be np.int or np.float32")

    @classmethod
    def integer(cls):
        raise NotImplementedError()

    @classmethod
    def float(cls):
        raise NotImplementedError()

    @property
    def binary(self):
        return bool(self._isbinary)

    @property
    def free(self):
        return bool(self._isfree)

    def __eq__(self, other):
        if isinstance(other,str):
            if other.lower() == "free":
                return self.free
            if other.lower() == "binary":
                return self.binary
        else:
            super(ArrayFormat,self).__eq__(other)

    @property
    def npl(self):
        return copy.copy(self._npl)

    @property
    def format(self):
        return copy.copy(self._format)

    @property
    def width(self):
        return copy.copy(self._width)

    @property
    def decimal(self):
        return copy.copy(self._decimal)

    def __setattr__(self, key, value):
        if key == "format":
            value = value.upper()
            assert value.upper() in self._fmts
            if value == 'I':
                assert self.dtype in [int, np.int, np.int32]
                self._format = value
                self._decimal = None
            else:
                self._format = value
                if self.decimal is None:
                    self._decimal = self.default_float_decimal

        elif key == "width":
            width = int(value)
            if self.dtype == np.float32 and width < self.decimal:
                raise Exception("width cannot be less than decimal")
            elif self.dtype == np.float32 and \
                width < self.default_float_width:
                print("ArrayFormat warning:setting width less " +
                      "than default of {0}".format(self.default_float_width))
                self._width = width
        elif key == "decimal":
            if self.dtype in [int,np.int,np.int32]:
                raise Exception("cannot set decimal for integer dtypes")
            else:
                value = int(value)
                if value < self.default_float_decimal:
                    print("ArrayFormat warning: setting decimal " +
                          " less than default of " +
                          "{0}".format(self.default_float_decimal))
                if value < self.decimal:
                    print("ArrayFormat warning: setting decimal " +
                          " less than current value of " +
                          "{0}".format(self.default_float_decimal))
                self._decimal = int(value)

        elif key == "entries" \
                or key == "entires_per_line" \
                or key == "npl":
            value = int(value)
            assert value <= self._npl_full, "cannot set npl > shape"
            self._npl = value

        elif key.lower() == "binary":
            value = bool(value)
            if value and self.free:
            #    raise Exception("cannot switch from 'free' to 'binary' format")
                self._isfree = False
            self._isbinary = value
            self._set_defaults()

        elif key.lower() == "free":
            value = bool(value)
            if value and self.binary:
            #    raise Exception("cannot switch from 'binary' to 'free' format")
                self._isbinary = False
            self._isfree = bool(value)
            self._set_defaults()

        elif key.lower() == "fortran":
            self._parse_fortran_format(value)

        elif key.lower() == "python" or key.lower() == "py":
            self._parse_python_format(value)

        else:
            super(ArrayFormat,self).__setattr__(key, value)

    @property
    def py(self):
        return self._get_python_format()

    def _get_python_format(self):

        if self.format == 'I':
            fmt = 'd'
        else:
            fmt = self.format
        pd = '{0:' + str(self.width)
        if self.decimal is not None:
            pd += '.' + str(self.decimal) + fmt + '}'
        else:
            pd += fmt + '}'

        if self.npl is None:
            if self._isfree:
                return (self._npl_full, pd)
            else:
                raise Exception("ArrayFormat._get_python_format() error: " +\
                                "format is not 'free' and npl is not set")

        return (self.npl, pd)

    def _parse_python_format(self, arg):
        raise NotImplementedError()

    @property
    def fortran(self):
        return self._get_fortran_format()

    def _get_fortran_format(self):
        if self._isfree:
            return "(FREE)"
        if self._isbinary:
            return "(BINARY)"

        fd = '({0:d}{1:s}{2:d}'.format(self.npl,self.format,self.width)
        if self.decimal is not None:
            fd += '.{0:d})'.format(self.decimal)
        else:
            fd += ')'
        return fd

    def _parse_fortran_format(self, arg):
        """Decode fortran descriptor

        Parameters
        ----------
        arg : str

        Returns
        -------
        npl, fmt, width, decimal : int, str, int, int

        """
        # strip off any quotes around format string

        npl, fmt, width, decimal = ArrayFormat.decode_fortran_descriptor(arg)
        if isinstance(npl,str):
            if 'FREE' in npl.upper():
                self._set_defaults()
                self._isfree = True
                return

            elif 'BINARY' in npl.upper():
                self._set_defaults()
                self._isbinary = True
                return
        self._npl = int(npl)
        self._format = fmt
        self._width = int(width)
        if decimal is not None:
            self._decimal = int(decimal)


    @property
    def numpy(self):
        return self._get_numpy_format()

    def _get_numpy_format(self):
        return "%{0}{1}.{2}".format(self.width,self.format,self.decimal)

    @staticmethod
    def decode_fortran_descriptor(fd):
        """Decode fortran descriptor

        Parameters
        ----------
        fd : str

        Returns
        -------
        npl, fmt, width, decimal : int, str, int, int

        """
        # strip off any quotes around format string
        fd = fd.replace("'", "")
        fd = fd.replace('"', '')
        # strip off '(' and ')'
        fd = fd.strip()[1:-1]
        if str('FREE') in str(fd.upper()):
            return 'free', None, None, None
        elif str('BINARY') in str(fd.upper()):
            return 'binary', None, None, None
        if str('.') in str(fd):
            raw = fd.split('.')
            decimal = int(raw[1])
        else:
            raw = [fd]
            decimal = None
        fmts = ['I', 'G', 'E', 'F']
        raw = raw[0].upper()
        for fmt in fmts:
            if fmt in raw:
                raw = raw.split(fmt)
                # '(F9.0)' will return raw = ['', '9']
                #  try and except will catch this
                try:
                    npl = int(raw[0])
                    width = int(raw[1])
                except:
                    npl = 1
                    width = int(raw[1])
                if fmt == 'G':
                    fmt = 'E'
                return npl, fmt, width, decimal
        raise Exception('Unrecognized format type: ' +
                        str(fd) + ' looking for: ' + str(fmts))


def read1d(f, a):
    """
    Fill the 1d array, a, with the correct number of values.  Required in
    case lpf 1d arrays (chani, layvka, etc) extend over more than one line

    """
    values = []
    while True:
        line = f.readline()
        t = line.strip().split()
        values = values + t
        if len(values) >= a.shape[0]:
            break
    a[:] = np.array(values[0:a.shape[0]], dtype=a.dtype)
    return a


def new_u2d(old_util2d, value):
    new_util2d = Util2d(old_util2d.model, old_util2d.shape, old_util2d.dtype,
                         value, old_util2d.name, old_util2d.fmtin,
                         old_util2d.cnstnt, old_util2d.iprn,
                         old_util2d.ext_filename, old_util2d.locat,
                         old_util2d.bin)
    return new_util2d


class Util3d(object):
    """
    Util3d class for handling 3-D model arrays.  just a thin wrapper around
        Util2d

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    shape : length 3 tuple
        shape of the 3-D array, typically (nlay,nrow,ncol)
    dtype : [np.int,np.float32,np.bool]
        the type of the data
    value : variable
        the data to be assigned to the 3-D array.
        can be a scalar, list, or ndarray
    name : string
        name of the property, used for writing comments to input files
    fmtin : string
        modflow fmtin variable (optional).  (the default is None)
    cnstnt : string
        modflow cnstnt variable (optional) (the default is 1.0)
    iprn : int
        modflow iprn variable (optional) (the default is -1)
    locat : int
        modflow locat variable (optional) (the default is None).  If the model
        instance does not support free format and the
        external flag is not set and the value is a simple scalar,
        then locat must be explicitly passed as it is the unit number
        to read the array from
    ext_filename : string
        the external filename to write the array representation to
        (optional) (the default is None) .
        If type(value) is a string and is an accessible filename, the
        ext_filename is reset to value.
    bin : bool
        flag to control writing external arrays as binary (optional)
        (the defaut is False)

    Attributes
    ----------
    array : np.ndarray
        the array representation of the 3-D object


    Methods
    -------
    get_file_entry : string
        get the model input file string including the control record for the
        entire 3-D property

    See Also
    --------

    Notes
    -----

    Examples
    --------

    """

    def __init__(self, model, shape, dtype, value, name,
                 fmtin=None, cnstnt=1.0, iprn=-1, locat=None,
                 ext_unit_dict=None):
        """
        3-D wrapper from Util2d - shape must be 3-D
        """
        if isinstance(value, Util3d):
            for attr in value.__dict__.items():
                setattr(self, attr[0], attr[1])
            self.model = model
            for i, u2d in enumerate(self.util_2ds):
                self.util_2ds[i] = Util2d(model, u2d.shape, u2d.dtype,
                                           u2d._array, name=u2d.name,
                                           fmtin=u2d.format.fortran, locat=locat,
                                           cnstnt=u2d.cnstnt)

            return
        assert len(shape) == 3, 'Util3d:shape attribute must be length 3'
        self.model = model
        self.shape = shape
        self.dtype = dtype
        self.__value = value
        if isinstance(name, list):
            self.name = name
        else:
            t = []
            for k in range(shape[0]):
                t.append(name)
            self.name = t
        self.name_base = []
        for k in range(shape[0]):
            if 'Layer' not in self.name[k]:
                self.name_base.append(self.name[k] + ' Layer ')
            else:
                self.name_base.append(self.name[k])
        self.fmtin = fmtin
        self.cnstnt = cnstnt
        self.iprn = iprn
        self.locat = locat
        if model.external_path is not None:
            self.ext_filename_base = []
            for k in range(shape[0]):
                self.ext_filename_base.append(os.path.join(model.external_path,
                                                           self.name_base[
                                                               k].replace(' ',
                                                                          '_')))
        self.util_2ds = self.build_2d_instances()

    def __setitem__(self, k, value):
        if isinstance(k, int):
            assert k in range(0, self.shape[
                0]), "Util3d error: k not in range nlay"
            self.util_2ds[k] = new_u2d(self.util_2ds[k], value)
        else:
            raise NotImplementedError(
                "Util3d doesn't support setitem indices" + str(k))

    def __setattr__(self, key, value):
        if hasattr(self, "util_2ds") and key == "cnstnt":
            # set the cnstnt for each u2d
            for u2d in self.util_2ds:
                u2d.cnstnt = value
        elif hasattr(self,"util_2ds") and key == "fmtin":
            for u2d in self.util_2ds:
                u2d.format = ArrayFormat(u2d,fortran=value)
        elif hasattr(self,"util_2ds") and key == "how":
            for u2d in self.util_2ds:
                u2d.how = value
        else:
            # set the attribute for u3d
            super(Util3d, self).__setattr__(key, value)

    def export(self, f):
        from flopy import export
        return export.utils.util3d_helper(f, self)

    def to_shapefile(self, filename):
        """
        Export 3-D model data to shapefile (polygons).  Adds an
            attribute for each Util2d in self.u2ds

        Parameters
        ----------
        filename : str
            Shapefile name to write

        Returns
        ----------
        None

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.lpf.hk.to_shapefile('test_hk.shp')
        """

        from flopy.utils.flopy_io import write_grid_shapefile, shape_attr_name

        array_dict = {}
        for ilay in range(self.model.nlay):
            u2d = self[ilay]
            name = '{}_{:03d}'.format(shape_attr_name(u2d.name), ilay + 1)
            array_dict[name] = u2d.array
        write_grid_shapefile(filename, self.model.dis.sr,
                             array_dict)

    def plot(self, filename_base=None, file_extension=None, mflay=None,
             fignum=None, **kwargs):
        """
        Plot 3-D model input data

        Parameters
        ----------
        filename_base : str
            Base file name that will be used to automatically generate file
            names for output image files. Plots will be exported as image
            files if file_name_base is not None. (default is None)
        file_extension : str
            Valid matplotlib.pyplot file extension for savefig(). Only used
            if filename_base is not None. (default is 'png')
        mflay : int
            MODFLOW zero-based layer number to return.  If None, then all
            all layers will be included. (default is None)
        **kwargs : dict
            axes : list of matplotlib.pyplot.axis
                List of matplotlib.pyplot.axis that will be used to plot
                data for each layer. If axes=None axes will be generated.
                (default is None)
            pcolor : bool
                Boolean used to determine if matplotlib.pyplot.pcolormesh
                plot will be plotted. (default is True)
            colorbar : bool
                Boolean used to determine if a color bar will be added to
                the matplotlib.pyplot.pcolormesh. Only used if pcolor=True.
                (default is False)
            inactive : bool
                Boolean used to determine if a black overlay in inactive
                cells in a layer will be displayed. (default is True)
            contour : bool
                Boolean used to determine if matplotlib.pyplot.contour
                plot will be plotted. (default is False)
            clabel : bool
                Boolean used to determine if matplotlib.pyplot.clabel
                will be plotted. Only used if contour=True. (default is False)
            grid : bool
                Boolean used to determine if the model grid will be plotted
                on the figure. (default is False)
            masked_values : list
                List of unique values to be excluded from the plot.

        Returns
        ----------
        out : list
            Empty list is returned if filename_base is not None. Otherwise
            a list of matplotlib.pyplot.axis is returned.

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.lpf.hk.plot()

        """
        import flopy.plot.plotutil as pu

        if file_extension is not None:
            fext = file_extension
        else:
            fext = 'png'

        names = ['{} layer {}'.format(self.name[k], k + 1) for k in
                 range(self.shape[0])]

        filenames = None
        if filename_base is not None:
            if mflay is not None:
                i0 = int(mflay)
                if i0 + 1 >= self.shape[0]:
                    i0 = self.shape[0] - 1
                i1 = i0 + 1
            else:
                i0 = 0
                i1 = self.shape[0]
            # build filenames
            filenames = ['{}_{}_Layer{}.{}'.format(filename_base, self.name[k],
                                                   k + 1, fext) for k in
                         range(i0, i1)]

        return pu._plot_array_helper(self.array, self.model,
                                     names=names, filenames=filenames,
                                     mflay=mflay, fignum=fignum, **kwargs)

    def __getitem__(self, k):
        if isinstance(k, int):
            return self.util_2ds[k]
        elif len(k) == 3:
            return self.array[k[0], k[1], k[2]]
        else:
            raise Exception("Util3d error: unsupported indices:" + str(k))

    def get_file_entry(self):
        s = ''
        for u2d in self.util_2ds:
            s += u2d.get_file_entry()
        return s

    def get_value(self):
        value = []
        for u2d in self.util_2ds:
            value.append(u2d.get_value())
        return value

    @property
    def array(self):
        a = np.empty((self.shape), dtype=self.dtype)
        # for i,u2d in self.uds:
        for i, u2d in enumerate(self.util_2ds):
            a[i] = u2d.array
        return a

    def build_2d_instances(self):
        u2ds = []
        # if value is not enumerable, then make a list of something
        if not isinstance(self.__value, list) \
                and not isinstance(self.__value, np.ndarray):
            self.__value = [self.__value] * self.shape[0]

        # if this is a list or 1-D array with constant values per layer
        if isinstance(self.__value, list) \
                or (isinstance(self.__value, np.ndarray)
                    and (self.__value.ndim == 1)):

            assert len(self.__value) == self.shape[0], \
                'length of 3d enumerable:' + str(len(self.__value)) + \
                ' != to shape[0]:' + str(self.shape[0])

            for i, item in enumerate(self.__value):
                if isinstance(item, Util2d):
                    u2ds.append(item)
                else:
                    name = self.name_base[i] + str(i + 1)
                    ext_filename = None
                    if self.model.external_path is not None:
                        ext_filename = self.ext_filename_base[i] + str(i + 1) + \
                                       '.ref'
                    u2d = Util2d(self.model, self.shape[1:], self.dtype, item,
                                 fmtin=self.fmtin, name=name,
                                 ext_filename=ext_filename,
                                 locat=self.locat)
                    u2ds.append(u2d)

        elif isinstance(self.__value, np.ndarray):
            # if an array of shape nrow,ncol was passed, tile it out for each layer
            if self.__value.shape[0] != self.shape[0]:
                if self.__value.shape == (self.shape[1], self.shape[2]):
                    self.__value = [self.__value] * self.shape[0]
                else:
                    raise Exception('value shape[0] != to self.shape[0] and' +
                                    'value.shape[[1,2]] != self.shape[[1,2]]' +
                                    str(self.__value.shape) + ' ' + str(
                        self.shape))
            for i, a in enumerate(self.__value):
                a = np.atleast_2d(a)
                ext_filename = None
                name = self.name_base[i] + str(i + 1)
                if self.model.external_path is not None:
                    ext_filename = self.ext_filename_base[i] + str(
                        i + 1) + '.ref'
                u2d = Util2d(self.model, self.shape[1:], self.dtype, a,
                             fmtin=self.fmtin, name=name,
                             ext_filename=ext_filename,
                             locat=self.locat)
                u2ds.append(u2d)

        else:
            raise Exception('util_array_3d: value attribute must be list ' +
                            ' or ndarray, not' + str(type(self.__value)))
        return u2ds

    @staticmethod
    def load(f_handle, model, shape, dtype, name, ext_unit_dict=None):
        assert len(shape) == 3, 'Util3d:shape attribute must be length 3'
        nlay, nrow, ncol = shape
        u2ds = []
        for k in range(nlay):
            u2d = Util2d.load(f_handle, model, (nrow, ncol), dtype, name,
                               ext_unit_dict=ext_unit_dict)
            u2ds.append(u2d)
        u3d = Util3d(model, shape, dtype, u2ds, name)
        return u3d

    def __mul__(self, other):
        if np.isscalar(other):
            new_u2ds = []
            for u2d in self.util_2ds:
                new_u2ds.append(u2d * other)
            return Util3d(self.model, self.shape, self.dtype, new_u2ds,
                          self.name, self.fmtin, self.cnstnt, self.iprn,
                          self.locat)
        elif isinstance(other, list):
            assert len(other) == self.shape[0]
            new_u2ds = []
            for u2d,item in zip(self.util_2ds,other):
                new_u2ds.append(u2d * item)
            return Util3d(self.model, self.shape, self.dtype, new_u2ds,
                          self.name, self.fmtin, self.cnstnt, self.iprn,
                          self.locat)


class Transient2d(object):
    """
    Transient2d class for handling time-dependent 2-D model arrays.
    just a thin wrapper around Util2d

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    shape : length 2 tuple
        shape of the 2-D transient arrays, typically (nrow,ncol)
    dtype : [np.int,np.float32,np.bool]
        the type of the data
    value : variable
        the data to be assigned to the 2-D arrays. Typically a dict
        of {kper:value}, where kper is the zero-based stress period
        to assign a value to.  Value should be cast-able to Util2d instance
        can be a scalar, list, or ndarray is the array value is constant in
        time.
    name : string
        name of the property, used for writing comments to input files and
        for forming external files names (if needed)
    fmtin : string
        modflow fmtin variable (optional).  (the default is None)
    cnstnt : string
        modflow cnstnt variable (optional) (the default is 1.0)
    iprn : int
        modflow iprn variable (optional) (the default is -1)
    locat : int
        modflow locat variable (optional) (the default is None).  If the model
        instance does not support free format and the
        external flag is not set and the value is a simple scalar,
        then locat must be explicitly passed as it is the unit number
         to read the array from
    ext_filename : string
        the external filename to write the array representation to
        (optional) (the default is None) .
        If type(value) is a string and is an accessible filename,
        the ext_filename is reset to value.
    bin : bool
        flag to control writing external arrays as binary (optional)
        (the default is False)

    Attributes
    ----------
    transient_2ds : dict{kper:Util2d}
        the transient sequence of Util2d objects

    Methods
    -------
    get_kper_entry : (itmp,string)
        get the itmp value and the Util2d file entry of the value in
        transient_2ds in bin kper.  if kper < min(Transient2d.keys()),
        return (1,zero_entry<Util2d>).  If kper > < min(Transient2d.keys()),
        but is not found in Transient2d.keys(), return (-1,'')

    See Also
    --------

    Notes
    -----

    Examples
    --------

    """

    def __init__(self, model, shape, dtype, value, name, fmtin=None,
                 cnstnt=1.0, iprn=-1, ext_filename=None, locat=None,
                 bin=False):

        if isinstance(value, Transient2d):
            for attr in value.__dict__.items():
                setattr(self, attr[0], attr[1])
            for kper, u2d in self.transient_2ds.items():
                self.transient_2ds[kper] = Util2d(model, u2d.shape, u2d.dtype,
                                                  u2d._array, name=u2d.name,
                                                  fmtin=u2d.format.fortran, locat=locat,
                                                  cnstnt=u2d.cnstnt)

            self.model = model
            return

        self.model = model
        assert len(shape) == 2, "Transient2d error: shape arg must be " + \
                                "length two (nrow, ncol), not " + \
                                str(shape)
        self.shape = shape
        self.dtype = dtype
        self.__value = value
        self.name_base = name
        self.fmtin = fmtin
        self.cnstst = cnstnt
        self.iprn = iprn
        self.locat = locat
        if model.external_path is not None:
            self.ext_filename_base = \
                os.path.join(model.external_path,
                             self.name_base.replace(' ', '_'))
        self.transient_2ds = self.build_transient_sequence()
        return

    def __setattr__(self, key, value):
        if hasattr(self, "transient_2ds") and key == "cnstnt":
            # set cnstnt for each u2d
            for kper,u2d in self.transient_2ds.items():
                self.transient_2ds[kper].cnstnt = value
        elif hasattr(self, "transient_2ds") and key == "fmtin":
            # set fmtin for each u2d
            for kper,u2d in self.transient_2ds.items():
                self.transient_2ds[kper].format = ArrayFormat(u2d,fortran=value)
        elif hasattr(self, "transient_2ds") and key == "how":
            # set how for each u2d
            for kper,u2d in self.transient_2ds.items():
                self.transient_2ds[kper].how = value
        # set the attribute for u3d, even for cnstnt
        super(Transient2d, self).__setattr__(key, value)

    def get_zero_2d(self, kper):
        name = self.name_base + str(kper + 1) + '(filled zero)'
        return Util2d(self.model, self.shape,
                       self.dtype, 0.0, name=name).get_file_entry()

    def to_shapefile(self, filename):
        """
        Export transient 2D data to a shapefile (as polygons). Adds an
            attribute for each unique Util2d instance in self.data

        Parameters
        ----------
        filename : str
            Shapefile name to write

        Returns
        ----------
        None

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.rch.rech.as_shapefile('test_rech.shp')
        """
        from flopy.utils.flopy_io import write_grid_shapefile, shape_attr_name

        array_dict = {}
        for kper in range(self.model.nper):
            u2d = self[kper]
            name = '{}_{:03d}'.format(shape_attr_name(u2d.name), kper + 1)
            array_dict[name] = u2d.array
        write_grid_shapefile(filename, self.model.dis.sr, array_dict)

    def plot(self, filename_base=None, file_extension=None, **kwargs):
        """
        Plot transient 2-D model input data

        Parameters
        ----------
        filename_base : str
            Base file name that will be used to automatically generate file
            names for output image files. Plots will be exported as image
            files if file_name_base is not None. (default is None)
        file_extension : str
            Valid matplotlib.pyplot file extension for savefig(). Only used
            if filename_base is not None. (default is 'png')
        **kwargs : dict
            axes : list of matplotlib.pyplot.axis
                List of matplotlib.pyplot.axis that will be used to plot
                data for each layer. If axes=None axes will be generated.
                (default is None)
            pcolor : bool
                Boolean used to determine if matplotlib.pyplot.pcolormesh
                plot will be plotted. (default is True)
            colorbar : bool
                Boolean used to determine if a color bar will be added to
                the matplotlib.pyplot.pcolormesh. Only used if pcolor=True.
                (default is False)
            inactive : bool
                Boolean used to determine if a black overlay in inactive
                cells in a layer will be displayed. (default is True)
            contour : bool
                Boolean used to determine if matplotlib.pyplot.contour
                plot will be plotted. (default is False)
            clabel : bool
                Boolean used to determine if matplotlib.pyplot.clabel
                will be plotted. Only used if contour=True. (default is False)
            grid : bool
                Boolean used to determine if the model grid will be plotted
                on the figure. (default is False)
            masked_values : list
                List of unique values to be excluded from the plot.
            kper : str
                MODFLOW zero-based stress period number to return. If
                kper='all' then data for all stress period will be
                extracted. (default is zero).

        Returns
        ----------
        out : list
            Empty list is returned if filename_base is not None. Otherwise
            a list of matplotlib.pyplot.axis is returned.

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.rch.rech.plot()

        """
        import flopy.plot.plotutil as pu

        if file_extension is not None:
            fext = file_extension
        else:
            fext = 'png'

        if 'kper' in kwargs:
            kk = kwargs['kper']
            kwargs.pop('kper')
            try:
                kk = kk.lower()
                if kk == 'all':
                    k0 = 0
                    k1 = self.model.nper
                else:
                    k0 = 0
                    k1 = 1
            except:
                k0 = int(kk)
                k1 = k0 + 1
                # if kwargs['kper'] == 'all':
                #     kwargs.pop('kper')
                #     k0 = 0
                #     k1 = self.model.nper
                # else:
                #     k0 = int(kwargs.pop('kper'))
                #     k1 = k0 + 1
        else:
            k0 = 0
            k1 = 1

        if 'fignum' in kwargs:
            fignum = kwargs.pop('fignum')
        else:
            fignum = list(range(k0, k1))

        if 'mflay' in kwargs:
            kwargs.pop('mflay')

        axes = []
        for idx, kper in enumerate(range(k0, k1)):
            title = '{} stress period {:d}'. \
                format(self.name_base.replace('_', '').upper(),
                       kper + 1)
            if filename_base is not None:
                filename = filename_base + '_{:05d}.{}'.format(kper + 1, fext)
            else:
                filename = None
            axes.append(pu._plot_array_helper(self[kper].array, self.model,
                                              names=title, filenames=filename,
                                              fignum=fignum[idx], **kwargs))
        return axes

    def __getitem__(self, kper):
        if kper in list(self.transient_2ds.keys()):
            return self.transient_2ds[kper]
        elif kper < min(self.transient_2ds.keys()):
            return self.get_zero_2d(kper)
        else:
            for i in range(kper, -1, -1):
                if i in list(self.transient_2ds.keys()):
                    return self.transient_2ds[i]
            raise Exception("Transient2d.__getitem__(): error:" + \
                            " could not find an entry before kper {0:d}".format(
                                kper))

    @property
    def array(self):
        arr = np.zeros((self.model.dis.nper, self.shape[0], self.shape[1]),
                       dtype=self.dtype)
        for kper in range(self.model.dis.nper):
            u2d = self[kper]
            arr[kper, :, :] = u2d.array
        return arr

    def export(self, f):
        from flopy import export
        return export.utils.transient2d_helper(f, self)

    def get_kper_entry(self, kper):
        """
        get the file entry info for a given kper
        returns (itmp,file entry string from Util2d)
        """
        if kper in self.transient_2ds:
            return (1, self.transient_2ds[kper].get_file_entry())
        elif kper < min(self.transient_2ds.keys()):
            return (1, self.get_zero_2d(kper))
        else:
            return (-1, '')

    def build_transient_sequence(self):
        """
        parse self.__value into a dict{kper:Util2d}
        """

        # a dict keyed on kper (zero-based)
        if isinstance(self.__value, dict):
            tran_seq = {}
            for key, val in self.__value.items():
                try:
                    key = int(key)
                except:
                    raise Exception("Transient2d error: can't cast key: " +
                                    str(key) + " to kper integer")
                if key < 0:
                    raise Exception("Transient2d error: key can't be " +
                                    " negative: " + str(key))
                try:
                    u2d = self.__get_2d_instance(key, val)
                except Exception as e:
                    raise Exception("Transient2d error building Util2d " +
                                    " instance from value at kper: " +
                                    str(key) + "\n" + str(e))
                tran_seq[key] = u2d
            return tran_seq

        # these are all for single entries - use the same Util2d for all kper
        # an array of shape (nrow,ncol)
        elif isinstance(self.__value, np.ndarray):
            return {0: self.__get_2d_instance(0, self.__value)}

        # a filename
        elif isinstance(self.__value, str):
            return {0: self.__get_2d_instance(0, self.__value)}

        # a scalar
        elif np.isscalar(self.__value):
            return {0: self.__get_2d_instance(0, self.__value)}

        # lists aren't allowed
        elif isinstance(self.__value, list):
            raise Exception("Transient2d error: value cannot be a list " +
                            "anymore.  try a dict{kper,value}")
        else:
            raise Exception("Transient2d error: value type not " +
                            " recognized: " + str(type(self.__value)))

    def __get_2d_instance(self, kper, arg):
        """
        parse an argument into a Util2d instance
        """
        ext_filename = None
        name = self.name_base + str(kper + 1)
        if self.model.external_path is not None:
            ext_filename = self.ext_filename_base + str(kper) + '.ref'
        u2d = Util2d(self.model, self.shape, self.dtype, arg,
                     fmtin=self.fmtin, name=name,
                     ext_filename=ext_filename,
                     locat=self.locat)
        return u2d


class Util2d(object):
    """
    Util2d class for handling 2-D model arrays

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    shape : lenght 3 tuple
        shape of the 3-D array
    dtype : [np.int,np.float32,np.bool]
        the type of the data
    value : variable
        the data to be assigned to the 2-D array.
        can be a scalar, list, ndarray, or filename
    name : string
        name of the property (optional). (the default is None
    fmtin : string
        modflow fmtin variable (optional).  (the default is None)
    cnstnt : string
        modflow cnstnt variable (optional) (the default is 1.0)
    iprn : int
        modflow iprn variable (optional) (the default is -1)
    locat : int
        modflow locat variable (optional) (the default is None).  If the model
        instance does not support free format and the
        external flag is not set and the value is a simple scalar,
        then locat must be explicitly passed as it is the unit number
         to read the array from)
    ext_filename : string
        the external filename to write the array representation to
        (optional) (the default is None) .
        If type(value) is a string and is an accessible filename,
        the ext_filename is reset to value.
    bin : bool
        flag to control writing external arrays as binary (optional)
        (the default is False)

    Attributes
    ----------
    array : np.ndarray
        the array representation of the 2-D object
    how : str
        the str flag to control how the array is written to the model
        input files e.g. "constant","internal","external","openclose"
    format : ArrayFormat object
        controls the ASCII representation of the numeric array

    Methods
    -------
    get_file_entry : string
        get the model input file string including the control record

    See Also
    --------

    Notes
    -----
    If value is a valid filename and model.external_path is None, then a copy
    of the file is made and placed in model.model_ws directory.

    If value is a valid filename and model.external_path is not None, then
    a copy of the file is made a placed in the external_path directory.

    If value is a scalar, it is always written as a constant, regardless of
    the model.external_path setting.

    If value is an array and model.external_path is not None, then the array
    is written out in the external_path directory.  The name of the file that
    holds the array is created from the name attribute.  If the model supports
    "free format", then the array is accessed via the "open/close" approach.
    Otherwise, a unit number and filename is added to the name file.

    If value is an array and model.external_path is None, then the array is
    written internally to the model input file.

    Examples
    --------

    """

    def __init__(self, model, shape, dtype, value, name, fmtin=None,
                 cnstnt=1.0, iprn=-1, ext_filename=None, locat=None, bin=False,
                 how=None):
        """
        1d or 2-d array support with minimum of mem footprint.
        only creates arrays as needed, 
        otherwise functions with strings or constants
        shape = 1-d or 2-d tuple
        value =  an instance of string,list,np.int,np.float32,np.bool or np.ndarray
        vtype = str,np.int,np.float32,np.bool, or np.ndarray
        dtype = np.int, or np.float32
        if ext_filename is passed, scalars are written externally as arrays
        model instance bool attribute "free_format" used for generating control record
        model instance string attribute "external_path" 
        used to determine external array writing
        bin controls writing of binary external arrays
        """
        if isinstance(value, Util2d):
            for attr in value.__dict__.items():
                setattr(self, attr[0], attr[1])
            self.model = model
            return
        if name is not None:
            name = name.lower()
        if ext_filename is not None:
            ext_filename = ext_filename.lower()

        self.model = model
        for s in shape:
            assert isinstance(s,numbers.Integral),"all shape elements must be integers, " +\
                                                  "not {0}:{1}".format(type(s), str(s))
        self.shape = shape
        self.dtype = dtype
        self.name = name
        self.locat = locat
        self.parse_value(value)
        self.__value_built = None
        self.cnstnt = float(cnstnt)
        self.iprn = iprn
        self._format = ArrayFormat(self,fortran=fmtin)
        self._format.binary = bool(bin)
        self.ext_filename = ext_filename
        self._ext_filename = self.name.replace(' ','_') + ".ref"

        self._acceptable_hows = ["constant","internal","external","openclose"]

        # some defense
        if dtype not in [np.int, np.int32, np.float32, np.bool]:
            raise Exception('Util2d:unsupported dtype: ' + str(dtype))

        if how is not None:
            how = how.lower()
            assert how in self._acceptable_hows
            self._how = how
        else:
            self._decide_how()

    def _decide_how(self):
        #if a constant was passed in
        if self.vtype in [np.int,np.float32]:
            self._how = "constant"
        # if a filename was passed in or external path was set
        elif self.model.external_path is not None or \
            self.vtype == str:
            if self.model.free_format:
                self._how = "openclose"
            else:
                self._how = "external"

        else:
            self._how = "internal"

    def plot(self, title=None, filename_base=None, file_extension=None,
             fignum=None, **kwargs):
        """
        Plot 2-D model input data

        Parameters
        ----------
        title : str
            Plot title. If a plot title is not provide one will be
            created based on data name (self.name). (default is None)
        filename_base : str
            Base file name that will be used to automatically generate file
            names for output image files. Plots will be exported as image
            files if file_name_base is not None. (default is None)
        file_extension : str
            Valid matplotlib.pyplot file extension for savefig(). Only used
            if filename_base is not None. (default is 'png')
        **kwargs : dict
            axes : list of matplotlib.pyplot.axis
                List of matplotlib.pyplot.axis that will be used to plot
                data for each layer. If axes=None axes will be generated.
                (default is None)
            pcolor : bool
                Boolean used to determine if matplotlib.pyplot.pcolormesh
                plot will be plotted. (default is True)
            colorbar : bool
                Boolean used to determine if a color bar will be added to
                the matplotlib.pyplot.pcolormesh. Only used if pcolor=True.
                (default is False)
            inactive : bool
                Boolean used to determine if a black overlay in inactive
                cells in a layer will be displayed. (default is True)
            contour : bool
                Boolean used to determine if matplotlib.pyplot.contour
                plot will be plotted. (default is False)
            clabel : bool
                Boolean used to determine if matplotlib.pyplot.clabel
                will be plotted. Only used if contour=True. (default is False)
            grid : bool
                Boolean used to determine if the model grid will be plotted
                on the figure. (default is False)
            masked_values : list
                List of unique values to be excluded from the plot.

        Returns
        ----------
        out : list
            Empty list is returned if filename_base is not None. Otherwise
            a list of matplotlib.pyplot.axis is returned.

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.dis.top.plot()
        
        """
        import flopy.plot.plotutil as pu

        if title is None:
            title = self.name

        if file_extension is not None:
            fext = file_extension
        else:
            fext = 'png'

        filename = None
        if filename_base is not None:
            filename = '{}_{}.{}'.format(filename_base, self.name, fext)

        return pu._plot_array_helper(self.array, self.model,
                                     names=title, filenames=filename,
                                     fignum=fignum, **kwargs)

    def export(self, f):
        from flopy import export
        return export.utils.util2d_helper(f, self)

    def to_shapefile(self, filename):
        """
        Export 2-D model data to a shapefile (as polygons) of self.array

        Parameters
        ----------
        filename : str
            Shapefile name to write

        Returns
        ----------
        None

        See Also
        --------

        Notes
        -----

        Examples
        --------
        >>> import flopy
        >>> ml = flopy.modflow.Modflow.load('test.nam')
        >>> ml.dis.top.as_shapefile('test_top.shp')
        """
        from flopy.utils.flopy_io import write_grid_shapefile, shape_attr_name
        name = shape_attr_name(self.name, keep_layer=True)
        write_grid_shapefile(filename, self.model.dis.sr, {name: self.array})

    def set_fmtin(self, fmtin):
        self._format = ArrayFormat(self,fortran=fmtin)

    def get_value(self):
        return copy.deepcopy(self.__value)

    # overloads, tries to avoid creating arrays if possible
    def __add__(self, other):
        if self.vtype in [np.int, np.float32] and self.vtype == other.vtype:
            return self.__value + other.get_value()
        else:
            return self.array + other.array

    def __sub__(self, other):
        if self.vtype in [np.int, np.float32] and self.vtype == other.vtype:
            return self.__value - other.get_value()
        else:
            return self.array - other.array

    def __mul__(self, other):
        if np.isscalar(other):
            return Util2d(self.model, self.shape, self.dtype,
                          self.__value_built * other, self.name,
                          self.format.fortran, self.cnstnt, self.iprn,
                          self.ext_filename,
                          self.locat, self.format.binary)
        else:
            raise NotImplementedError(
                "Util2d.__mul__() not implemented for non-scalars")

    def __getitem__(self, k):
        if isinstance(k, int):
            if len(self.shape) == 1:
                return self.array[k]
            elif self.shape[0] == 1:
                return self.array[0,k]
            elif self.shape[1] == 1:
                return self.array[k,0]
            else:
                raise Exception("Util2d.__getitem__() error: an integer was passed, " +
                                "self.shape > 1 in both dimensions")
        else:
            if isinstance(k, tuple):
                if len(k) == 2:
                    return self.array[k[0], k[1]]
                if len(k) == 1:
                    return self.array[k]
            else:
                return self.array[(k,)]

    def __setitem__(self, k, value):
        """
        this one is dangerous because it resets __value
        """
        a = self.array
        a[k] = value
        a = a.astype(self.dtype)
        self.__value = a
        if self.__value_built is not None:
            self.__value_built = None

    def __setattr__(self, key, value):
        if key == "fmtin":
            self._format = ArrayFormat(self,fortran=value)
        elif key == "format":
            assert isinstance(value,ArrayFormat)
            self._format = value
        elif key == "how":
            value = value.lower()
            assert value in self._acceptable_hows
            self._how = value
        else:
            super(Util2d, self).__setattr__(key, value)

    def all(self):
        return self.array.all()

    def __len__(self):
        return self.shape[0]

    def sum(self):
        return self.array.sum()

    @property
    def format(self):
        # don't return a copy because we want to allow
        # access to the attributes of ArrayFormat
        return self._format

    @property
    def how(self):
        return copy.copy(self._how)

    @property
    def vtype(self):
        return type(self.__value)

    @property
    def python_file_path(self):
        """
        where python is going to write the file
        Returns
        -------
            file_path (str) : path relative to python: includes model_ws
        """
        #if self.vtype != str:
        #    raise Exception("Util2d call to python_file_path " +
        #                    "for vtype != str")
        python_file_path = ''
        if self.model.model_ws != '.':
            python_file_path = os.path.join(self.model.model_ws)
        if self.model.external_path is not None:
            python_file_path = os.path.join(python_file_path,
                                           self.model.external_path)
        python_file_path = os.path.join(python_file_path,
                                       self.filename)
        return python_file_path

    @property
    def filename(self):
        if self.vtype != str:
            if self.ext_filename is not None:
                filename = os.path.split(self.ext_filename)[-1]
            else:
                filename = os.path.split(self._ext_filename)[-1]
        else:
            filename = os.path.split(self.__value)[-1]
        return filename

    @property
    def model_file_path(self):
        """
        where the model expects the file to be

        Returns
        -------
            file_path (str): path relative to the name file

        """

        model_file_path = ''
        if self.model.external_path is not None:
            model_file_path = os.path.join(model_file_path,
                                           self.model.external_path)
        model_file_path = os.path.join(model_file_path, self.filename)
        return model_file_path

    def get_constant_cr(self,value):

        if self.model.free_format:
            lay_space = '{0:>27s}'.format('')
            if self.vtype in [int,np.int]:
                lay_space = '{0:>32s}'.format('')
            cr = 'CONSTANT ' + self.format.py[1].format(value)
            cr = '{0:s}{1:s}#{2:<30s}\n'.format(cr, lay_space,
                                                self.name)
        else:
            cr = self._get_fixed_cr(0)
        return cr

    def _get_fixed_cr(self,locat):
        if self.dtype == np.int:
            cr = '{0:>10.0f}{1:>10.0f}{2:>20s}{3:>10.0f} #{4}\n' \
                .format(locat, self.cnstnt, self.format.fortran,
                        self.iprn, self.name)
        elif self.dtype == np.float32:
            cr = '{0:>10.0f}{1:>10.5G}{2:>20s}{3:>10.0f} #{4}\n' \
                .format(locat, self.cnstnt, self.format.fortran,
                        self.iprn, self.name)
        else:
            raise Exception('Util2d: error generating fixed-format ' +
                            ' control record, dtype must be np.int or np.float32')
        return cr

    def get_internal_cr(self):
        if self.model.free_format:
            cr = 'INTERNAL {0:15.6G} {1:>10s} {2:2.0f} #{3:<30s}\n' \
                 .format(self.cnstnt, self.format.fortran, self.iprn, self.name)
            return cr
        else:
            return self._get_fixed_cr(self.locat)

    def get_openclose_cr(self):
        cr = 'OPEN/CLOSE  {0:>30s} {1:15.6G} {2:>10s} {3:2.0f} {4:<30s}\n'.format(
                    self.model_file_path, self.cnstnt,
                    self.format.fortran, self.iprn,
                    self.name)
        return cr

    def get_external_cr(self):
        locat = self.model.next_ext_unit()
        if self.format.binary:
            locat = -1 * np.abs(locat)
        self.model.add_external(self.model_file_path,locat,self.format.binary)
        if self.model.free_format:
            cr = 'EXTERNAL  {0:>30d} {1:15.6G} {2:>10s} {3:2.0f} {4:<30s}\n'.format(
                locat, self.cnstnt,
                self.format.fortran, self.iprn,
                self.name)
            return cr
        else:
            return self._get_fixed_cr(locat)

    def get_file_entry(self,how=None):

        if how is not None:
            how = how.lower()
        else:
            how = self._how

        if self.format.binary and how in ["constant","internal"]:
            print("Util2d:{0} warning: ".format(self.name) +\
                  "resetting 'how' to external since format is binary")
            if self.model.free_format:
                how = "openclose"
            else:
                how = "external"
        if how == "internal":
            assert not self.format.binary,"Util2d error: 'how' is internal, but" +\
                                          "format is binary"
            cr = self.get_internal_cr()
            return cr + self.string

        elif how == "external" or how == "openclose":
            if how == "openclose":
                assert self.model.free_format,"Util2d error: 'how' is openclose," +\
                                              "but model doesn't support free fmt"

            # write a file if needed
            if self.vtype != str:
                if self.format.binary:
                    self.write_bin(self.shape,self.python_file_path,self._array,
                                   bintype="head")
                else:
                    self.write_txt(self.shape, self.python_file_path,
                                   self._array,fortran_format=self.format.fortran)

            elif self.__value != self.python_file_path:
                if os.path.exists(self.python_file_path):
                    # if the file already exists, remove it
                    if self.model.verbose:
                        print("Util2d warning: removing existing array " +
                              "file {0}".format(self.model_file_path))
                    try:
                        os.remove(self.python_file_path)
                    except Exception as e:
                        raise Exception("Util2d: error removing existing file " +\
                                        self.python_file_path)
                # copy the file to the new model location
                try:
                    shutil.copy2(self.__value,self.python_file_path)
                except Exception as e:
                    raise Exception("Util2d.get_file_array(): error copying " +
                                    "{0} to {1}:{2}".format(self.__value,
                                                            self.python_file_path,
                                                            str(e)))
            if how == "external":
                return self.get_external_cr()
            else:
                return self.get_openclose_cr()

        elif how == "constant":
            if self.vtype not in [int,np.float32]:
                u = np.unique(self._array)
                assert u.shape[0] == 1,"Util2d error: 'how' is constant, but array " +\
                                       "is not uniform"
                value = u[0]
            else:
                value = self.__value
            return self.get_constant_cr(value)

        else:
            raise Exception("Util2d.get_file_entry() error: " +\
                            "unrecognized 'how':{0}".format(how))

    @property
    def string(self):
        """
        get the string representation of value attribute

        Note:
            the string representation DOES NOT include the effects of the control
            record multiplier - this method is used primarily for writing model input files

        """
        # convert array to sting with specified format
        a_string = self.array2string(self.shape, self._array,
                                     python_format=self.format.py)
        return a_string

    @property
    def array(self):
        """
        Get the COPY of array representation of value attribute with the
        effects of the control record multiplier applied.

        Returns
        -------
        array : numpy.ndarray
            Copy of the array with the multiplier applied.

        Note
        ----
            .array is a COPY of the array representation as seen by the
            model - with the effects of the control record multiplier applied.

        """
        if self.cnstnt == 0.0:
            cnstnt = 1.0
        else:
            cnstnt = self.cnstnt
        # return a copy of self._array since it is being
        # multiplied
        return (self._array * cnstnt).astype(self.dtype)

    @property
    def _array(self):
        """
        get the array representation of value attribute
        if value is a string or a constant, the array is loaded/built only once

        Note:
            the return array representation DOES NOT include the effect of the multiplier
            in the control record.  To get the array as the model sees it (with the multiplier applied),
            use the Util2d.array method.
        """
        if self.vtype == str:
            if self.__value_built is None:
                file_in = open(self.__value, 'r')
                self.__value_built = \
                    Util2d.load_txt(self.shape, file_in, self.dtype,
                                     self.format.fortran).astype(self.dtype)
                file_in.close()
            return self.__value_built
        elif self.vtype != np.ndarray:
            if self.__value_built is None:
                self.__value_built = np.ones(self.shape, dtype=self.dtype) \
                                     * self.__value
            return self.__value_built
        else:
            return self.__value

    @staticmethod
    def load_txt(shape, file_in, dtype, fmtin):
        """
        load a (possibly wrapped format) array from a file
        (self.__value) and casts to the proper type (self.dtype)
        made static to support the load functionality 
        this routine now supports fixed format arrays where the numbers
        may touch.
        """
        # file_in = open(self.__value,'r')
        # file_in = open(filename,'r')
        # nrow,ncol = self.shape
        nrow, ncol = shape
        npl, fmt, width, decimal = ArrayFormat.decode_fortran_descriptor(fmtin)
        data = np.zeros((nrow * ncol), dtype=dtype) + np.NaN
        d = 0
        if not hasattr(file_in, 'read'):
            file_in = open(file_in, 'r')
        while True:
            line = file_in.readline()
            if line in [None, ''] or d == nrow * ncol:
                break
            if npl == 'free':
                raw = line.strip('\n').split()
            else:
                # split line using number of values in the line
                rawlist = []
                istart = 0
                istop = width
                for i in range(npl):
                    txtval = line[istart:istop]
                    if txtval.strip() != '':
                        rawlist.append(txtval)
                    else:
                        break
                    istart = istop
                    istop += width
                raw = rawlist

            for a in raw:
                try:
                    data[d] = dtype(a)
                except:
                    raise Exception('Util2d:unable to cast value: ' +
                                    str(a) + ' to type:' + str(dtype))
                if d == (nrow * ncol) - 1:
                    assert len(data) == (nrow * ncol)
                    data.resize(nrow, ncol)
                    return data
                d += 1
                #        file_in.close()
        if np.isnan(np.sum(data)):
            raise Exception("Util2d.load_txt() error: np.NaN in data array")
        data.resize(nrow, ncol)
        return data

    @staticmethod
    def write_txt(shape, file_out, data, fortran_format="(FREE)",
                  python_format=None):
        if fortran_format.upper() == '(FREE)' and python_format is None:
            np.savetxt(file_out, data,
                       ArrayFormat.get_default_numpy_fmt(data.dtype),
                       delimiter='')
            return
        if not hasattr(file_out,"write"):
            file_out = open(file_out,'w')
        file_out.write(Util2d.array2string(shape,data,fortran_format=fortran_format,
                                           python_format=python_format))

    @staticmethod
    def array2string(shape, data, fortran_format="(FREE)",
                     python_format=None):
        """
        return a string representation of
        a (possibly wrapped format) array from a file
        (self.__value) and casts to the proper type (self.dtype)
        made static to support the load functionality
        this routine now supports fixed format arrays where the numbers
        may touch.
        """
        if len(shape) == 2:
            nrow, ncol = shape
        else:
            nrow = 1
            ncol = shape[0]
        data = np.atleast_2d(data)
        if python_format is None:
            column_length, fmt, width, decimal = \
                ArrayFormat.decode_fortran_descriptor(fortran_format)
            output_fmt = '{0}0:{1}.{2}{3}{4}'.format('{', width, decimal, fmt,
                                                     '}')
        else:
            try:
                column_length, output_fmt = int(python_format[0]), \
                                            python_format[1]
            except:
                raise Exception('Util2d.write_txt: \nunable to parse'
                                + 'python_format:\n    {0}\n'.
                                format(python_format)
                                + '  python_format should be a list with\n'
                                + '   [column_length, fmt]\n'
                                + '    e.g., [10, {0:10.2e}]')
        if ncol % column_length == 0:
            linereturnflag = False
        else:
            linereturnflag = True
        # write the array to a string
        s = ""
        for i in range(nrow):
            icol = 0
            for j in range(ncol):
                try:
                    s = s + output_fmt.format(data[i, j])
                except Exception as e:
                    raise Exception("error writing array value" + \
                     "{0} at r,c [{1},{2}]\n{3}".format(data[i, j], i, j, str(e)))
                if (j + 1) % column_length == 0.0 and (j != 0 or ncol == 1):
                    s += '\n'
            if linereturnflag:
                s += '\n'
        return s

    @staticmethod
    def load_bin(shape, file_in, dtype, bintype=None):
        import flopy.utils.binaryfile as bf
        nrow, ncol = shape
        if bintype is not None:
            if dtype not in [np.int]:
                header_dtype = bf.BinaryHeader.set_dtype(bintype=bintype)
            header_data = np.fromfile(file_in, dtype=header_dtype, count=1)
        else:
            header_data = None
        data = np.fromfile(file_in, dtype=dtype, count=nrow * ncol)
        data.resize(nrow, ncol)
        return [header_data, data]

    @staticmethod
    def write_bin(shape, file_out, data, bintype=None, header_data=None):
        if not hasattr(file_out,'write'):
            file_out = open(file_out,'wb')
        dtype = data.dtype
        if dtype.kind != 'i':
            if bintype is not None:
                if header_data is None:
                    header_data = BinaryHeader.create(bintype=bintype,nrow=shape[0],
                                                      ncol=shape[1])
            if header_data is not None:
                header_data.tofile(file_out)
        data.tofile(file_out)
        return

    def parse_value(self, value):
        """
        parses and casts the raw value into an acceptable format for __value
        lot of defense here, so we can make assumptions later
        """
        if isinstance(value, list):
            value = np.array(value)

        if isinstance(value, bool):
            if self.dtype == np.bool:
                try:
                    self.__value = np.bool(value)

                except:
                    raise Exception('Util2d:could not cast ' +
                                    'boolean value to type "np.bool": ' +
                                    str(value))
            else:
                raise Exception('Util2d:value type is bool, ' +
                                ' but dtype not set as np.bool')
        elif isinstance(value, str):
            if os.path.exists(value):
                self.__value = value
                return
            elif self.dtype == np.int:
                try:
                    self.__value = int(value)
                except:
                    raise Exception("Util2d error: str not a file and " +
                                    "couldn't be cast to int: {0}".format(value))

            else:
                try:
                    self.__value = float(value)
                except:
                    raise Exception("Util2d error: str not a file and " +
                                    "couldn't be cast to float: {0}".format(value))

        elif np.isscalar(value):
            if self.dtype == np.int:
                try:
                    self.__value = np.int(value)
                except:
                    raise Exception('Util2d:could not cast scalar ' +
                                    'value to type "int": ' + str(value))
            elif self.dtype == np.float32:
                try:
                    self.__value = np.float32(value)
                except:
                    raise Exception('Util2d:could not cast ' +
                                    'scalar value to type "float": ' +
                                    str(value))

        elif isinstance(value, np.ndarray):
            # if value is 3d, but dimension 1 is only length 1,
            # then drop the first dimension
            if len(value.shape) == 3 and value.shape[0] == 1:
                value = value[0]
            if self.shape != value.shape:
                raise Exception('Util2d:self.shape: ' + str(self.shape) +
                                ' does not match value.shape: ' +
                                str(value.shape))
            if self.dtype != value.dtype:
                value = value.astype(self.dtype)
            self.__value = value

        else:
            raise Exception('Util2d:unsupported type in util_array: ' +
                            str(type(value)))

    @staticmethod
    def load(f_handle, model, shape, dtype, name, ext_unit_dict=None):
        """
        functionality to load Util2d instance from an existing
        model input file.
        external and internal record types must be fully loaded
        if you are using fixed format record types,make sure 
        ext_unit_dict has been initialized from the NAM file
        """

        curr_unit = None
        if ext_unit_dict is not None:
            # determine the current file's unit number
            cfile = f_handle.name
            for cunit in ext_unit_dict:
                if cfile == ext_unit_dict[cunit].filename:
                    curr_unit = cunit
                    break

        # Allows for special MT3D array reader
        array_format = None
        if hasattr(model, 'array_format'):
            array_format = model.array_format

        cr_dict = Util2d.parse_control_record(f_handle.readline(),
                                              current_unit=curr_unit,
                                              dtype=dtype,
                                              ext_unit_dict=ext_unit_dict,
                                              array_format=array_format)

        if cr_dict['type'] == 'constant':
            u2d = Util2d(model, shape, dtype, cr_dict['cnstnt'], name=name,
                          iprn=cr_dict['iprn'], fmtin=cr_dict['fmtin'])

        elif cr_dict['type'] == 'open/close':
            # clean up the filename a little
            fname = cr_dict['fname']
            fname = fname.replace("'", "")
            fname = fname.replace('"', '')
            fname = fname.replace('\'', '')
            fname = fname.replace('\"', '')
            fname = fname.replace('\\', os.path.sep)
            fname = os.path.join(model.model_ws, fname)
            # load_txt(shape, file_in, dtype, fmtin):
            assert os.path.exists(fname), "Util2d.load() error: open/close " + \
                                          "file " + str(fname) + " not found"
            if str('binary') not in str(cr_dict['fmtin'].lower()):
                f = open(fname, 'r')
                data = Util2d.load_txt(shape=shape,
                                       file_in=f,
                                       dtype=dtype, fmtin=cr_dict['fmtin'])
            else:
                f = open(fname, 'rb')
                header_data, data = Util2d.load_bin(shape, f, dtype,
                                                    bintype='Head')
            f.close()
            u2d = Util2d(model, shape, dtype, data, name=name,
                         iprn=cr_dict['iprn'], fmtin=cr_dict['fmtin'],
                         cnstnt=cr_dict['cnstnt'])


        elif cr_dict['type'] == 'internal':
            data = Util2d.load_txt(shape, f_handle, dtype, cr_dict['fmtin'])
            u2d = Util2d(model, shape, dtype, data, name=name,
                         iprn=cr_dict['iprn'], fmtin=cr_dict['fmtin'],
                         cnstnt=cr_dict['cnstnt'])

        elif cr_dict['type'] == 'external':


            if str('binary') not in str(cr_dict['fmtin'].lower()):
                assert cr_dict['nunit'] in list(ext_unit_dict.keys())
                data = Util2d.load_txt(shape,
                                       ext_unit_dict[
                                       cr_dict['nunit']].filehandle,
                                       dtype, cr_dict['fmtin'])
            else:
                if cr_dict['nunit'] not in list(ext_unit_dict.keys()):
                    cr_dict["nunit"] *= -1
                assert cr_dict['nunit'] in list(ext_unit_dict.keys())
                header_data, data = Util2d.load_bin(
                    shape, ext_unit_dict[cr_dict['nunit']].filehandle, dtype,
                    bintype='Head')
            u2d = Util2d(model, shape, dtype, data, name=name,
                         iprn=cr_dict['iprn'], fmtin=cr_dict['fmtin'],
                         cnstnt=cr_dict['cnstnt'])
            # track this unit number so we can remove it from the external
            # file list later
            model.pop_key_list.append(cr_dict['nunit'])
        return u2d

    @staticmethod
    def parse_control_record(line, current_unit=None, dtype=np.float32,
                             ext_unit_dict=None, array_format=None):
        """
        parses a control record when reading an existing file
        rectifies fixed to free format
        current_unit (optional) indicates the unit number of the file being parsed
        """
        free_fmt = ['open/close', 'internal', 'external', 'constant']
        raw = line.lower().strip().split()
        freefmt, cnstnt, fmtin, iprn, nunit = None, None, None, -1, None
        fname = None
        isfloat = False
        if dtype == np.float or dtype == np.float32:
            isfloat = True
            # if free format keywords
        if str(raw[0]) in str(free_fmt):
            freefmt = raw[0]
            if raw[0] == 'constant':
                if isfloat:
                    cnstnt = np.float(raw[1].lower().replace('d', 'e'))
                else:
                    cnstnt = np.int(raw[1].lower())
            if raw[0] == 'internal':
                if isfloat:
                    cnstnt = np.float(raw[1].lower().replace('d', 'e'))
                else:
                    cnstnt = np.int(raw[1].lower())
                fmtin = raw[2].strip()
                iprn = int(raw[3])
            elif raw[0] == 'external':
                if ext_unit_dict is not None:
                    try:
                        # td = ext_unit_dict[int(raw[1])]
                        fname = ext_unit_dict[int(raw[1])].filename.strip()
                    except:
                        pass
                nunit = int(raw[1])
                if isfloat:
                    cnstnt = np.float(raw[2].lower().replace('d', 'e'))
                else:
                    cnstnt = np.int(raw[2].lower())
                fmtin = raw[3].strip()
                iprn = int(raw[4])
            elif raw[0] == 'open/close':
                fname = raw[1].strip()
                if isfloat:
                    cnstnt = np.float(raw[2].lower().replace('d', 'e'))
                else:
                    cnstnt = np.int(raw[2].lower())
                fmtin = raw[3].strip()
                iprn = int(raw[4])
                npl, fmt, width, decimal = None, None, None, None
        else:
            locat = np.int(line[0:10].strip())
            if isfloat:
                cnstnt = np.float(
                    line[10:20].strip().lower().replace('d', 'e'))
            else:
                cnstnt = np.int(line[10:20].strip())
                if cnstnt == 0:
                    cnstnt = 1
            if locat != 0:
                fmtin = line[20:40].strip()
                try:
                    iprn = np.int(line[40:50].strip())
                except:
                    iprn = 0
            # locat = int(raw[0])
            # cnstnt = float(raw[1])
            # fmtin = raw[2].strip()
            # iprn = int(raw[3])
            if locat == 0:
                freefmt = 'constant'
            elif locat < 0:
                freefmt = 'external'
                nunit = np.int(locat) * -1
                fmtin = '(binary)'
            elif locat > 0:
                # if the unit number matches the current file, it's internal
                if locat == current_unit:
                    freefmt = 'internal'
                else:
                    freefmt = 'external'
                nunit = np.int(locat)

            # Reset for special MT3D control flags
            if array_format == 'mt3d':
                if locat == 100:
                    freefmt = 'internal'
                    nunit = current_unit
                elif locat == 101:
                    raise NotImplementedError(
                        'MT3D block format not supported...')
                elif locat == 102:
                    raise NotImplementedError(
                        'MT3D zonal format not supported...')
                elif locat == 103:
                    freefmt = 'internal'
                    nunit = current_unit
                    fmtin = '(free)'

        cr_dict = {}
        cr_dict['type'] = freefmt
        cr_dict['cnstnt'] = cnstnt
        cr_dict['nunit'] = nunit
        cr_dict['iprn'] = iprn
        cr_dict['fmtin'] = fmtin
        cr_dict['fname'] = fname
        return cr_dict


