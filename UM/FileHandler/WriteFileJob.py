# Copyright (c) 2020 Ultimaker B.V.
# Uranium is released under the terms of the LGPLv3 or higher.

from UM.Job import Job

from UM.Logger import Logger
from UM.FileHandler.FileWriter import FileWriter
from UM.Message import Message

import io
import os
import time
import subprocess
import math

from typing import Any, Optional, Union
from enum import Enum


class SliceType(Enum):
    NONE = 0
    INNER = 1
    OUTER = 2
    SKIN = 3
    FILL = 4
    SKIRT= 5
    

htmlTemplate = '''
<html>
<head>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <script type="text/javascript">
        google.charts.load('current', { 'packages': ['corechart'] });
        google.charts.setOnLoadCallback(drawChart);
        function drawChart() {
            JS_TEMPLATE
        }
    </script>
</head>
<body>
    <table border='0'>
        DIV_TEMPLATE
    </table>
</body>
</html>
'''

jsTemplate = '''
                data1 = google.visualization.arrayToDataTable([
                    ['X', 'Y'],
                    DATA_1
                ]);
                data2 = google.visualization.arrayToDataTable([
                    ['X', 'Y'],
                    DATA_2
                ]);
                data3 = google.visualization.arrayToDataTable([
                    ['X', 'Y'],
                    DATA_3
                ]);
                data4 = google.visualization.arrayToDataTable([
                    ['X', 'Y'],
                    DATA_4
                ]);
                options1 = {
                    title: 'TITLE_1',
                    legend: { position: 'none' },
                    'chartArea': {'width': '90%', 'height': '80%'},
                };
                options2 = {
                    title: 'TITLE_2',
                    legend: { position: 'none' },
                    'chartArea': {'width': '90%', 'height': '80%'},
                };
                options3 = {
                    title: 'TITLE_3',
                    legend: { position: 'none' },
                    'chartArea': {'width': '90%', 'height': '80%'},
                };
                options4 = {
                    title: 'TITLE_4',
                    legend: { position: 'none' },
                    'chartArea': {'width': '90%', 'height': '80%'},
                };
                CHART_1 = new google.visualization.LineChart(document.getElementById('ROWCOL_1'));
                CHART_1.draw(data1, options1);
                CHART_2 = new google.visualization.LineChart(document.getElementById('ROWCOL_2'));
                CHART_2.draw(data2, options2);
                CHART_3 = new google.visualization.LineChart(document.getElementById('ROWCOL_3'));
                CHART_3.draw(data3, options3);
                CHART_3 = new google.visualization.LineChart(document.getElementById('ROWCOL_4'));
                CHART_3.draw(data4, options4);
'''

divTemplate = '''
        <tr>
            <td>
                _LAYER_
            </td>
            <td>
                <div id="ROWCOL_1" style="width: 700px; height: 400px"></div>
            </td>
            <td>
                <div id="ROWCOL_2" style="width: 700px; height: 400px"></div>
            </td>
            <td>
                <div id="ROWCOL_3" style="width: 700px; height: 400px"></div>
            </td>
            <td>
                <div id="ROWCOL_4" style="width: 700px; height: 400px"></div>
            </td>
        </tr>
'''    

