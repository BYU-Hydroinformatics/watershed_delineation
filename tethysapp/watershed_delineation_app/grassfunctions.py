import os
import sys
import subprocess
import tempfile
from tempfile import mkstemp

# Apache should have ownership and full permission over this path
DEM_FULL_PATH = "/home/sherry/DEM/utah3857.tif"
DEM_NAME = 'utah3857' # DEM layer name, no extension (no .tif)
DRAINAGE_FULL_PATH = "/home/sherry/DEM/utah3857_drain.tif"
DRAINAGE_NAME = 'utah3857_drain'
STREAMS_FULL_PATH = "/home/sherry/DEM/utah3857_streams.tif"
STREAMS_NAME = 'utah3857_streams'
GISBASE = "/usr/lib/grass72" # full path to GRASS installation
GRASS7BIN = "grass" # command to start GRASS from shell
GISDB = os.path.join(tempfile.gettempdir(), 'grassdata')
OUTPUT_DATA_PATH = os.path.join(tempfile.gettempdir(), 'grassdata', "output_data")


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
            outlet = (xlon, ylat)

        # Define region
        stats = gscript.parse_command('g.region', raster=dem, flags='p')


        # Flow accumulation analysis
        if not os.path.exists(drainage_mapset_path):
            stats = gscript.read_command('r.watershed', elevation=dem, threshold='10000', drainage=drainage,
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

        # output watershed to GeoJSON
        geojson_f_name = "{0}.GEOJSON".format(basin)
        basin_GEOJSON = os.path.join(output_data_path, geojson_f_name)
        stats = gscript.parse_command('v.out.ogr', input=basin_all_0_vect, output=basin_GEOJSON, \
                                      format="GeoJSON", type="area", overwrite=True, flags="c")

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