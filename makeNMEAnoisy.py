'''
LKB 2019(c)
FLAMINGO toolset

Read NMEA $GPGGA and $GPRMC and adds noise
Outputs $GPGGA,$GPRMC,$GPGST strings




NOTE:

$GPGGA lat, long is in   DDMM.MMMMM (2cm accuracy)
talker ID: $GP - GPS, $GL - GLO, $GN - combined
$GPRMC is required for Google Earth. GE is also checking CRC


WARNING: There are a lot of assumptions in the code. It was not fully tested.

This code is only valid for Europe
In GST
 residuals are hardcoded to pseudorange residuals
 Error ellipse orientation is assumed to be ~75-85deg from north (correct in multipath free European locations).
 Folowing the same assumptions lat == semi-major and lon == semi-minor



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
convert from NMEA DDMM to minutes only for calculation

IN: str (D)DDMM.xx
OUT: MM.MMMMMMM


'5256.546' == 3176.546
'''
def convertDDMMtoMM(coordinateString):

	if coordinateString.find('.')==4: #DDMM.xx
		coord = int(coordinateString[:2])*60+float(coordinateString[2:])
	elif coordinateString.find('.')==5: #DDDMM.xx
		coord = int(coordinateString[:3])*60+float(coordinateString[3:])
	else:
		raise ValueError(f'lat,lon is not encoded properly (expected degrees as 2 or 3 digits), got {coordinateString}')
	return coord


'''
IN: MM.MMMMM
OUT: str DDMM.MMMMM
3rd decimal place is 2m, 5th is 2cm, 6th is 2mm
3176.546 == '5256.54600'
'''
def convertMMtoDDMM(coordinateVal):
	from math import floor

	DD = floor(coordinateVal/60)
	MM = coordinateVal-DD*60
	return f'{DD:03}{MM:02.5f}'


'''
Calculate distance for lat,lon,ht at given lat
that can be used to estimate how distance on the sphere [m,m,m] translate into
lat,lon,ht in [min,min,m]
earthRadius - as defined in ITRF2014 [m]
IN: lat of area under consideration location [deg]
OUT: np array of scale: [m,m,m]->[min,min,m]

NOTE: you only need latitude of Location, it works for small area only
'''
def calcPlanarScale(latOfLocation,earthRadius=6378137.0):

  earthCircle = 2 * earthRadius * np.pi
  latLenght = earthCircle / (60*360)  #in [min] !
  scaleToPlanar = 1/np.array([latLenght * np.cos(latOfLocation * np.pi / 180),latLenght, 1])

  return scaleToPlanar


#### NOISE CALCULUS

'''
translate noise level to precision model in [m]
N-S lat (\Phi)
E-W lon (\Lambda)

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
create error (noise) at 1sigma (68% distribution) and distribute it to N/E part of ellipse
for more details check <https://www.gpsworld.com/gpsgnss-accuracy-lies-damn-lies-and-statistics-1134/>

IN:  [precLat,precLon,precHt] [m]
OUT: [errLat,errLon,errHt] [min,min,m]

TODO: consider more advanced error model
'''
def createErrors(precModelArray,latOfLocation,probability=0.68):
	precModelArray = np.array(precModelArray)
	#baloon prec to acc and split around 0
	accCoefficient = 1+(1-probability)/2
	accModel = accCoefficient*precModelArray/2
	errModel =[uniform(-acc,acc) for acc in accModel] #in m

	# errModel = np.array(errModel)*[1/1200,1/1800,1] #[min,min,m] TEST FOR UK
	errModel = np.array(errModel)*calcPlanarScale(latOfLocation) #[min,min,m]

	return errModel


'''
createGST string
IN: UTC, preciosnModel
OUT: changed string

NOTE: code is only valid for EU
I assume N/S orientation of Error Elipse and that it is equal to lat,lon
'''
def createGST(UTC,precModel):

	# TODO: set elipse erorr orient 80+-5
	errAz= round(80.00 + uniform(-3,3),2)
	RMS_res = round(1.70 + uniform(-1,1),2)
	latAcc,lonAcc,htAcc = precModel

	string = f'GPGST,{UTC},{RMS_res},{latAcc},{lonAcc},{errAz},{lonAcc},{lonAcc},{htAcc:.2f}'
	GSTstring= f'${string}*{calculateNMEAchecksum(string)}'
	return GSTstring



####I/O FUNCTIONS


'''
alter RMC to match GGA

'''
def changeRMC(RMCstring,GGAdata):

	RMCdata = RMCstring.split(",")
	RMCdata[3],RMCdata[5] = GGAdata[2],GGAdata[4]

	#TODO alter f5,6 accordingly to the noise, 
	#TODO-7 check f2,f8

	RMCstr = ','.join(RMCdata)
	RMCstr = correctNMEAcrc(RMCstr)

	return RMCstr

'''
read GGA and alter lat,lon,ht by adding noise,

IN: GGA string
OUT: changed GGA string,GGAdata(list)

'''
def changeGGA(line,precModelArray):

	data = line.split(",")
	#TODO split DD MM
	coords = [data[2],data[4]]
	latlon = [convertDDMMtoMM(string) for string in coords]
	coords = [*latlon,float(data[9])] #lat,lon,ht

	#add noise to value
	lat = coords[0]/60
	noise = createErrors(precModelArray,lat)
	coords = np.array(coords) + noise

	# data[2],data[4],data[9] = [f'{item:.2f}' for item in coords]
	data[2],data[4], = [convertMMtoDDMM(item) for item in coords[:2]]
	data[9] = f'{coords[2]:.2f}'
	NMEAstr = ','.join(data)

	NMEAstr = correctNMEAcrc(NMEAstr)

	return NMEAstr,data




'''
read NMEA file (GGA,RMC)
add noise, create GST string
get RMC and match GST - needed for Google Earth

IN: NMEA file, noise level [m]
OUT: N/A

NOTE:
I assume that GGA string always comes before GPRMC (!)
'''
def createNoisyFile(file,noiseLevel):

	outFile = f'{file[:-5]}_out_{noiseLevel}.NMEA'
	outF =  open(outFile, mode='w+')

	with open(file) as f:
		for line in f:
			if line.find('$GPGGA')==0: #find at start of line
				precModelArray = precModel(noiseLevel)
				NMEAstr,GGAdata = changeGGA(line,precModelArray)
				#add GST
				UTC = GGAdata[1]
				NMEAstr =  f'{NMEAstr}{createGST(UTC,precModelArray)}\n'
				outF.write(NMEAstr)
			if line.find('$GPRMC')==0: #find at start of line
				str = changeRMC(line,GGAdata)
				outF.write(str)
	outF.close()




##################
####MAIN CODE
###################
if __name__ == "__main__":

	allFiles = glob.glob('.\data\*.nmea')
	print(allFiles)

	for file in allFiles:
			createNoisyFile(file,5)
			createNoisyFile(file,1)
