import os

import pandas as pd, numpy as np

import pvlib
from pvlib.pvsystem import PVSystem
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

__temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

__pvwatts_system = PVSystem(
    module_parameters={'pdc0': 240, 'gamma_pdc': -0.004},
    inverter_parameters={'pdc0': 240},
    temperature_model_parameters = __temperature_model_parameters)



naive_times = pd.date_range(start='1981', end='1990', freq='1h',closed='left')
#as Asia/Kolkata
times = naive_times.tz_localize('Etc/Greenwich') 


df_ghi  = pd.read_csv("Raw_SSRD_63Locations_1981.csv", header = None)*1000
df_temp = pd.read_csv("63Locations_2mTempC_1981.csv", header = None)
df_wind = pd.read_csv("Wind_1m_63Locations_1981.csv", header = None)

# need to add empty row since time series has 78888 rows and these ghi/temp/wind datasets only have 78887
df_ghi = df_ghi.append(pd.Series(), ignore_index = True).set_index(times)
df_temp = df_temp.append(pd.Series(), ignore_index = True).set_index(times)
df_wind = df_wind.append(pd.Series(), ignore_index = True).set_index(times)


df_locations = pd.read_csv('63Locations.csv')


for i, lat, lon, alt, state in df_locations.itertuples():

    location = Location(latitude = lat, 
                        longitude = lon, 
                        altitude = alt, 
                        name = state)

    mc = ModelChain(__pvwatts_system, location, aoi_model = 'physical', spectral_model = 'no_loss')

    solpos = pvlib.solarposition.pyephem(times, 
                                     latitude = lat, 
                                     longitude = lon, 
                                     altitude = alt, 
                                     pressure = 101325, 
                                     temperature = df_temp[i].mean(), 
                                     horizon = '+0:00')


    df_res = pd.concat([df_ghi[i].rename('ghi'), df_temp[i].rename('temp_air'), df_wind[i].rename('wind_speed'), solpos['zenith']], axis = 1)

    # # list comprehension is slightly faster than apply
    # df_res['dni'] = df_res.apply(lambda row: pvlib.irradiance.disc(row.ghi, row.zenith, row.name)['dni'], axis = 1).astype(np.float64)
    df_res['dni'] = pd.Series([pvlib.irradiance.disc(ghi, zen, i)['dni'] for ghi, zen, i in zip(df_res['ghi'], df_res['zenith'], df_res.index)]).astype(np.float64)
    df_res['dhi'] = df_res['ghi'] - df_res['dni']*np.cos(np.radians(df_res['zenith']))

    weather = df_res.drop('zenith', axis = 1)

    mc.run_model(weather)

    df_acdc = pd.concat((mc.ac.rename('AC'), mc.dc.rename('DC')), axis = 1)

    df_acdc.to_csv(f"solar_AC_DC_location_{i}.csv")


    
