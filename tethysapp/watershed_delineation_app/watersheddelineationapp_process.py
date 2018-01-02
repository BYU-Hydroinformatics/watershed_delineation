import os
import binascii
from pywps import Process, LiteralInput, ComplexInput, ComplexOutput, Format, FORMATS
from tethys_apps.tethysapp.watershed_delineation_app.grassfunctions import WD

class watersheddelineationprocess(Process):
    def __init__(self):
        # init process
        inputs = [LiteralInput('outlet_x', 'Outlet Longitude', data_type='float'),
                  LiteralInput('outlet_y', 'Outlet Latitude', data_type='float')]
        outputs = [ComplexOutput('watershed', 'Delineated Watershed', supported_formats=[Format('application/gml+xml')]),
                   ComplexOutput('snappoint', 'Snapped outlet point', supported_formats=[Format('application/gml+xml')])]

        super(watersheddelineationprocess, self).__init__(
            self._handler,
            identifier='watersheddelineationprocess', # must be same, as filename
            version='1.0',
            title="Watershed delineation process",
            abstract='This process provides watershed delineation function using GRASS within DR country area',
            profile='',
            inputs=inputs,
            outputs=outputs,
            store_supported=True,
            status_supported=True
        )


    def _handler(self, request, response):


        #get input values
        xlon = request.inputs['outlet_x'][0].data
        ylat = request.inputs['outlet_y'][0].data
        prj = "native"
        string_length = 4
        jobid = binascii.hexlify(os.urandom(string_length))

        # Run WD()
        # basin_GEOJSON, msg = WD(jobid, xlon, ylat, prj)
        WD_dict = WD(jobid, xlon, ylat, prj)

        basin_GEOJSON = WD_dict["basin_GEOJSON"]
        outlet_snapped_GEOJSON = WD_dict["outlet_snapped_geojson"]

        print basin_GEOJSON

        response.outputs['watershed'].output_format = FORMATS.GML
        response.outputs['watershed'].file = basin_GEOJSON
        response.outputs['snappoint'].output_format = FORMATS.GML
        response.outputs['snappoint'].file = outlet_snapped_GEOJSON

        print response.outputs['watershed'].file

        return response

