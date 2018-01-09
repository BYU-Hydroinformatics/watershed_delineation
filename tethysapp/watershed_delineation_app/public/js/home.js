/**
 * Created by sherry on 12/29/17.
 */
var map, click_point_layer, river_layer, basin_layer, snap_point_layer,dem_layer;
var outlet_x, outlet_y;

var displayStatus = $('#display-status');


$(document).ready(function () {

    map = new ol.Map({
	layers: [ ],
	controls: ol.control.defaults(),
	target: 'map',
	view: new ol.View({
		zoom: 8,
        projection: "EPSG:3857"
	})
    });

    bing_layer = new ol.layer.Tile({
		source: new ol.source.BingMaps({
			imagerySet: 'AerialWithLabels',
			key: 'SFpNe1Al6IDxInoiI7Ta~LX-BVFN0fbUpmO4hIUm3ZA~AsJ3XqhA_0XVG1SUun4_ibqrBVYJ1XaYJdYUuHGqVCPOM71cx-3FS2FzCJCa2vIh'
		})
	});

    // river_layer = new ol.layer.Vector({
    //     source: new ol.source.Vector({
    //       url: "/static/watershed_delineation_app/kml/streams_1k_vect.kml",
    //       format: new ol.format.KML(),
    //      })
    //   });

    river_layer = new ol.layer.Tile({
        source: new ol.source.TileWMS({
            //url: 'https://geoserver.byu.edu/arcgis/services/sherry/utah_streams1k/MapServer/WMSServer?',
            url:'https://geoserver.byu.edu/arcgis/services/sherry/dr_streams/MapServer/WMSServer?',
            params: {'LAYERS': '0'},
            crossOrigin: 'anonymous'
        }),
        keyword: 'nwm'
    });

    click_point_layer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      style: new ol.style.Style({
        fill: new ol.style.Fill({
          color: 'rgba(255, 255, 255, 0.2)'
        }),
        stroke: new ol.style.Stroke({
          color: '#ffcc33',
          width: 2
        }),
        image: new ol.style.Circle({
          radius: 7,
          fill: new ol.style.Fill({
            color: '#ffcc33'
          })
        })
      })
    });

    snap_point_layer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      style: new ol.style.Style({
        fill: new ol.style.Fill({
          color: 'rgba(255, 255, 255, 0.2)'
        }),
        stroke: new ol.style.Stroke({
          color: '#00ff00',
          width: 2
        }),
        image: new ol.style.Circle({
          radius: 7,
          fill: new ol.style.Fill({
            color: '#00ff00'
          })
        })
      })
    });

    basin_layer = new ol.layer.Vector({
    source: new ol.source.Vector({
        features: new ol.format.GeoJSON()
    }),
    style: new ol.style.Style({
        stroke: new ol.style.Stroke({
        color: 'blue',
        lineDash: [4],
        width: 3
        }),
        fill: new ol.style.Fill({
        color: 'rgba(0, 0, 255, 0.1)'
        })
    })
    });

    map.addLayer(bing_layer);

    map.addLayer(click_point_layer);
    map.addLayer(river_layer);
    map.addLayer(basin_layer);
    map.addLayer(snap_point_layer);

    // var ylat = 40.1;
    // var xlon = -111.55;
    var ylat = 18.9108;
    var xlon = -71.2500;
    CenterMap(xlon,ylat);
    map.getView().setZoom(10);

    map.on('click', function(evt) {
        var coordinate = evt.coordinate;
        addClickPoint(evt.coordinate);

        outlet_x = coordinate[0];
        outlet_y = coordinate[1];
        // map.getView().setCenter(evt.coordinate);
        // map.getView().setZoom(14);

    })

});

function CenterMap(xlon,ylat){
    var dbPoint = {
        "type": "Point",
        "coordinates": [xlon, ylat]
    };
    var coords = ol.proj.transform(dbPoint.coordinates, 'EPSG:4326','EPSG:3857');
    map.getView().setCenter(coords);
}

function addClickPoint(coordinates){
    // Check if the feature exists. If not then create it.
    // If it does exist, then just change its geometry to the new coords.
    var geometry = new ol.geom.Point(coordinates);
    if (click_point_layer.getSource().getFeatures().length==0){
        var feature = new ol.Feature({
            geometry: geometry,
            attr: 'Some Property'
        });
        click_point_layer.getSource().addFeature(feature);
    } else {
        click_point_layer.getSource().getFeatures()[0].setGeometry(geometry);
    }
}

function geojson2feature(myGeoJSON) {
    //Convert GeoJSON object into an OpenLayers 3 feature.
    var geojsonformatter = new ol.format.GeoJSON();
    var myFeature = geojsonformatter.readFeatures(myGeoJSON);
    //var myFeature = new ol.Feature(myGeometry);
    return myFeature;

}

function run_wd_service() {

    basin_layer.getSource().clear();
    snap_point_layer.getSource().clear();

    displayStatus.removeClass('error');
    displayStatus.addClass('calculating');
    displayStatus.html('<em>Calculating...</em>');

    $.ajax({
        type: 'GET',
        url: 'run',
        dataType:'json',
        data: {
                'xlon': outlet_x,
                'ylat': outlet_y,
                'prj' : "native"
        },
        success: function (data) {

            basin_layer.getSource().addFeatures(geojson2feature(data.basin_data));
            snap_point_layer.getSource().addFeatures(geojson2feature(data.outlet_snapped_data));
            displayStatus.removeClass('calculating');
            displayStatus.addClass('success');
            displayStatus.html('<em>Success!</em>');

            map.getView().fit(basin_layer.getSource().getExtent(), map.getSize())


        },
        error: function (jqXHR, textStatus, errorThrown) {
            alert("Error");
            displayStatus.removeClass('calculating');
            displayStatus.addClass('error');
            displayStatus.html('<em>' + errorThrown + '</em>');
        }
    });

}
