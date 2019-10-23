# NMEAnoiseMaker

This tool is adding artificial noise to NMEA string

### workflow

Tool reads NMEA $GPGGA and

* adds noise to lat,lon,ht from $GPGGA
* create $GPGST string
* read $GPRMC and match lat,lon with $GPGGA


LKB 2019(c)


## NMEA strings 

### GGA


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

### GST

0  Message ID $GPGST
1  UTC of position fix
2  RMS value of the pseudorange or carrier phase (RTK/PPP) residuals
3  Error ellipse semi-major axis 1 sigma error, in meters
4  Error ellipse semi-minor axis 1 sigma error, in meters
5  Error ellipse orientation, degrees from true north
6  Latitude 1 sigma error, in meters
7  Longitude 1 sigma error, in meters
8  Height 1 sigma error, in meters
9  The checksum data, always begins with *

### RMC

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