#!/usr/bin/python
#####
# this script uses PyPROSAIL and Py6S to model canopy reflectance
# for a suite of vegetation types for use in unmixing models and in
# canopy reflectance inversions
#
# c. 2016-2017 Christopher Anderson
#####

import numpy as np
import pyprosail
import aei as aei
import random
import spectral as spectral
from Py6S import *

# load sixs
s = SixS()

#####
# set up output files and processing parameters
#####

# set output file names
output_base = aei.params.environ['AEI_GS'] + '/scratch/spectral_libraries/veg_bundles'
output_sli = output_base + '.sli'
output_hdr = output_base + '.hdr'
output_csv = output_base + '.csv'
output_md = output_base + '_md.csv'

# set lists to update through processing
output_spec = []
output_metadata = []
output_metadata.append('N (arb), chloro (ug/cm2), caroten (ug/cm2), brown (arb),\
    EWT (cm), LMA (g/cm2), soil_reflectance (%), LAI (arb), hot_spot (arb), \
    s_za (deg), s_az (deg), v_za (deg), v_az (deg), bimodality (?), inclination (?)')

# set number of random veg, bundles to simulate
n_bundles = 2000

# set the number of output bands (default prosail is 2101)
nb = 2101

#####
# set up the leaf and canopy modeling parameters
#####

N = []
chloro = []
caroten = []
brown = []
EWT = []
LMA = []
soil_reflectance = []
LAI = []
hot_spot = []
LAD_inclination = []
LAD_bimodality = []
s_az = []
s_za = []
v_az = []
v_za = []

# loop through the bundles and generate random canopy parameters
for i in range(n_bundles):
    
    # structural coefficient (arbitrary units)
    #  range 1.3 - 2.5 from Rivera et al. 2013 http://dx.doi.org/10.3390/rs5073280
    N.append(random.uniform(1.3,2.5))

    # total chlorophyll content (ug/cm^2)
    #  range ~ 5 - 75 from Rivera et al. 2013, but i'll set a little more conservative
    chloro.append(random.gauss(35, 30))
    while chloro[-1] < 10 or chloro[-1] > 60:
        chloro[-1] = random.gauss(35, 30)

    # total carotenoid content (ug/cm^2)
    #  kinda fudged this to be like 1/4 of total chl
    caroten.append(random.gauss(8.75, 7.5))
    while caroten[-1] < 2 or caroten[-1] > 15:
        caroten[-1] = random.gauss(8.75, 7.5)

    # brown pigment content (arbitrary units) - not gonna mess with this
    brown.append(0)

    # equivalent water thickness (cm)
    #  range 0.002 - 0.05 from Rivera et al. 2013
    EWT.append(random.uniform(0.002, 0.05))

    # leaf mass per area (g/cm^2)
    #  global range 0.0022 - 0.0365 (median 0.01)
    #  from Asner et al. 2011 http://dx.doi.org/10.1016/j.rse.2011.08.020
    # gonna go a little more conservative
    LMA.append(random.gauss(0.012, 0.005))
    while LMA[-1] < 0.005 or LMA[-1] > 0.0250:
        LMA[-1] = random.gauss(0.012, 0.005)

    # soil reflectance metric (wet soil = 0, dry soil = 1)
    soil_reflectance.append(random.uniform(0,1))

    # leaf area index (unitless, cm^2 leaf area/cm^2 ground area)
    #  range 0.01 - 18.0 (5.5 mean) globally
    #  range 0.2 - 8.7 (3.6 mean) for crops
    #  range 0.6 - 2.8 (1.3 mean) for desert plants
    #  range 0.5 - 6.2 (2.6 mean) for boreal broadleaf forest
    #  range 0.5 - 8.5 (4.6 mean) for boreal needle forest
    #  range 0.8 - 11.6 (5.1 mean) for temperate broadleaf forest
    #  range 0.01 - 15.0 (5.5 mean) for temperate needle forest
    #  range 0.6 - 8.9 (4.8 mean) for tropical broadleaf forest
    #  range 0.3 - 5.0 (1.7 mean) for grasslands
    #  range 1.6 - 18.0 (8.7 mean) for plantations
    #  range 0.4 - 4.5 (2.1 mean) for shrublands
    #  range 0.2 - 5.3 (1.9 mean) for tundra
    #  range 2.5 - 8.4 (6.3 mean) for wetlands
    #  from Asner, Scurlock and Hicke 2003 http://dx.doi.org/10.1046/j.1466-822X.2003.00026.x
    LAI.append(random.gauss(4,2))
    while LAI[-1] < 0.5 or LAI[-1] > 15:
        LAI[-1] = random.gauss(3,2)

    # hot spot parameter (derived from brdf model)
    #  range 0.05-0.5 from Rivera et al. 2013
    hot_spot.append(random.uniform(0.05, 0.5))

    # leaf distribution function parameter.
    #  range LAD_inc -0.4 -  0.4, LAD_bim -0.1 - 0.2 for trees
    #  range LAD_inc -0.1 -  0.3, LAD_bim  0.3 - 0.5 for lianas
    #  range LAD_inc -0.8 - -0.2, LAD_bim -0.1 - 0.3 for palms
    #  from Asner et al. 2011
    LAD_inclination.append(random.uniform(-0.4, 0.4))
    LAD_bimodality.append(random.uniform(-0.1, 0.2))

    # viewing and solar angle parameters
    #  solar zenith ranges cludged from http://gis.stackexchange.com/questions/191692/maximum-solar-zenith-angle-for-landsat-8-images
    #  I couldn't find good data on the range of possible solar or viewing azimuth.
    #  I decided to set view parameters to 0 to assume nice, clean nadir viewing, and let the sun vary.
    s_za.append(random.uniform(20, 70))
    s_az.append(random.uniform(0,360))
    v_az.append(0)
    v_za.append(0)

