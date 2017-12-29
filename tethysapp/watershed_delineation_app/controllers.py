import os
import sys
from datetime import datetime
import binascii
import subprocess
import tempfile
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from tethys_sdk.gizmos import Button, TextInput, SelectInput
from django.shortcuts import render

# Apache should have ownership and full permission over this path
DEM_FULL_PATH = "/home/sherry/dem/dr_srtm_30_3857.tif"
DEM_NAME = 'dr_srtm_30_3857' # DEM layer name, no extension (no .tif)
DRAINAGE_FULL_PATH = "/home/sherry/dem/dr_srtm_30_3857_drain.tif"
DRAINAGE_NAME = 'dr_srtm_30_3857_drain'
GISBASE = "/usr/lib/grass72" # full path to GRASS installation
GRASS7BIN = "grass" # command to start GRASS from shell
GISDB = os.path.join(tempfile.gettempdir(), 'grassdata')
OUTPUT_DATA_PATH = os.path.join(tempfile.gettempdir(), 'grassdata', "output_data")

@login_required()
def home(request):
    """
    Controller for the app home page.
    """
    print("AAAAAAAAAAAAAA")
    print(__file__)
    btnDelin = Button(display_text="Delinate Watershed",
                          name="btnDelin",
                          attributes="onclick=run_wd_service()",
                          submit=False)

    context = {
        'btnDelin':btnDelin
    }

    return render(request, 'watershed_delineation_app/home.html', context)

def run_wd(request):

    string_length = 4
    jobid = binascii.hexlify(os.urandom(string_length))
    time_start = datetime.now()
    status = "error"
    message = ""
    input_para = {}

    try:
        if request.GET:
            xlon = request.GET.get("xlon", None)
            ylat = request.GET.get("ylat", None)
            prj = request.GET.get("prj", None)

            input_para["xlon"] = xlon
            input_para["ylat"] = ylat
            input_para["prj"] = prj

            # Run SC()
            basin_GEOJSON, msg = WD(jobid, xlon, ylat, prj)

            #Check results
            if basin_GEOJSON is not None:
                message += msg
            else:
                message += msg
        else:
            raise Exception("Please call this service in a GET request.")

    except Exception as ex:
        message = ex.message

    # Return inputs and results
    finally:

        with open(basin_GEOJSON) as f:
            basin_data = json.load(f)

        return JsonResponse(basin_data)

def WD(jobid, xlon, ylat, prj):

        dem_full_path = DEM_FULL_PATH
        dem = DEM_NAME
        drainage_full_path = DRAINAGE_FULL_PATH
        drainage = DRAINAGE_NAME
        gisbase = GISBASE
        grass7bin = GRASS7BIN

        # Define grass data folder, location, mapset
        gisdb = os.path.join(tempfile.gettempdir(), 'grassdata')
        if not os.path.exists(gisdb):
            os.mkdir(gisdb)
        location = "location_{0}".format(dem)
        mapset = "PERMANENT"
        msg = ""

        output_data_path = OUTPUT_DATA_PATH
        if not os.path.exists(output_data_path):
            os.mkdir(output_data_path)

        try:
            # Create location
            location_path = os.path.join(gisdb, location)
            if not os.path.exists(location_path):
                startcmd = grass7bin + ' -c ' + dem_full_path + ' -e ' + location_path

                p = subprocess.Popen(startcmd, shell=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = p.communicate()
                if p.returncode != 0:
                    print >> sys.stderr, 'ERROR: %s' % err
                    print >> sys.stderr, 'ERROR: Cannot generate location (%s)' % startcmd
                    sys.exit(-1)

            xlon = float(xlon)
            ylat = float(ylat)
            outlet = (xlon, ylat)

            # Set GISBASE environment variable
            os.environ['GISBASE'] = gisbase
            # the following not needed with trunk
            os.environ['PATH'] += os.pathsep + os.path.join(gisbase, 'extrabin')
            # Set GISDBASE environment variable
            os.environ['GISDBASE'] = gisdb

            # define GRASS-Python environment
            gpydir = os.path.join(gisbase, "etc", "python")
            sys.path.append(gpydir)

            # import GRASS Python bindings (see also pygrass)
            import grass.script as gscript
            import grass.script.setup as gsetup
            gscript.core.set_raise_on_error(True)

            # launch session
            gsetup.init(gisbase, gisdb, location, mapset)

            # Check the dem file, import if not exist
            dem_mapset_path = os.path.join(gisdb, location, mapset, "cell", dem)

            if not os.path.exists(dem_mapset_path):
                stats = gscript.read_command('r.in.gdal', flags='o', input=dem_full_path, output=dem)

            # import drainage
            drainage_mapset_path = os.path.join(gisdb, location, mapset, "cell", drainage)
            if not os.path.exists(drainage_mapset_path):
                stats = gscript.read_command('r.in.gdal', flags='o', input=drainage_full_path, output=drainage)

            # Project xlon, ylat wgs84 into current
            if prj.lower() != "native" or prj.lower() == "wgs84":
                logging.info("\n ---------- Reproject xlon and ylat into native dem projection ------------- \n")
                stats = gscript.read_command('m.proj', coordinates=(xlon, ylat), flags='i')
                coor_list = stats.split("|")
                xlon = float(coor_list[0])
                ylat = float(coor_list[1])
                outlet = (xlon, ylat)

            # Define region
            stats = gscript.parse_command('g.region', raster=dem, flags='p')

            # Flow accumulation analysis
            if not os.path.exists(drainage_mapset_path):
                stats = gscript.read_command('r.watershed', elevation=dem, threshold='10000', drainage=drainage,
                                             flags='s', overwrite=True)

            # Delineate watershed
            basin = "{0}_basin_{1}".format(dem, jobid)
            stats = gscript.read_command('r.water.outlet', input=drainage, output=basin, coordinates=outlet,
                                         overwrite=True)

            # output lake
            basin_all_0 = "{0}_all_0".format(basin)
            mapcalc_cmd = '{0} = if({1}, 0)'.format(basin_all_0, basin)
            gscript.mapcalc(mapcalc_cmd, overwrite=True, quiet=True)

            # covert raster lake_rast_all_0 into vector
            basin_all_0_vect = "{0}_all_0_vect".format(basin)
            stats = gscript.parse_command('r.to.vect', input=basin_all_0, output=basin_all_0_vect, type="area",
                                          overwrite=True)

            # output GeoJSON
            geojson_f_name = "{0}.GEOJSON".format(basin)
            basin_GEOJSON = os.path.join(output_data_path, geojson_f_name)
            stats = gscript.parse_command('v.out.ogr', input=basin_all_0_vect, output=basin_GEOJSON, \
                                          format="GeoJSON", type="area", overwrite=True, flags="c")

            return basin_GEOJSON, msg

        except Exception as e:

            msg = e.message
            return None, msg
