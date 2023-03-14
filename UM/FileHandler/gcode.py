import os
import math
from enum import Enum
import subprocess

class TransformGCode:
    class SliceType(Enum):
        NONE = 0
        INNER = 1
        OUTER = 2
        SKIN = 3
        FILL = 4
        SKIRT = 5

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

    layerHeight = 30
    secondaryZAxis = 1000
    store = []
    sliceType = SliceType.NONE
    layer = 0
    holdJSTemplate = ""
    holdDivTemplate = ""
    points = {}
    pathOrder = []

    # ----------------------------------
    # toString()
    # ---------------------------------
    def __repr__(self) -> str:
        return f"{type(self).__name__}(layerHeight={self.layerHeight}, secondaryZAxis={self.secondaryZAxis})"

    # ---------------------------------
    # Generate HTML for the layer
    # ---------------------------------
    def addLayerHTML(self):
        if not self.points:
            return
        tempJS = self.jsTemplate
        tempDiv = self.divTemplate
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
    # Calculate if there is a turn between three given points
    # if there is a turn return the angle
    # ---------------------------------------------------
    def calculateTurn(self):
        deltaX = self.store[1][0] - self.store[0][0]
        deltaY = self.store[1][1] - self.store[0][1]
        if deltaX == 0:
            return 90
        formula = deltaY / deltaX
        angle = math.atan(formula)*(180/math.pi)
        return angle

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
        writeTypeStart = ""
        writeTypeEnd = ""
        nextZ = ""
        nonXYLines = []

        for line in content:
            line = line.strip()
            if ";Layer height:" in line:
                tempVal = line.split(":")[1].strip()
                self.layerHeight = float(tempVal)
                print("Layer Height : " + str(self.layerHeight))
                continue
            if ";secondary_z_axis:" in line:
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
                # self.sliceType = SliceType.NONE
                self.layer = int(line.split(";LAYER:")[1].strip())
                # print("Layer = " + str(self.layer))
                self.points.clear()
                # writeLayer = "; ---- LAYER " + str(self.layer) + " --------"
                # writeLayer = writeLayer + '\nN' + str(count) + " M1"
                #writeLayer =  'N' + str(count) + " M1"
                #of.write("; ---- LAYER " + str(self.layer) + " --------")
                self.pathOrder = []

                localValue = layerCount * self.layerHeight
                if localValue > self.secondaryZAxis:
                    layerCount = 1
                    localValue = 0
                if localValue == 0:
                    writeLayer = 'N' + str(count) + " M1"
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
                if self.sliceType == self.SliceType.FILL or self.sliceType == self.SliceType.SKIN or self.sliceType == self.SliceType.SKIRT:
                    liftSideValue = 'N' + str(count) + " M3"
                    count = count + 1
                    writeTypeStart = liftSideValue
                    # print(writeTypeStart)

                # -----------------------------------------------
                # if SliceType of type SKIN or FILE started
                # add a "M2"
                # -----------------------------------------------
                self.sliceType = self.SliceType[line.split(
                    ":")[1].replace("WALL-", "").strip()]
                #print("slice = " + str(self.sliceType.value))
                if self.sliceType == self.SliceType.FILL or self.sliceType == self.SliceType.SKIN or self.sliceType == self.SliceType.SKIRT:
                    liftSideValue = 'N' + str(count) + " M2"
                    count = count + 1
                    writeTypeEnd = liftSideValue
                    # print(writeTypeEnd)
                # writeType = "; ---- " + \
                #     str(self.sliceType) + " --------" + liftSideValue
                # of.write("; ---- " +      str(self.sliceType) + " --------")

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

                    if " Z" in line:
                        tempVal = line.split(" Z")[1].split(" ")[0]
                        out = out.replace(" Z" + tempVal, "")

                    if " X" not in out and " Y" not in out:
                        if len(nextZ) > 0:
                            out = out + " " + nextZ
                        nextZ = ""
                        nonXYLines.append(out)
                        continue

                    if " X" in out and " Y" in out:
                        self.store.append([currX, currY])
                        if len(self.store) > 2:
                            self.store.pop(0)
                        if len(self.store) == 2:
                            angle = self.calculateTurn()
                            saveLine = saveLine + " C" + format(angle, '.5f')

                if len(saveLine.strip()) > 0:
                    saveLine = saveLine.replace(" G28 ", " G0 ")
                    # of.write(saveLine + "\t; -- " + str(self.cordX()
                    #                                     ) + ", " + str(self.cordY()) + "\n")
                    of.write(saveLine + "\n")
                    for nxyLine in nonXYLines:
                        of.write(nxyLine + "\n")
                    nonXYLines = []
                    if len(writeLayer.strip()) > 0:
                        of.write(writeLayer + "\n")
                        writeLayer = ""
                    if len(writeTypeStart.strip()) > 0:
                        of.write(writeTypeStart + "\n")
                        writeTypeStart = ""
                    if len(writeTypeEnd.strip()) > 0:
                        of.write(writeTypeEnd + "\n")
                        writeTypeEnd = ""
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
            of.write(saveLine + "\n")
            for nxyLine in nonXYLines:
                of.write(nxyLine + "\n")
                nonXYLines = []
                if len(writeTypeStart.strip()) > 0:
                    of.write(writeTypeStart + "\n")
                    writeTypeStart = ""
                if len(writeTypeEnd.strip()) > 0:
                    of.write(writeTypeEnd + "\n")
                    writeTypeEnd = ""
        self.addLayerHTML()
        print("-------------Done---------")
        # os.system(r'D:/g2p/g2pcoach.exe C:/Users/Public/gcode1.txt')
        plot = open("plot.html", "w")
        plot.write(self.htmlTemplate.replace("JS_TEMPLATE", self.holdJSTemplate).replace(
            "DIV_TEMPLATE", self.holdDivTemplate))
        plot.close()
        f.close()
        of.close()
        subprocess.Popen([os.environ['PROGRAMFILES'] +
                        "/Merlin Printer 1.0.0/UM/g2p/g2pcoach.exe", dest])


#---------- TESTING ---------------------------

inputFile = "C:\\Users\\nr\\Documents\\Merlin\\lshape.gcode"
outputFile = "C:\\Users\\nr\\Documents\\Merlin\\lshape_out.gcode"

transform = TransformGCode()
transform.updateGcode(inputFile, outputFile)

