import os
import binascii
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from tethys_sdk.gizmos import Button, TextInput, SelectInput
from django.shortcuts import render
from tethys_apps.tethysapp.watershed_delineation_app.grassfunctions import WD


@login_required()
def home(request):
    """
    Controller for the app home page.
    """
    btnDelin = Button(display_text="Delinate Watershed",
                          name="btnDelin",
                          attributes="onclick=run_wd_service()",
                          submit=False)

    context = {
        'btnDelin':btnDelin
    }

    return render(request, 'watershed_delineation_app/home.html', context)

@login_required()
def run_wd(request):

    string_length = 4
    jobid = binascii.hexlify(os.urandom(string_length))
    message = ""

    try:
        if request.GET:
            xlon = request.GET.get("xlon", None)
            ylat = request.GET.get("ylat", None)
            prj = request.GET.get("prj", None)

            # Run WD()
            #outletbasin_GEOJSON, msg = WD(jobid, xlon, ylat, prj)
            WD_dict= WD(jobid, xlon, ylat, prj)

            outlet_snapped_GEOJSON = WD_dict["outlet_snapped_geojson"]
            basin_GEOJSON = WD_dict["basin_GEOJSON"]
            msg=WD_dict["msg"]
            status=WD_dict["status"]

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
        with open(outlet_snapped_GEOJSON) as f:
            outlet_snapped_data = json.load(f)

        return JsonResponse({"basin_data":basin_data,
                             "outlet_snapped_data":outlet_snapped_data})

