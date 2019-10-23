'''
LKB 2019(c)
FLAMINGO toolset

Read NMEA $GPGGA and $GPRMC and adds noise
Outputs $GPGGA,$GPRMC,$GPGST strings

$GPRMC is required for Google Earth. GE is also checking CRC


NOTE:

$GPGGA lat, long is in   DDMM.MMMMM (to 2cm level)
talker ID: $GP - GPS, $GL - GLO, $GN - combined


WARNING:

This code is only valid for Europe (lat,lon conversion)
In GST
 residuals are hardcoded to pseudorange residuals
 Error ellipse orientation is assumed to be ~75-85deg from north
 (correct in multipath free European locations).
 Folowing same assumptions lat == semi-major and lon == semi-minor

There are a lot of assumptions in the code
It was not fully tested
'''
import numpy as np
from numpy.random import uniform

import glob

##################
####SUPPORT FUNCTIONS
###################

'''
calculate NMEA CRC
This is requied for Google Earth (I do crc on each line)
IN: NMEAstr between $ and * (!)
OUT:checksum to place after *
ex'$GPGSV,3,3,10,26,37,134,00,29,25,136,00*76'

code based on <http://code.activestate.com/recipes/576789-nmea-sentence-checksum/>
'''
def calculateNMEAchecksum(NMEAstring):

    calc_cksum = 0
    for s in NMEAstring:
        #it is XOR of ech Unicode integer representation
        calc_cksum ^= ord(s)

    calc_cksum = hex(calc_cksum) #get hex representation
    calc_cksum = f'{calc_cksum}'[2:] #cut 0x

    return calc_cksum



'''
wrapper for NMEA string CRC corrections
IN: full NMEAstr
OUT:corrected CRC
'''
def correctNMEAcrc(NMEAstring):
	NMEAstring = NMEAstring[1:].split('*')[0] #get str between $ and *
	CRCvalue = calculateNMEAchecksum(NMEAstring)

	correctNMEA= f'${NMEAstring}*{CRCvalue}\n'
	return correctNMEA

'''
IN: str DDMM.MMMMMMM
OUT: MM.MMMMMMM
'5256.546' == 3176.546
'''
def convertDDMMtoMM(coordinateString):

	if coordinateString.find('.')==4: #DDMM.MMMMMMM
		coord = int(coordinateString[:2])*60+float(coordinateString[2:])
	elif coordinateString.find('.')==5: #DDDMM.MMMMMMM
		coord = int(coordinateString[:3])*60+float(coordinateString[3:])
	else:
		print(f'ERROR with {coordinateString}')
	return coord


'''
IN: MM.MMMMMMM
OUT: str DDMM.MMMMM
3rd decimal place is 2m, 5th is 2cm, 6th is 2mm
3176.546 == '5256.54600'
'''
def convertMMtoDDMM(coordinateVal):
	from math import floor

	DD = floor(coordinateVal/60)
	MM = coordinateVal-DD*60
	# breakpoint()
	return f'{DD:03}{MM:02.5f}'


'''
translate noise level to precision model in [m]
N-S lat (\Phi)
E-W lon (\LambnoiseLevelda)

OUT:  [precLat,precLon,precHt]
'''
def precModel(noiseLevel):
	lat_lon_Ratio = 2 #how much each contribure to noise
	precLon = noiseLevel/np.sqrt(1+lat_lon_Ratio)
	precLat = np.sqrt(noiseLevel**2-precLon**2)
	precHt = noiseLevel*4

	precVec  = [precLat,precLon,precHt]
	precVec = [round(item,2) for item in precVec]
	# print(precVec,np.sqrt(precVec[0]**2+precVec[1]**2))

	return precVec

'''
create error at 68% CEP
TODO: check the naming convencion with vanDilligen
TODO: create more advanced model with offsets
IN:  [precLat,precLon,precHt] [m]
OUT: [errLat,errLon,errHt] [min,min,m]

TODO: consider more advanced error model
'''
def createErrors(precModelArray,probability=0.68):
	precModelArray = np.array(precModelArray)
	#baloon prec to acc and split around 0
	accCoefficient = 1+(1-probability)/2
	accModel = accCoefficient*precModelArray/2
	errModel =[uniform(-acc,acc) for acc in accModel] #in m

	errModel = np.array(errModel)*[1/1200,1/1800,1] #[min,min,m]


	return errModel