class WriteFileJob(Job):
    layerHeight = 30
    secondaryZAxis = 100
    store = []
    sliceType = SliceType.NONE
    layer = 0
    holdJSTemplate = ""
    holdDivTemplate = ""
    points = {}
    pathOrder = []
    """A Job subclass that performs writing.

    The writer defines what the result of this job is.
    """

    def __init__(self, writer: Optional[FileWriter], stream: Union[io.BytesIO, io.StringIO], data: Any, mode: int) -> None:
        """Creates a new job for writing.

        :param writer: The file writer to use, with the correct MIME type.
        :param stream: The output stream to write to.
        :param data: Whatever it is what we want to write.
        :param mode: Additional information to send to the writer, for example: such as whether to
        write in binary format or in ASCII format.
        """

        super().__init__()
        self._stream = stream
        self._writer = writer
        self._data = data
        self._file_name = ""
        self._mode = mode
        # If this file should be added to the "recent files" list upon success
        self._add_to_recent_files = False
        self._message = None  # type: Optional[Message]
        self.progress.connect(self._onProgress)
        self.finished.connect(self._onFinished)

    def _onFinished(self, job: Job) -> None:
        if self == job and self._message is not None:
            self._message.hide()
            self._message = None

    def _onProgress(self, job: Job, amount: float) -> None:
        if self == job and self._message:
            self._message.setProgress(amount)

    def setFileName(self, name: str) -> None:
        self._file_name = name

    def getFileName(self) -> str:
        return self._file_name

    def getStream(self) -> Union[io.BytesIO, io.StringIO]:
        return self._stream

    def setMessage(self, message: Message) -> None:
        self._message = message

    def getMessage(self) -> Optional[Message]:
        return self._message

    def setAddToRecentFiles(self, value: bool) -> None:
        self._add_to_recent_files = value

    def getAddToRecentFiles(self) -> bool:
        return self._add_to_recent_files and (True if not self._writer else self._writer.getAddToRecentFiles())

   
    def run(self) -> None:
        Job.yieldThread()
        begin_time = time.time()
        self.setResult(None if not self._writer else self._writer.write(
            self._stream, self._data, self._mode))
        Logger.log("d", "---------------------------------")
        Logger.log("d", self.getFileName())
        if not self.getResult():
            self.setError(Exception(
                "No writer in WriteFileJob" if not self._writer else self._writer.getInformation()))
        end_time = time.time()
        Logger.log("d", "Writing file took %s seconds", end_time - begin_time)
        self.updateGcode(self.getFileName(), os.path.splitext(
            self.getFileName())[0]+"_transformed.gcode")

    # ----------------------------------
    # toString()
    # ---------------------------------
    def __repr__(self) -> str:
        return f"{type(self).__name__}(layerHeight={self.layerHeight}, secondaryZAxis={self.secondaryZAxis})"

    # ---------------------------------
    # Generate HTML for the layer
    # ---------------------------------
    def addLayerHTML(self):
        print("addLayerHTML : " + str(self.pathOrder))
        if not self.points:
            return
        tempJS = jsTemplate
        tempDiv = divTemplate
        allPoints = ""
        column = 0
        for porder in self.pathOrder:
            column = column + 1
            if porder in self.points:
                tempJS = tempJS.replace(
                    "DATA_" + str(column), self.points[porder])
                tempJS = tempJS.replace(
                    "ROWCOL_" + str(column), "row_" + str(self.layer) + "_col_" + str(column))
                tempJS = tempJS.replace("TITLE_" + str(column), str(porder))
                tempDiv = tempDiv.replace(
                    "ROWCOL_" + str(column), "row_" + str(self.layer) + "_col_" + str(column))
                allPoints = allPoints + self.points[porder]

        tempJS = tempJS.replace("DATA_4", allPoints)
        tempJS = tempJS.replace("ROWCOL_4", "row_" +
                                str(self.layer) + "_col_4")
        tempJS = tempJS.replace("TITLE_4", "ALL")
        tempDiv = tempDiv.replace(
            "ROWCOL_4", "row_" + str(self.layer) + "_col_4")
        tempDiv = tempDiv.replace("_LAYER_", str(self.layer))
        self.holdJSTemplate = self.holdJSTemplate + tempJS
        self.holdDivTemplate = self.holdDivTemplate + tempDiv

    # ---------------------------------------------------
    # Calculate the Angle between three given points
    # ---------------------------------------------------
    def getAngle(self, a, b, c):
        ang = math.degrees(math.atan2(
            c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
        return ang + 360 if ang < 0 else ang

    # ---------------------------------------------------
    # Calculate if there is a turn between three given points
    # if there is a turn return the angle
    # ---------------------------------------------------
    def calculateTurn(self):
        slopeA = self.store[1][1] - self.store[0][1] / \
            self.store[1][0] - self.store[0][0]
        slopeB = self.store[2][1] - self.store[1][1] / \
            self.store[2][0] - self.store[1][0]
        if slopeA != slopeB:
            return self.getAngle(self.store[0], self.store[1], self.store[2])
        return 0

    # ---------------------------------------------------
    # find the shift in x-axis between two points
    # ---------------------------------------------------
    def cordX(self):
        if len(self.store) < 2:
            return 0
        return self.store[1][0] - self.store[0][0]

    # ---------------------------------------------------
    # find the shift in y-axis between two points
    # ---------------------------------------------------
    def cordY(self):
        if len(self.store) < 2:
            return 0
        return self.store[1][1] - self.store[0][1]

    # ---------------------------------------------------
    # find the shift in x-axis between two points
    # ---------------------------------------------------
    def updateGcode(self, source: str, dest: str):
        print(dest+","+source)
        f = open(source, "r")
        of = open(dest,  "w")

        count = 1
        content = f.readlines()
        layerCount = 1
        saveLine = ""
        writeLayer = ""
        writeType = ""
        nextZ = ""

        for line in content:
            line = line.strip()
            if ";Layer height:" in line:
                tempVal = line.split(":")[1].strip()
                self.layerHeight = float(tempVal)
                print("Layer Height : " + str(self.layerHeight))
                continue
            if ";MINZ:" in line:
                tempVal = line.split(":")[1].strip()
                if tempVal.replace(".", "").isnumeric():
                    self.secondaryZAxis = float(tempVal)
                    print("secondaryZAxis : " + str(self.secondaryZAxis))
                continue
            if line.startswith("M"):
                continue

            if ";LAYER:" in line:

                if self.layer < 3:
                    self.addLayerHTML()
                self.sliceType = SliceType.NONE
                self.layer = int(line.split(";LAYER:")[1].strip())
                print("Layer = " + str(self.layer))
                self.points.clear()
                # writeLayer = "; ---- LAYER " + str(self.layer) + " --------"
                # writeLayer = writeLayer + '\nN' + str(count) + " M1"
                # writeLayer =  'N' + str(count) + " M1"
                self.pathOrder = []

                localValue = layerCount * self.layerHeight
                if localValue >= self.secondaryZAxis:
                    layerCount = 1
                    localValue = 0
                if localValue == 0:
                    writeLayer =  'N' + str(count) + " M1"
                    nextZ = "Z" + str(self.layerHeight)
                else:
                    nextZ = "Z" + str(localValue)
                layerCount = layerCount + 1
                continue

            # -----------------------------------------------
            # New Slicetype is starting. SliceType can be
            # INNER WALL, OUTER WALL, FILL, or SKIN
            # -----------------------------------------------
            elif ";TYPE:" in line:
                liftSideValue = ""
                # -----------------------------------------------
                # if the Last SliceType was a SKIN or FILE
                # add a "M3"
                # -----------------------------------------------
                if self.sliceType == SliceType.FILL or self.sliceType == SliceType.SKIN or self.sliceType == SliceType.SKIRT :
                    liftSideValue = 'N' + str(count) + " M3"
                    count = count + 1

                # -----------------------------------------------
                # if SliceType of type SKIN or FILE started
                # add a "M2"
                # -----------------------------------------------
                self.sliceType = SliceType[line.split(
                    ":")[1].replace("WALL-", "").strip()]
                if self.sliceType == SliceType.FILL or self.sliceType == SliceType.SKIN or self.sliceType == SliceType.SKIRT:
                    liftSideValue = 'N' + str(count) + " M2"
                    count = count + 1
                # writeType = "; ---- " + \
                #     str(self.sliceType) + " --------" + liftSideValue
                writeType = liftSideValue

                # -----------------------------------------------
                # generate heading for HTML and the order of
                # SliceType for this Layer
                # -----------------------------------------------
                self.points[self.sliceType] = "// -- " + \
                    str(self.layer) + " :: " + str(self.sliceType) + "\n"
                self.pathOrder.append(self.sliceType)
                continue

            if len(line.strip()) > 0 and line[0] != ';':
                if ";" in line:
                    out = 'N' + str(count) + " " + \
                        line.split(";")[0].replace("E", "A").strip()
                elif "S" in line:
                    out = 'N' + str(count) + " " + \
                        line.split("S")[0].strip()
                else:
                    out = 'N' + str(count) + " " + \
                        line.replace("E", "A").strip()
                fields = out.split(" ")
                if len(fields) > 2 and (fields[1] == "G1" or fields[1] == "G0"):
                    currX = -1
                    currY = -1
                    for fld in fields:
                        if fld.startswith("X"):
                            currX = float(fld.replace("X", ""))
                        if fld.startswith("Y"):
                            currY = float(fld.replace("Y", ""))

                    if " X" in out and " Y" in out:
                        self.store.append([currX, currY])
                        if len(self.store) > 3:
                            self.store.pop(0)
                        if len(self.store) == 3:
                            angle = self.calculateTurn()
                            if angle > 0:
                                if float(self.cordX()) > 10 or float(self.cordY()) > 10:
                                    saveLine = saveLine + " C" + format(angle, '.0f')

                    if " Z" in line:
                        tempVal = line.split(" Z")[1].split(" ")[0]
                        out = out.replace(" Z" + tempVal, "")

                if len(saveLine.strip()) > 0:
                    saveLine = saveLine.replace(" G28 ", " G0 ")
                    # of.write(saveLine + "\t; -- " + str(self.cordX()
                    #                                     ) + ", " + str(self.cordY()) + "\n")
                    of.write(saveLine + "\n")
                    if len(writeLayer.strip()) > 0:
                        of.write(writeLayer + "\n")
                        writeLayer = ""
                    if len(writeType.strip()) > 0:
                        of.write(writeType + "\n")
                        writeType = ""
                if " X" in saveLine and " Y" in saveLine:
                    xVal = saveLine.split(" X")[1].split(" ")[0]
                    yVal = saveLine.split(" Y")[1].split(" ")[0]
                    self.points[self.sliceType] = self.points[self.sliceType] + \
                        "[" + xVal + ", " + yVal + "],\n"
                saveLine = out
                if len(nextZ) > 0:
                    saveLine = saveLine + " " + nextZ
                    nextZ = ""
                count = count + 1
        if len(saveLine.strip()) > 0:
            saveLine = saveLine.replace(" G28 ", " G0 ")
            # of.write(saveLine + "\t; -- " + str(self.cordX()) +
            #          ", " + str(self.cordY()) + "\n")
            of.write(saveLine)
        self.addLayerHTML()
        print("-------------Done---------")
        f.close()
        of.close()
   
        Logger.log("d", os.environ['PROGRAMFILES'] +
                "/Merlin Printer 1.0.0/UM/g2p/g2pcoach.exe")
        subprocess.Popen([os.environ['PROGRAMFILES'] +
                        "/Merlin Printer 1.0.0/UM/g2p/g2pcoach.exe", dest])
