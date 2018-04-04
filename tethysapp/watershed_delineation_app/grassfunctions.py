import os
import sys
import subprocess
import tempfile
from tempfile import mkstemp
import geojson

# Apache should have ownership and full permission over this path
DEM_FULL_PATH = "/home/sherry/DR/dr3857.tif"
DEM_NAME = 'dr3857' # DEM layer name, no extension (no .tif)
DRAINAGE_FULL_PATH = "/home/sherry/DR/dr3857_drain.tif"
DRAINAGE_NAME = 'dr3857_drain'
STREAMS_FULL_PATH = "/home/sherry/DR/dr3857_streams10k.tif"
STREAMS_NAME = 'dr3857_streams10k'
GISBASE = "/usr/lib/grass74" # full path to GRASS installation
GRASS7BIN = "grass" # command to start GRASS from shell
GISDB = os.path.join(tempfile.gettempdir(), 'grassdata')
OUTPUT_DATA_PATH = os.path.join(tempfile.gettempdir(), 'grassdata', "output_data")
os.environ["HOME"] = "/tmp"

def WD(jobid, xlon, ylat, prj):

    dem_full_path = DEM_FULL_PATH
    dem = DEM_NAME
    drainage_full_path = DRAINAGE_FULL_PATH
    drainage = DRAINAGE_NAME
    streams_full_path = STREAMS_FULL_PATH
    streams = STREAMS_NAME
    gisbase = GISBASE
    grass7bin = GRASS7BIN

    # Define grass data folder, location, mapset
    gisdb = GISDB
    if not os.path.exists(gisdb):
        os.mkdir(gisdb)
    location = "location_wd_{0}".format(dem)
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

        # Set GISBASE environment variable
        os.environ['GISBASE'] = gisbase
        # the following not needed with trunk
        os.environ['PATH'] += os.pathsep + os.path.join(gisbase, 'bin')
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

        # import streams
        streams_mapset_path = os.path.join(gisdb, location, mapset, "cell", streams)
        if not os.path.exists(streams_mapset_path):
            stats = gscript.read_command('r.in.gdal', flags='o', input=streams_full_path, output=streams)

        # Project xlon, ylat wgs84 into current
        if prj.lower() != "native" or prj.lower() == "wgs84":

            stats = gscript.read_command('m.proj', coordinates=(xlon, ylat), flags='i')
            coor_list = stats.split("|")
            xlon = float(coor_list[0])
            ylat = float(coor_list[1])

        # Define region
        stats = gscript.parse_command('g.region', raster=dem, flags='p')

        # Read extent of the dem file
        for key in stats:
            if "north:" in key:
                north = float(key.split(":")[1])
            elif "south:" in key:
                south = float(key.split(":")[1])
            elif "west:" in key:
                west = float(key.split(":")[1])
            elif "east:" in key:
                east = float(key.split(":")[1])
            elif "nsres:" in key:
                nsres = float(key.split(":")[1])
            elif "ewres:" in key:
                ewres = float(key.split(":")[1])

        # check if xlon, ylat is within the extent of dem
        if xlon < west or xlon > east:
            raise Exception("(xlon, ylat) is out of dem region.")
        elif ylat < south or ylat > north:
            raise Exception("(xlon, ylat) is out of dem region.")

        # Flow accumulation analysis
        if not os.path.exists(drainage_mapset_path):
            # Define region
            stats = gscript.parse_command('g.region', raster=dem, flags='p')
            stats = gscript.read_command('r.watershed', elevation=dem, threshold='50000', drainage=drainage,
                                         flags='s', overwrite=True)

        # change outlet coordinates to a shape file
        fd, outlet_txt_path = mkstemp()
        os.write(fd, "{0} | {1}".format(xlon, ylat))
        os.close(fd)
        outlet_vect = "{0}_outletvect_{1}".format(dem, jobid)
        stats = gscript.read_command('v.in.ascii', input=outlet_txt_path, output=outlet_vect, overwrite=True)

        # Point snap
        # r.stream.snap is addon extension installed with "g.extension extension=r.stream.snap" in grass console
        # default installation path is /home/sherry/.grass7/addons/bin/r.stream.snap
        # have to copy to /usr/lib/grass72/bin/r.stream.snap to make it work
        # must define region to streams here
        stats = gscript.parse_command('g.region', raster=streams, flags='p')
        outlet_snapped_vect = "{0}_outletsnap_{1}".format(dem, jobid)
        stats = gscript.read_command('r.stream.snap', input=outlet_vect, output=outlet_snapped_vect, stream_rast=streams, radius=1000, overwrite=True)

        #read snapped outlet coordinates
        #outlet_snapped_coords = "{0}_outletsnap_{1}".format(dem, jobid)
        # v.out.ascii
        stats = gscript.read_command("v.out.ascii", input=outlet_snapped_vect)
        xlon_snapped = float(stats.split('|')[0])
        ylat_snapped = float(stats.split('|')[1])
        outlet_snapped_coords = (xlon_snapped, ylat_snapped)
        print(outlet_snapped_coords)

        #output snap outlet to GeoJSON
        outlet_snapped_geojson_name = "{0}.GEOJSON".format(outlet_snapped_vect)
        outlet_snapped_GEOJSON = os.path.join(output_data_path, outlet_snapped_geojson_name)
        stats = gscript.parse_command('v.out.ogr', input=outlet_snapped_vect, output=outlet_snapped_GEOJSON, \
                                      format="GeoJSON", type="point", overwrite=True, flags="c")

        # Delineate watershed
        basin = "{0}_basin_{1}".format(dem, jobid)
        stats = gscript.read_command('r.water.outlet', input=drainage, output=basin, coordinates=outlet_snapped_coords,
                                     overwrite=True)

        # output lake
        basin_all_0 = "{0}_all_0".format(basin)
        mapcalc_cmd = '{0} = if({1}, 0)'.format(basin_all_0, basin)
        gscript.mapcalc(mapcalc_cmd, overwrite=True, quiet=True)

        # covert raster lake_rast_all_0 into vector
        basin_all_0_vect = "{0}_all_0_vect".format(basin)
        stats = gscript.parse_command('r.to.vect', input=basin_all_0, output=basin_all_0_vect, type="area",
                                      overwrite=True)
        # # method 1: remove small areas (hard to define thredhold)
        # # v.clean input=basin_1vec@test1 output=clean_basin_1 tool=rmarea threshold=10000
        # basin_all_0_clean = "{0}_all_0_clean".format(basin)
        # stats = gscript.parse_command('v.clean', input=basin_all_0_vect, output=basin_all_0_clean, tool='rmarea', threshold = '50000',
        #                               overwrite=True)

        # method 2: list area of each area, extract biggest one (may remove snap point)
        # stats = gscript.parse_command('v.db.addcolumn', map=basin_all_0_vect, columns="area_polygon DOUBLE PRECISION")
        # stats = gscript.parse_command('v.to.db', map=basin_all_0_vect, option="area", columns="area_polygon")
        # stats = gscript.read_command('db.select', sql="SELECT cat FROM {0} where area_polygon = (SELECT MAX(area_polygon) from {1})".format(basin_all_0_vect,basin_all_0_vect))
        # cat_max = int(stats.split("\n")[1])
        # basin_all_0_max = "{0}_all_0_max".format(basin)
        # stats = gscript.parse_command('v.extract', cats="{0}".format(str(cat_max)), input=basin_all_0_vect, output=basin_all_0_max,overwrite=True)

        # method 3: buffer
        # v.buffer input = drain_A1vect output = drain_A1buf01 distance = 0.1 --overwrite
        final_polygon_vect_name = basin_all_0_vect

        stats = gscript.read_command('db.select', sql="SELECT COUNT(*) FROM {0}".format(basin_all_0_vect))
        count_num =int(stats.split("\n")[1])
        if count_num > 1:
            print("***************run buffer*********")
            basin_all_0_buf = "{0}_all_0_buf".format(basin)
            stats = gscript.parse_command('v.buffer', input=basin_all_0_vect, output=basin_all_0_buf, distance="0.1", overwrite=True)
            stats = gscript.parse_command('v.db.addtable', map=basin_all_0_buf, columns="area_polygon DOUBLE PRECISION")

            stats = gscript.read_command('db.select', sql="SELECT COUNT(*) FROM {0}".format(basin_all_0_buf))
            count_num_bufferred = int(stats.split("\n")[1])
            print("After buffer count: {0}".format(str(count_num_bufferred)))
            if count_num_bufferred == 0:
                raise Exception("Buffered polygon count = 0")
            if count_num_bufferred > 1:
                raise Exception("Buffered polygon count > 1")

            final_polygon_vect_name = basin_all_0_buf

        # output watershed to GeoJSON
        geojson_f_name = "{0}.GEOJSON".format(basin)
        basin_GEOJSON = os.path.join(output_data_path, geojson_f_name)
        stats = gscript.parse_command('v.out.ogr', input=final_polygon_vect_name, output=basin_GEOJSON, \
                                      format="GeoJSON", type="area", overwrite=True, flags="c")

        # check and make sure the geojson file only contain one feature.
        # If the watershed have holes, the holes will be written as standalone features in the geojson file and cause error in reservoir calculation app
        f_geojson = open(basin_GEOJSON)
        geojson_obj = geojson.load(f_geojson)
        print("*****************searching hole*********************")
        if len(geojson_obj.features) > 1:
            print("*****************found hole*********************")
            for fea in geojson_obj.features:
                if len(fea.properties.keys()) > 0:
                    geojson_f_name_new = "{0}_new.GEOJSON".format(basin)
                    basin_GEOJSON_new = os.path.join(output_data_path, geojson_f_name_new)
                    f_out = open(basin_GEOJSON_new, "w")
                    geojson.dump(fea, f_out)
                    f_out.flush()
                    basin_GEOJSON = basin_GEOJSON_new
                    break

        return {"outlet_snapped_geojson":outlet_snapped_GEOJSON,
                "basin_GEOJSON":basin_GEOJSON,
                "msg":msg,
                "status":"success"}

    except Exception as e:

        msg = e.message
        return {"outlet_snapped_geojson": None,
                "basin_GEOJSON": None,
                "msg": msg,
                "status":"error"}
