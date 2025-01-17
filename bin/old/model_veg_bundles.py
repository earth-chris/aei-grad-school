#####
# this script uses PyPROSAIL and Py6S to model canopy reflectance
# for a suite of vegetation types for use in unmixing models and in
# canopy reflectance inversions
#
# c. 2016 Christopher Anderson
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

# set output file base name (will have _speclib.csv, _speclib.sli, 
#  _speclib.hdr, and _atm_x.sixs appended for the csv, spectral library, 
#  and sixs outputs with x as the atmospheric iteration)
output_base = aei.params.environ['AEI_GS'] + '/scratch/spectral_libraries/sr_test_fullrange_veg_bundles'

# set number of random atmospheres to simulate
n_atmospheres = 1

# set number of random veg, bundles to simulate
n_bundles = 100

#####
# set up the spectral output parameters
#####

# specify the output sensor configuration for modeled spectra
#  options include ali, aster, er2_mas, gli, landsat_etm, landsat_mss, landsat_oli,
#  landsat_tm, meris, modis, polder, spot_hrv, spot_vgt, vnir, whole_range, and custom
target_sensor = 'landsat_oli'

# set up output wavelengths (in um) if using custom wl range (ignored for pre-defined sensors)
wl_start = 0.4
wl_end = 2.5
wl_interval = 0.01
wl = np.arange(wl_start, wl_end, wl_interval)
wl_sixs = Wavelength(wl_start, wl_end)

# set up output type (an option from s.outputs)
#  examples include pixel_radiance, pixel_reflectance, apparent_radiance, apparent_reflectance, etc.
output_type = 'pixel_reflectance'

#####
# set up atmospheric modeling parameters
#####

# select the atmospheric profile (an option from AtmosProfile)
#  examples include Tropical, MidlatitudeSummer, MidlatitudeWinter, etc.
atmos_profile = [AtmosProfile.Tropical]
atmos_profile_ind = np.random.randint(0,len(atmos_profile)-1,n_atmospheres)

# select the aerosol profile to use (an option from AeroProfile)
#  examples include BiomassBurning, Continental, Desert, Maritime, NoAerosols, Urban, etc.
aero_profile = [AeroProfile.Continental]
aero_profile_ind = np.random.randint(0,len(aero_profile)-1,n_atmospheres)

# select ground reflectance method (an option from GroundReflectance)
#  examples include GreenVegetation, Hetero(/Homo)geneousLambertian, HotSpot, LeafDistPlanophile, etc
ground_reflectance = [GroundReflectance.HomogeneousLambertian]
ground_reflectance_ind = np.random.randint(0,len(ground_reflectance)-1,n_atmospheres)

# set altitudes for sensor (ground) and target (target altitude for modeled reflectance)
#  Landsat 4, 5, 7, 8 altitude - 705 km 
altitudes = Altitudes()
#altitudes.set_sensor_custom_altitude(705)
altitudes.set_sensor_satellite_level()
altitudes.set_target_sea_level()
s.altitudes = altitudes

# set aerosol optical thickness (550 nm)
aot = aei.fn.randomFloats(n_atmospheres, 0.3, 0.7)

# select viewing geometry parameters
geo = Geometry.User()
solar_a = aei.fn.randomFloats(n_atmospheres, 0, 0) 
solar_z = aei.fn.randomFloats(n_atmospheres, 0, 0)
view_a = aei.fn.randomFloats(n_atmospheres, 0, 0)
view_z = aei.fn.randomFloats(n_atmospheres, 0, 0)
#solar_a = aei.fn.randomFloats(n_atmospheres, 0, 359) 
#solar_z = aei.fn.randomFloats(n_atmospheres, 10, 45)
#view_a = aei.fn.randomFloats(n_atmospheres, 0, 5) - 2.5
#view_z = aei.fn.randomFloats(n_atmospheres, 0, 1)

# set view geometry to nadir for prosail, so the radiative transfer
#  stuff is handled by sixs
solar_a_prosail = 0
solar_z_prosail = 0
view_a_prosail = 0
view_z_prosail = 0

# convert view azimuth to 0-360 scale
view_a[(view_a < 0)] = view_a[(view_a < 0)] + 360

#####
# set up the leaf and canopy modeling parameters
#####

# structural coefficient (arbitrary units)
#  range 1.3 - 2.5 from Rivera et al. 2013 http://dx.doi.org/10.3390/rs5073280
#N = aei.fn.randomFloats(n_bundles, 1.3, 2.5)
N = []
for i in range(n_bundles):
    N.append(random.gauss(1.9,0.3))

