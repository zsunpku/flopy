import numpy as np
from ..pakbase import Package


class ModflowPbc(Package):
    """
    Periodic boundary condition class

    """

    def __init__(self, model, layer_row_column_data=None,
                 layer_row_column_shead_ehead=None,
                 cosines=None, extension='pbc', unitnumber=None, zerobase=True):
        # set default unit number of one is not specified
        if unitnumber is None:
            unitnumber = ModflowPbc.defaultunit()

        # Call ancestor's init to set self.parent, extension, name and unit number
        Package.__init__(self, model, extension, ModflowPbc.ftype(),
                         unitnumber)
        self.heading = '# PBC for MODFLOW, generated by Flopy.'
        self.mxactp = 0
        if layer_row_column_data is None:
            if layer_row_column_shead_ehead is not None:
                print('\nWARNING: ModflowPbc - Do not use layer_row_column_shead_ehead!\n' + \
                      '                      Use layer_row_column_data instead.')
                layer_row_column_data = layer_row_column_shead_ehead
            else:
                raise Exception('Failed to specify layer_row_column_shead_ehead or layer_row_column_data.')

        self.mxactp, self.layer_row_column_data = self.assign_layer_row_column_data(layer_row_column_data, 5,
                                                                                    zerobase=zerobase)
        self.mxcos, self.cosines = self.assign_layer_row_column_data(cosines, 3,
                                                                     zerobase=False)  # misuse of this function - zerobase needs to be False
        '''self.mxcos = 0
        if (cosines != None):
            error_message = 'cosines must have 3 columns'
            if (not isinstance(cosines, list)):
                cosines = [cosines]
            for a in cosines:
                a = np.atleast_2d(a)
                nr, nc = a.shape
                assert nc == 3, error_message
                if (nr > self.mxcos):
                    self.mxcos = nr
            self.cosines = cosines'''
        self.np = 0
        self.parent.add_package(self)

    def ncells(self):
        # Returns the  maximum number of cells that have recharge (developped for MT3DMS SSM package)
        return self.mxactp

    def write_file(self):
        """
        Write the package file.

        Returns
        -------
        None

        """
        f_pbc = open(self.fn_path, 'w')
        f_pbc.write('%s\n' % self.heading)
        f_pbc.write('%10i%10i\n' % (self.mxactp, self.mxcos))
        for n in range(self.parent.get_package('DIS').nper):
            if (n < len(self.layer_row_column_data)):
                a = self.layer_row_column_data[n]
                itmp = a.shape[0]
            else:
                itmp = -1
            if (n < len(self.cosines)):
                c = self.cosines[n]
                ctmp = c.shape[0]
            else:
                ctmp = -1
            f_pbc.write('%10i%10i%10i\n' % (itmp, ctmp, self.np))
            if (n < len(self.layer_row_column_data)):
                for b in a:
                    f_pbc.write('%10i%10i%10i%10f%10f\n' % (b[0], b[1], b[2], b[3], b[4]))
            if (n < len(self.cosines)):
                for d in c:
                    f_pbc.write('%10f%10f%10f\n' % (d[0], d[1], d[2]))
        f_pbc.close()



    @staticmethod
    def ftype():
        return 'PBC'


    @staticmethod
    def defaultunit():
        return 30
