# scratch code to run in QGIS if I want to get the attributes of a table
# currently this one is designed for the Calgary City Boundary table,
# but can be modified to include more

# NOTE:
# this script is designed to be ran in QGIS, it will fail if ran in my project environment

import csv
from qgis.core import QgsProject # type: ignore[reportMissingImports]
# ignore that Pylance doesn't recognize this library

layer_name = "weather_stations"
layer = QgsProject.instance().mapLayersByName(layer_name)[0]

# Define output path (CSV can be opened/saved as Excel)
output_path = r"C:/path/to/your/field_definitions.csv"
output_path = r"C:/Users/willh/Desktop/weather_stations_field_definitions.csv"

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(
        ["ID", "Name", "Type", "TypeName", "Length", "Precision"]
    )

    for idx, field in enumerate(layer.fields()):
        """
        # scratch code for listing the attributes, so I can figure out which one to use
        for item in dir(field): print(item)
        break
        """

        writer.writerow(
            [
                idx,
                field.name(),
                field.friendlyTypeString(),
                field.typeName(),
                field.length(),
                field.precision(),
            ]
        )

print("Field definitions exported successfully!")