# total chlorophyll content (ug/cm^2)
#  range ~ 5 - 75 from Rivera et al. 2013
#chloro = aei.fn.randomFloats(n_bundles, 10, 60)
chloro = []
for i in range(n_bundles):
    chloro.append(random.gauss(30, 15))

# total carotenoid content (ug/cm^2)
caroten = aei.fn.randomFloats(n_bundles, 8, 8)

# brown pigment content (arbitrary units)
brown = aei.fn.randomFloats(n_bundles, 0, 0)

# equivalent water thickness (cm)
#  range 0.002 - 0.05 from Rivera et al. 2013
#EWT = aei.fn.randomFloats(n_bundles, 0.002, 0.05)
EWT = []
for i in range(n_bundles):
    EWT.append(random.gauss(0.025, 0.01))

# leaf mass per area (g/cm^2)
#  global range 0.0022 - 0.0365 (median 0.01)
#  from Asner et al. 2011 http://dx.doi.org/10.1016/j.rse.2011.08.020
#LMA = aei.fn.randomFloats(n_bundles, 0.005, 0.035)
LMA = []
for i in range(n_bundles):
    LMA.append(random.gauss(0.012, 0.005))

# soil reflectance metric (wet soil = 0, dry soil = 1)
soil_reflectance = aei.fn.randomFloats(n_bundles, 0, 0)

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
#LAI = aei.fn.randomFloats(n_bundles, 0.6, 12.0)
LAI = []
for i in range(n_bundles):
    LAI.append(random.gauss(5,2.5))

# hot spot parameter (derived from brdf model)
#  range 0.05-0.5 from Rivera et al. 2013
#hot_spot = aei.fn.randomFloats(n_bundles, 0.05, 0.5)
hot_spot = []
for i in range(n_bundles):
    hot_spot.append(random.gauss(0.25, 0.1))

# leaf distribution function parameter.
#  range LAD_inc -0.4 -  0.4, LAD_bim -0.1 - 0.2 for trees
#  range LAD_inc -0.1 -  0.3, LAD_bim  0.3 - 0.5 for lianas
#  range LAD_inc -0.8 - -0.2, LAD_bim -0.1 - 0.3 for Palms
#  from Asner et al. 2011
#LAD_inclination = aei.fn.randomFloats(n_bundles, 0., 0.8) - 0.4
#LAD_bimodality = aei.fn.randomFloats(n_bundles, 0., 0.3) - 0.1
LAD_inclination = []
LAD_bimodality = []
for i in range(n_bundles):
    LAD_inclination.append(random.gauss(0, 0.2))
    LAD_bimodality.append(random.gauss(0.05, 0.05))

# old leaf inclination parameters based on fixed canopy architecture. options include:
# Planophile, Erectophile, Plagiophile, Extremophile, Spherical, Uniform
# LIDF = [pyprosail.Planophile, pyprosail.Uniform]
# LIDF_ind = np.random.random_integers(0,len(LIDF)-1,n_iterations)

#####
# set up if statements to set parameters based on sesnsor type
#####
if target_sensor == 'custom':
    run_sixs_params = SixSHelpers.Wavelengths.run_wavelengths
    num_bands = len(wl)
    good_bands = np.arange(num_bands)
elif target_sensor == 'ali':
    run_sixs_params = SixSHelpers.Wavelengths.run_ali
    num_bands = 7
    good_bands = np.arange(num_bands)
elif target_sensor == 'aster':
    run_sixs_params = SixSHelpers.Wavelengths.run_aster
    num_bands = 9
    good_bands = np.arange(num_bands)
elif target_sensor == 'er2_mas':
    run_sixs_params = SixSHelpers.Wavelengths.run_er2_mas
    num_bands = 7
    good_bands = np.arange(num_bands)
elif target_sensor == 'gli':
    run_sixs_params = SixSHelpers.Wavelengths.run_gli
    num_bands = 30
    good_bands = np.arange(num_bands)
elif target_sensor == 'landsat_etm':
    run_sixs_params = SixSHelpers.Wavelengths.run_landsat_etm
    num_bands = 6
    good_bands = np.arange(num_bands)
elif target_sensor == 'landsat_mss':
    run_sixs_params = SixSHelpers.Wavelengths.run_landsat_mss
    num_bands = 4
    good_bands = np.arange(num_bands)
elif target_sensor == 'landsat_oli':
    run_sixs_params = SixSHelpers.Wavelengths.run_landsat_oli
    num_bands = 10
    # use only the 6 traditional optical bands
    good_bands = np.arange(6)+1
elif target_sensor == 'landsat_tm':
    run_sixs_params = SixSHelpers.Wavelengths.run_landsat_tm
    num_bands = 6
    good_bands = np.arange(num_bands)
