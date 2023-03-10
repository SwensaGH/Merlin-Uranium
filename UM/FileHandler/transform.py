import sys
print(sys.argv)
print(sys.argv[0])
print(sys.argv[1])
f = open(sys.argv[1], "r")
of = open(sys.argv[2],  "w")
count = 1
content = f.readlines()
for line in content:
    line = line.strip()
    if line != '' and line[0] != ';':
        if ";" in line:
            of.write('N' + str(count) + " " + line.split(";")[0].replace("E", "Z").strip() + "\n")
        elif "S" in line:
            of.write('N' + str(count) + " " + line.split("S")[0].strip() + "\n")
        else :
            of.write( 'N' + str(count)  + " " + line.replace("E", "Z").strip() + "\n")
        count = count + 1    
print("-------------Done---------")
f.close()
of.close()
