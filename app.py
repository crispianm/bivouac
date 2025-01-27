from flask import Flask, render_template, url_for, jsonify, request, json
import re
import math

app = Flask(__name__)
from basic_weather_calls import weather_mesh
from wind_shelter import wind_shelter
from OSGridConverter import *

# from pathfinding import get_tile
from feature_class import map_feature, map_layer, heatmap_layer
import mercantile

# from elevation import getElevationMatrix, rasterToImage, getRasterRGB, getSlopeMatrix
from new_pathfinding import new_get_min_path
import numpy as np


class Optimiser:
    def __init__(self):
        self.preferences = {
            "Shops": None,
            "Pubs": None,
            "Water": None,
            "Accomodation": None,
            "Medical": None,
            "Landmarks": None,
            "Paths": None,
            "Elevation": None,
        }
        self.latlon = None
        self.zoom_level = None
        self.bbox = None
        self.startPoint = None
        self.endPoint = None
        self.features = None
        self.shelterIndex = None
        self.OSGridReference = None
        self.tempWind = None
        self.debug = True
        self.numberOfPoints = 30

    def updateOptimiser(self, latlon, zoom_level, bbox, features, preferences):
        self.latlon = latlon
        self.zoom_level = float(zoom_level)
        self.bbox = self.getBBoxList(bbox)
        self.features = features
        self.preferences = self.updatePreferences(preferences)
        self.shelterIndex = self.getShelterIndex()
        self.OSGridReference = self.getOSGridReference()
        self.tempWind = self.getTempWind()

    def make_heatmap(self, file_name):
        heatmap = heatmap_layer(self.bbox, self.preferences)
        heatmap.make_layers(file_name)

        x = heatmap.grid[0]
        y = heatmap.grid[1]
        z = heatmap.grid[2]

        n_spots = self.numberOfPoints
        grid_spots = np.concatenate(
            (
                np.array(
                    [
                        x[
                            np.unravel_index(
                                np.argsort(z.flatten())[-n_spots:], z.shape
                            )[0],
                            0,
                        ]
                    ]
                ).T,
                np.array(
                    [
                        y[
                            0,
                            np.unravel_index(
                                np.argsort(z.flatten())[-n_spots:], z.shape
                            )[1],
                        ]
                    ]
                ).T,
            ),
            1,
        )

        latlong_spots = []
        for i in range(grid_spots.shape[0]):
            latlong = grid2latlong(
                str(OSGridReference(grid_spots[i][0], grid_spots[i][1]))
            )
            latlong_spots.append([latlong.longitude, latlong.latitude])

        # heatmap.plot_3D_heatmap()
        return latlong_spots

    def convertToJson(self, minPath):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "LineString", "coordinates": minPath},
                }
            ],
        }
        # output = open("minPath.geojson", "w")
        # json.dump(geojson, output)
        return geojson

    def getBBoxList(self, bbox):
        bboxLatLon = re.findall("\(.*?\)", bbox)
        bboxList = []
        for latLon in bboxLatLon:
            bboxList.append(
                latLon.replace("(", "").replace(")", "").replace(" ", "").split(",")
            )
        bbox = [
            [float(bboxList[0][0]), float(bboxList[0][1])],
            [float(bboxList[1][0]), float(bboxList[1][1])],
        ]
        return bbox

    def setPoint(self, start_latlonDict, end_latlonDict):

        self.startPoint = [start_latlonDict["lng"], start_latlonDict["lat"]]
        self.endPoint = [end_latlonDict["lng"], end_latlonDict["lat"]]

        print("startPoint: ", self.startPoint)
        print("endPoint: ", self.endPoint)

        route_zoom = math.ceil(float(self.zoom_level))

        min_path = []
        while len(min_path) == 0:
            try:
                min_path = new_get_min_path(self.startPoint, self.endPoint, route_zoom)
            except:
                print("Error at zoom level: ", route_zoom)
                route_zoom -= 1
            if route_zoom < 8:
                print("\nNo path found")
                break

        return self.convertToJson(min_path)

    def getFeatures(self):
        pass
        # print(self.features)

    def getShelterIndex(self):
        shelterIndex = wind_shelter(
            self.latlon["lat"], self.latlon["lng"], math.ceil(float(self.zoom_level))
        )
        return shelterIndex

    def getOSGridReference(self):
        return str(latlong2grid(self.latlon["lat"], self.latlon["lng"]))

    def getTempWind(self):
        get_weather = weather_mesh([self.latlon["lat"]], [self.latlon["lng"]])
        tempWind = get_weather["features"][0]["properties"]
        return tempWind

    def updatePreferences(self, newPreferences):
        preferences = {}
        keys = list(self.preferences.keys())
        prefList = []
        for preference in newPreferences:
            if preference.isdigit():
                prefList.append(preference)

        for i in range(0, len(prefList)):
            preferences[keys[i]] = prefList[i]
        return preferences

    def printStats(self):
        print("Latlon:", self.latlon, flush=True)
        print("zoom_level:", self.zoom_level, flush=True)
        print("bbox:", self.bbox, flush=True)
        print("shelterIndex:", self.shelterIndex, flush=True)
        print("OSGridReference:", self.OSGridReference, flush=True)
        print("preferences:", self.preferences, flush=True)

    def run(self):

        app = Flask("Optimiser")

        @app.route("/")
        def home():
            return render_template("bivouac.html")

        @app.route("/end_destination", methods=["POST", "GET"])
        def end_destination():
            if request.method == "POST":

                start_location = json.loads(
                    re.findall("\{.*?\}", request.form["start_location"])[1]
                )
                end_location = json.loads(
                    re.findall("\{.*?\}", request.form["end_location"])[1]
                )
                minpath = optimiser.setPoint(start_location, end_location)
                data = {"status": "success", "minpath": minpath}

                print("Minpath obtained!\n")

            return data, 200

        @app.route("/create_heatmap", methods=["POST", "GET"])
        def create_heatmap():
            if request.method == "POST":

                best_points = optimiser.convertToJson(
                    optimiser.make_heatmap(self.features)
                )
                data = {"status": "success", "points": best_points}

            return data, 200

        @app.route("/set_preferences", methods=["POST", "GET"])
        def get_preferences():
            if request.method == "POST":
                preferences = request.form["preferences"]
                print("preferences set: ", preferences)
                data = {"status": "success"}
                try:
                    optimiser.preferences = optimiser.updatePreferences(preferences)
                except NameError:
                    pass
            return data, 200

        @app.route("/get_result", methods=["POST", "GET"])
        def process_result():
            if request.method == "POST":

                mouse_pos = request.form["mouse_info"]
                zoom_level = request.form["zoom_level"]
                bbox = request.form["bbox"]
                preferences = request.form["vals"]
                features = request.form["features"]

                latlon = json.loads(re.findall("\{.*?\}", mouse_pos)[1])
                optimiser.updateOptimiser(
                    latlon, zoom_level, bbox, json.loads(features), preferences
                )

                num_features = len(json.loads(features))

                data = {
                    "status": "success",
                    "some": num_features,
                    "temp": optimiser.tempWind["Temp"],
                    "wind": optimiser.tempWind["Wind"],
                    "wind_shelter": round(optimiser.shelterIndex, 4),
                    "osGrid": optimiser.OSGridReference,
                }

            return data, 200
        
        app.run(host="0.0.0.0")


if __name__ == "__main__":
    optimiser = Optimiser()
    optimiser.run()