elif target_sensor == 'meris':
    run_sixs_params = SixSHelpers.Wavelengths.run_meris
    num_bands = 16
    good_bands = np.arange(num_bands)
elif target_sensor == 'modis':
    run_sixs_params = SixSHelpers.Wavelengths.run_modis
    num_bands = 8
    good_bands = np.arange(num_bands)
elif target_sensor == 'polder':
    run_sixs_params = SixSHelpers.Wavelengths.run_polder
    num_bands = 8
    good_bands = np.arange(num_bands)
elif target_sensor == 'spot_hrv':
    run_sixs_params = SixSHelpers.Wavelengths.run_spot_hrv
    num_bands = 4
    good_bands = np.arange(num_bands)
elif target_sensor == 'spot_vgt':
    run_sixs_params = SixSHelpers.Wavelengths.run_spot_vgt
    num_bands = 4
    good_bands = np.arange(num_bands)
elif target_sensor == 'vnir':
    run_sixs_params = SixSHelpers.Wavelengths.run_vnir
    num_bands = 200
    good_bands = np.arange(num_bands)
elif target_sensor == 'whole_range':
    run_sixs_params = SixSHelpers.Wavelengths.run_whole_range
    num_bands = 380
    # use only 400-2500 nm range
    good_bands = np.arange(210)+20
else:
    raise OSError('Unsupported sensor configuration')

nb = len(good_bands)

#####
# set up the output file and band names
#####
output_csv = []
output_sli = []
output_hdr = []
output_sixs = []
output_spec = []

output_csv.append(output_base + '_speclib.csv')
output_sli.append(output_base + '_speclib.sli')
output_hdr.append(output_base + '_speclib.hdr')

for i in range(n_atmospheres):
    output_sixs.append(output_base + '_atm_%02d.sixs' % (i+1))
    
for i in range(n_bundles):
    output_spec.append('Veg. bundle ' + str(i+1))
    
#####
# set up the loop for each atmosphere/canopy model
#####

# first create the output array that will contain all the resulting spectra
output_array = np.zeros([nb, (n_bundles * n_atmospheres) + 1])

for i in range(n_atmospheres):
    
    # set the sixs atmosphere profile
    s.aero_profile = AeroProfile.PredefinedType(aero_profile[aero_profile_ind[i]])
    s.atmos_profile = AtmosProfile.PredefinedType(atmos_profile[atmos_profile_ind[i]])
    s.aot550 = aot[i]
    geo.solar_a = solar_a[i]
    geo.solar_z = solar_z[i]
    geo.view_a = view_a[i]
    geo.view_z = view_z[i]
    s.geometry = geo
    ground_refl = ground_reflectance[ground_reflectance_ind[i]]
    
    # loop through each veg / wood / soil bundle
    for j in range(n_bundles):
        
        # load prosail and run the canopy model
        LIDF = (LAD_inclination[j], LAD_bimodality[j])
        spectrum = pyprosail.run(N[j], chloro[j], caroten[j],  
                    brown[j], EWT[j], LMA[j], soil_reflectance[j], 
                    LAI[j], hot_spot[j], solar_z_prosail, solar_a_prosail,
                    view_z_prosail, view_a_prosail, LIDF)

        # set the prosail modeled spectrum as ground spectrum in sixs                            
        s.ground_reflectance = ground_refl(spectrum)
    
        # generate the output spectrum
        if target_sensor == 'custom':
            wavelengths, results = run_sixs_params(s, wl, output_name = output_type)
        else:
            wavelengths, results = run_sixs_params(s, output_name = output_type)
    
        # convert output to array for ease of output
        results = np.asarray(results)
        
        # add the modeled spectrum to the output array
        output_array[:, (i * n_bundles) + j + 1] = results[good_bands]
    
    # write the sixs parameters for this run to output file
    s.write_input_file(output_sixs[i])
    

# now that the loop has finished we can export our results to a csv file
wavelengths = np.asarray(wavelengths)
output_array[:, 0] = wavelengths[good_bands]
np.savetxt(output_csv[0], output_array.transpose(), delimiter=",")
    
# output a spectral library
with open(output_sli[0], 'w') as f: 
    output_array[:,1:].transpose().tofile(f)
    
metadata = {
    'samples' : nb,
    'lines' : (n_bundles * n_atmospheres),
    'bands' : 1,
    'data type' : 5,
    'header offset' : 0,
    'interleave' : 'bsq',
    'byte order' : 0,
    'sensor type' : target_sensor,
    'spectra names' : output_spec,
    'wavelength units' : 'micrometers',
    'wavelength' : wavelengths[good_bands]
    }
spectral.envi.write_envi_header(output_hdr[0], metadata, is_library=True)