'''
createGST string
IN: UTC, preciosnModel
OUT: changed string

NOTE: code is only valid for EU
I assume N/S orientation of Error Elipse and that it is equal to lat,lon

0  Message ID \$GPGST
1  UTC of position fix
2  RMS value of the pseudorange or carrier phase (RTK/PPP) residuals
3  Error ellipse semi-major axis 1 sigma error, in meters
4  Error ellipse semi-minor axis 1 sigma error, in meters
5  Error ellipse orientation, degrees from true north
6  Latitude 1 sigma error, in meters
7  Longitude 1 sigma error, in meters
8  Height 1 sigma error, in meters
9  The checksum data, always begins with *
'''

def createGST(UTC,precModel):

	# TODO: set elipse erorr orient 80+-5
	errAz= round(80.00 + uniform(-3,3),2)
	RMS_res = round(1.70 + uniform(-1,1),2)
	latAcc,lonAcc,htAcc = precModel

	string = f'GPGST,{UTC},{RMS_res},{latAcc},{lonAcc},{errAz},{lonAcc},{lonAcc},{htAcc:.2f}'
	GSTstring= f'${string}*{calculateNMEAchecksum(string)}'
	return GSTstring


'''
alter RMC to match GGA

0	Message ID $GPRMC
1	UTC of position fix
2	Status A=active or V=void
3	Latitude
4	Longitude
5	Speed over the ground in knots
6	Track angle in degrees (True)
7	Date
8	Magnetic variation in degrees
9	The checksum data, always begins with *
'''
def changeRMC(RMCstring,GGAdata):

	RMCdata = RMCstring.split(",")
	RMCdata[3],RMCdata[5] = GGAdata[2],GGAdata[4]

	RMCstr = ','.join(RMCdata)
	RMCstr = correctNMEAcrc(RMCstr)

	return RMCstr

'''
read GGA and alter lat,lon,ht by adding noise,

IN: GGA string
OUT: changed GGA string,GGAdata(list)

0	Message ID $GPGGA
1	UTC of position fix
2	Latitude
3	Direction of latitude: N: North,S: South
4	Longitude
5	Direction of longitude: E: East,W: West
6	GPS Quality indicator:
	0: Fix not valid
	1: GPS fix
	2: Differential GPS fix, OmniSTAR VBS
	4: Real-Time Kinematic, fixed integers
	5: Real-Time Kinematic, float integers, OmniSTAR XP/HP or Location RTK
7	Number of SVs in use, range from 00 through to 24+
8	HDOP
9	Orthometric height (MSL reference)
10	M: unit of measure for orthometric height is meters
11	Geoid separation
12	M: geoid separation measured in meters
13	Age of differential GPS data record, Type 1 or Type 9. Null field when DGPS is not used.
14	Reference station ID, range 0000-4095. A null field when any reference station ID is selected and no corrections are received1.
15	The checksum data, always begins with *
'''
def changeGGA(line,precModelArray):

	data = line.split(",")
	#TODO split DD MM
	coords = [data[2],data[4]]
	latlon = [convertDDMMtoMM(string) for string in coords]
	coords = [*latlon,float(data[9])] #lat,lon,ht

	#add noise to value
	noise = createErrors(precModelArray)
	coords = np.array(coords) + noise

	# data[2],data[4],data[9] = [f'{item:.2f}' for item in coords]
	data[2],data[4], = [convertMMtoDDMM(item) for item in coords[:2]]
	data[9] = f'{coords[2]:.2f}'
	NMEAstr = ','.join(data)

	NMEAstr = correctNMEAcrc(NMEAstr)

	return NMEAstr,data




'''
read nmea
create output file with noise added and GST string

I assume that GGA string always comes before GPRMC
'''
def createNoisyFile(file,noiseLevel):

	outFile = f'{file[:-5]}_out_{noiseLevel}.NMEA'
	outF =  open(outFile, mode='w+')

	with open(file) as f:
		for line in f:
			if line.find('$GPGGA')==0: #find at start of line
				precModelArray = precModel(noiseLevel)
				NMEAstr,GGAdata = changeGGA(line,precModelArray)
				#add GST code
				UTC = GGAdata[1]
				NMEAstr =  f'{NMEAstr}{createGST(UTC,precModelArray)}\n'
				outF.write(NMEAstr)
			if line.find('$GPRMC')==0: #find at start of line
				str = changeRMC(line,GGAdata)
				outF.write(str)
	outF.close()
	return GGAdata



##################
####MAIN CODE
###################
if __name__ == "__main__":

    allFiles = glob.glob('*.nmea') #read all files

    for file in allFiles:
        createNoisyFile(file,5)
        createNoisyFile(file,1)