#####
# set up the loop for each atmosphere/canopy model
#####

# first create the output array that will contain all the resulting spectra
output_array = np.zeros([nb, (n_bundles) + 1])

# loop through each veg / wood / soil bundle
for j in range(n_bundles):
    
    # load prosail and run the canopy model
    LIDF = (LAD_inclination[j], LAD_bimodality[j])
    spectrum = pyprosail.run(N[j], chloro[j], caroten[j],  
                brown[j], EWT[j], LMA[j], soil_reflectance[j], 
                LAI[j], hot_spot[j], s_za[j], s_az[j],
                v_za[j], v_az[j], LIDF)

    # add the modeled spectrum to the output array
    output_array[:, (j+1)] = spectrum[:,1]
    
    # add a new name to label in the output spectral library
    output_spec.append('veg bundle ' + str(j+1))
    
    # update the metadata list with a string of parameters
    output_metadata.append("{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}".format(
        N[j], chloro[j], caroten[j], brown[j], EWT[j], LMA[j], soil_reflectance[j], 
        LAI[j], hot_spot[j], s_za[j], s_az[j], v_za[j], v_az[j], LIDF[0], LIDF[1]))
    
# now that the loop has finished we can export our results to a csv file
output_array[:, 0] = spectrum[:,0]
np.savetxt(output_csv, output_array.transpose(), delimiter=",", fmt = '%.3f')
    
# output a spectral library
with open(output_sli, 'w') as f: 
    output_array[:,1:].transpose().tofile(f)

# write the ENVI header file for the spectral library    
metadata = {
    'samples' : nb,
    'lines' : n_bundles,
    'bands' : 1,
    'data type' : 5,
    'header offset' : 0,
    'interleave' : 'bsq',
    'byte order' : 0,
    'sensor type' : 'prosail',
    'spectra names' : output_spec,
    'wavelength units' : 'micrometers',
    'wavelength' : output_array[:,0]
    }
spectral.envi.write_envi_header(output_hdr, metadata, is_library=True)

with open(output_md, 'w') as f:
    for line in output_metadata:
        f.write("{line}\n".format(line = line))