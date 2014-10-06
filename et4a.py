#!/usr/bin/python
# discussion: http://apicommunity.wunderground.com/weatherapi/topics/envirotranspiration
# original script: https://gist.github.com/anonymous/7f52c4d04f1a5658dace written by davemiedema
# Formula to calculate ET: http://www.fao.org/docrep/x0490e/x0490e08.htm
# process to determine effect of cloud cover on SR:  http://www.shodor.org/os411/courses/_master/tools/calculators/solarrad/

# RUN THIS SCRIPT AFTER MIDNIGHT THE DAY OF WATERING.  Doing so will ensure the correct ET factor is applied.
# Two separate tasks are performed here.  One is to calculate the ET and to suggest to Homeseer what ratio from normal to irrigate.
# Second task is to track the water balance.  The balance will be maintained at zero unless insufficient irrigation occurs or 
# there is more rainfall than the grass requires.  The script ignores factors effecting water balance for more than two days.
# Homeseer will not run sprinklers if rain is forecasted for today(the 24 hours after midnight) or tomorrow (the 48 hours after midnight).

# Download and install:  simplejson-3.6.3.tar.gz and  ActivePython-2.5.5.7-win32-x86.msi  Those work with Homeseer HS2 and at least Windows 7.


import urllib, sys, math, time, os, smtplib;

try:
    import json
except ImportError:
    import simplejson as json    #simplejson needed for Pyton 2.5

from datetime import date, timedelta, datetime
from email.mime.text import MIMEText

#the following 5 lines for Homeseer
def Main():
    print
HS_ET_Dev = "T17"  # Yesterday's ET value.  Does not consider water surplus or deficit.
HS_WR_Dev = "T18"  # Today's Watering Ratio.  Snevl Sprinklers does not currently support a variable watering adjustment needed for Watering Ratio.
HS_IR_Dev = "T19"  # Today's Irrigation amount in mm
Norm_ET = 6.0      # in mm. This is an estimate of the average amount of water needed during the 'watering months' (aka average ET).  Goal is to
                   # use this figure to adjust from this amount - up or down taking into account: 'yesterday's ET, surplus, and deficit.
HS_RT_Dev = "D1"   # Rain Tomorrow so no sprinkling today. This is for 'Summer Schedule' in Homeseer. Assumes Watering Ratio not available.
HS_RT1_Dev = "D2"  # Rain Tomorrow so no sprinkling today.  This is for 'Spring/Fall Schedule' in Homeseer.  Assumes Watering Ratio not available.

# Location constant
GMTOFFSET = 5
LATITUDE = 39.08
LONGITUDE = -94.58
COUNTRY = "KS"     # or State
CITY = "Shawnee_Mission"
KEY = "Your Key"      # get your key at Weatherunderground.  They are free.  But there are daily limits and rate limits.
level = 1   #debug level.  0 gives a summary.  1 & 2 gives progressively more info.
window = 5 #number of days to go back into the history to compute deficit/surplus.  maybe computing deficit or surplus from more than 2 days ago, has no value.

#assign global variables. Be sure to add global ref in functions.
H2oTom = 0 #probability of precip tomorrow.
H2oTod = 0 #probability of precip today.
forecast = 0 # predicted rainfall tomorrow.

try:
  os.chdir("Scripts")   #Changes the cwd when in Homeseer
except:
  pass

# Mapping of conditions to a level of cloud cover.  These can be adjusted for accuracy.
conditions = {
  "Blowing Snow"                   :8,
  "Clear"                          :0,
  "Fog"                            :5,
  "Haze"                           :2,
  "Heavy Blowing Snow"             :9,
  "Heavy Fog"                      :9,
  "Heavy Low Drifting Snow"        :10,
  "Heavy Rain"                     :10,
  "Heavy Rain Showers"             :10,
  "Heavy Thunderstorms and Rain"   :10,
  "Light Drizzle"                  :10,
  "Light Freezing Rain"            :10,
  "Light Ice Pellets"              :10,
  "Light Rain"                     :10,
  "Light Rain Showers"             :10,
  "Light Snow"                     :10,
  "Light Snow Grains"              :10,
  "Light Snow Showers"             :10,
  "Light Thunderstorms and Rain"   :10,
  "Low Drifting Snow"              :10,
  "Mist"                           :3,
  "Mostly Cloudy"                  :8,
  "Overcast"                       :10,
  "Partial Fog"                    :2,
  "Partly Cloudy"                  :5,
  "Patches of Fog"                 :2,
  "Rain"                           :10,
  "Rain Showers"                   :10,
  "Scattered Clouds"               :4,
  "Shallow Fog"                    :3,
  "Snow"                           :10,
  "Snow Showers"                   :10,
  "Thunderstorm"                   :10,
  "Thunderstorms and Rain"         :10,
  "Unknown"                        :5,  
}

# Print an attribute
def printAttr(indata, name, uiname):
  print "  " + uiname + " " + str(indata[name])

# Get forecast data for the city.  This is used to tell Homeseer not to water 'today'
# Results used to suppress watering based on forecast rainfall
def getForecastData():
  forecastURL = 'http://api.wunderground.com/api/' + KEY + '/forecast/q/' + COUNTRY + '/' + CITY + '.json'
  response = urllib.urlopen(forecastURL).read();
  data = json.loads(response)

  # Forecast day.
  #day = 0    # today
  day = 1    # tomorrow

  if (level > 2):
    print
    print 'Forecast for ' + CITY + ', ' + COUNTRY + ' for today'
    printAttr(data['forecast']['simpleforecast']['forecastday'][0], "pop", "% Chance of rainfall Today")
    print
    print 'Forecast for ' + CITY + ', ' + COUNTRY + ' for tomorrow'
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['date'], "pretty", "Date")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['high'], "celsius", "High temp")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['low'], "celsius", "Low temp")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day], "maxhumidity", "High humidity")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day], "avehumidity", "Average humidity")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day], "minhumidity", "Low humidity")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['maxwind'], "kph", "Max wind")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['avewind'], "kph", "Average wind")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day]['qpf_allday'], "mm", "Daily rainfall")
    printAttr(data['forecast']['simpleforecast']['forecastday'][day], "pop", "% Chance of rainfall Tomorrow")

  global H2oTod
  H2oTod = float(data['forecast']['simpleforecast']['forecastday'][0]['pop'])    #today
  global H2oTom
  H2oTom = float(data['forecast']['simpleforecast']['forecastday'][1]['pop'])    #tomorrow
#  global forecast
  forecast = float(data['forecast']['simpleforecast']['forecastday'][day]['qpf_allday']['mm'])
  return forecast

# Returns a calculation of saturation vapour pressure based on temperature in degrees
def saturationVapourPressure(T):
  return 0.6108 * math.exp((17.27 * T) / (T + 237.3))

def getHistoricalData(forecast):

  totalBalance = 0
  for day in range(window, -1,-1):
    today = date.today() - timedelta(day)
    datestring = today.strftime("%Y%m%d")

    if (day < 0):     #delete file already downloaded to get most recent?    Was set to 4  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      try:
        os.remove("data/" + datestring)
      except OSError:
        pass

    try:            # first try to get one weather station's day's info from file already downloaded
      data = json.load(open("data/" + datestring))
      source = "file " + datestring
    except:
      #             http://api.wunderground.com/api/your key/history_20141003/q/KS/Shawnee_Mission.json
      historyURL = 'http://api.wunderground.com/api/' + KEY + '/history_' + datestring + '/q/' + COUNTRY + '/' + CITY + '.json'
      if (window > 4): time.sleep(10)    #don't exceed API rate limits
      response = urllib.urlopen(historyURL).read()
      cachefile = open("data/" + datestring, 'w')
      cachefile.write(response)
      cachefile.close()
      data = json.loads(urllib.urlopen(historyURL).read())
      source = historyURL

    thedate = date(int(data['history']['dailysummary'][0]['date']['year']),
                   int(data['history']['dailysummary'][0]['date']['mon']),
                   int(data['history']['dailysummary'][0]['date']['mday']))

    dayOfYear = thedate.timetuple().tm_yday

    # Calculate solar radiation for location
    totalSolarRadiation = 0
    totalClearSkyIsolation = 0
    sunnyHours = 0

    # Get the conditions for the 24 hours of the requested day
    for hour in range(0,24):
      # Sometimes data is missing for an hour.  If we don't find data, cloud cover will stay at
      # -1
      cloudCover = -1

      # Look through the historical data we have
      for period in range(0, len(data['history']['observations'])):

        # Look for our hour in the date
        if (int(data['history']['observations'][period]['date']['hour']) == hour):

          # If there are conditions in the data, get them, and find the percent cloud cover 
          # for this hour
          if (data['history']['observations'][period]['conds']):
            cloudCover = float(conditions[data['history']['observations'][period]['conds']])/10
            cloudCoverString = data['history']['observations'][period]['conds']
            break;

      # If we didn't find any conditions for this hour, assume the same conditions as the 
      # previous hour.  Sometimes we are missing early data, but this is usually at night
      # anyway, so we are safe
      if (cloudCover == -1): cloudCover = previousCloudCover
      previousCloudCover = cloudCover

      # If we have data
      if (cloudCover != -1):

        # Find out the angle of the sun was in the middle of this hour as a good
        # estimate
        gmtHour = hour + GMTOFFSET + 0.5
        fractionalDay = (360/365.25)*(dayOfYear+gmtHour/24)
        

        f = math.radians(fractionalDay)
        declination = 0.396372 - 22.91327  * math.cos(f) + 4.02543  * math.sin(f) - 0.387205 * math.cos(2 * f) + 0.051967 * math.sin(2 * f) - 0.154527 * math.cos(3 * f) + 0.084798 * math.sin(3 * f)
        timeCorrection = 0.004297 + 0.107029 * math.cos(f) - 1.837877 * math.sin(f) - 0.837378 * math.cos(2*f) - 2.340475*math.sin(2*f)
        solarHour = (gmtHour + 0.5 - 12)*15 + LONGITUDE + timeCorrection

        if (solarHour < -180): solarHour = solarHour + 360
        if (solarHour > 180): solarHour = solarHour - 360

        solarFactor = math.sin(math.radians(LATITUDE))*math.sin(math.radians(declination))+math.cos(math.radians(LATITUDE))*math.cos(math.radians(declination))*math.cos(math.radians(solarHour))

        sunElevation = math.degrees(math.asin(solarFactor))
        clearSkyInsolation = 990 * math.sin(math.radians(sunElevation))-30

        # Track the number of sunny hours
        if (cloudCover < 0.5 and clearSkyInsolation > 0): sunnyHours = sunnyHours + 1

        if (clearSkyInsolation < 0): clearSkyInsolation = 0
          
        solarRadiation = clearSkyInsolation * (1 - 0.75*(math.pow(cloudCover,3.4)))

        # Accumulate clear sky radiation and solar radiation on the ground
        totalSolarRadiation += solarRadiation
        totalClearSkyIsolation += clearSkyInsolation

# Per Hour Routine is finished.  Now to calculate results for this day.

    # Convert from Wh / m^2 / d 
    radiationAtSurface = totalSolarRadiation * 3600 / 1000 / 1000 # MJ / m^2 / d

    # m/s at 2m above ground
    windspeed = float(data['history']['dailysummary'][0]['meanwindspdm']) * 1000 / 3600  * 0.748
    pressure = float(data['history']['dailysummary'][0]['meanpressurem']) / 10 # kPa
    tempAvg = float(data['history']['dailysummary'][0]['meantempm']) # degrees C
    tempMin = float(data['history']['dailysummary'][0]['mintempm']) # degrees C
    tempMax = float(data['history']['dailysummary'][0]['maxtempm']) # degrees C
    humidMax = float(data['history']['dailysummary'][0]['maxhumidity']) # degrees C
    humidMin = float(data['history']['dailysummary'][0]['minhumidity']) # degrees C
    rainfall = float(data['history']['dailysummary'][0]['precipm']) # rainfall mm

    D = 4098 * saturationVapourPressure(tempAvg) / math.pow(tempAvg + 237.3,2)
    g = 0.665e-3 * pressure
    es = (saturationVapourPressure(tempMin) + saturationVapourPressure(tempMax)) / 2
    ea = saturationVapourPressure(tempMin) * humidMax / 200 + saturationVapourPressure(tempMax) * humidMin / 200
    vaporPressDeficit = es - ea

    ETo = ((0.408 * D * radiationAtSurface) + (g * 900 * windspeed * vaporPressDeficit) / (tempAvg + 273)) / (D + g * (1 + 0.34 * windspeed))


    #the following 'open file' routine works with Python 2.5. Each daily file holds mm of irrigation for that day. data for this
    #file could come from the sprinkler controller itself or from this script.

    yesterday = date.today() - timedelta(day +1)
    datestringy = yesterday.strftime("%Y%m%d")

    if (day == window):  # this is the first day of the window.  Set values to '0' for the day before.
      beginBalancey = 0
      totalSolarRadiationy = 0
      EToy = 0
      ETry = 0
      EToiy = 0
      endBalancey = 0
    else:
      f = json.load(open("balance/" + datestringy + ".json", 'r'))  # open yesterday's local history file to obtain beginning balance and irrigation amt
                                                                    # file will be created if it does not exist.
      EToy = float(f['ET'])   # yesterday's ET
      EToiy = float(f['irrigation'])   # Actual irrigation yesterday in case a different than calculated irrigation took place and was entered.
      endBalancey = float(f['endBalance'])       # beginning balance on day of file before irrigation

    beginBalance = endBalancey
    ETr = EToy / Norm_ET   # Ratio determined with rainfall and balance considered.
    EToi = - beginBalance - rainfall + EToy  # Today's irrigation
    if (EToi < 0): EToi = 0
    endBalance = beginBalance - EToy + rainfall - EToi      # Use EToy here because it is yesterday's ET, which we will use to irrigate today

    #  fi = json.load(open("balance/" + datestring + ".json", 'wb'))
    fi = open("balance/" + datestring + ".json", "w")                 # write file.  NO reason to open ??
    fi.write("{\" beginBalance\":\"" + str('%.2g'%(beginBalance)) +
     "\",\n\"SR\":\"" + str('%.4g'%(totalSolarRadiation)) +
     "\",\n\"ET\":\"" + str('%.2g'%(ETo)) +                            #today's ET
     "\",\n\"Ratio\":\"" + str('%.2g'%(ETr)) +
     "\",\n\"irrigation\":\"" + str('%.2g'%(EToi)) +
     "\",\n\"endBalance\":\"" + str('%.5g'%(endBalance)) +
     "\"}")
    fi.close()
    print

    if (day == 1):     # now calculating today's data before it is complete
      ETo1 = ETo # Yesterday's ET
      totalSolarRadiation1 = totalSolarRadiation
      EToi1 = EToi  # - totalBalance # Yesterday's Final ET adjusted for yesterday's rainfall and balance
      if (EToi1 < 0): EToi1 = 0  # assumes this will be today's irrigation amount
      #ETr is the ratio of normal watering required. Factors: ET, Rainfall, Forecasted Rainfall, and prior watering
      ETr1 = EToi1 / Norm_ET   # Ratio determined with rainfall and balance considered.
      beginBalance1 = beginBalance # this will be written in "today's" file.
      endBalance1 = endBalance   #endbalance today

    if (level > 0):
      print
      print 'Data for ' + CITY + ', ' + COUNTRY + ' from ' + source + " on " + str(thedate)
      if (day == 0): print " (current day is incomplete)"

      print "  Begin balance " + '%.3g'%(beginBalance)
      print "  Using Yesterday ET " + '%.2g'%(EToy)
      print "  Irrigation " +  '%.3g'%(EToi)
      print "  Rainfall " +  '%.2g'%(rainfall)
      print "  Evapotranspiration " + '%.2g'%(ETo)
      print "  Ending balance " + '%.3g'%(endBalance)
      print "  Solar Radiation " + '%.4g'%(totalSolarRadiation)
      print "  Sunny hours " + str(sunnyHours)
      print "  Clear Sky Solar Radiation " + '%.4g'%(totalClearSkyIsolation)


    if (level > 1):
      printAttr(data['history']['dailysummary'][0], "maxtempm", "High temp")
      printAttr(data['history']['dailysummary'][0], "meantempm", "Average temp")
      printAttr(data['history']['dailysummary'][0], "mintempm", "Low temp")
      printAttr(data['history']['dailysummary'][0], "maxhumidity", "High humidity")
      printAttr(data['history']['dailysummary'][0], "minhumidity", "Low humidity")
      printAttr(data['history']['dailysummary'][0], "maxwspdm", "Max wind")
      printAttr(data['history']['dailysummary'][0], "meanwindspdm", "Average wind")
      printAttr(data['history']['dailysummary'][0], "minwspdm", "Min wind")
      printAttr(data['history']['dailysummary'][0], "precipm", "Daily rainfall")
      printAttr(data['history']['dailysummary'][0], "meanpressurem", "Average air pressure")

      print "  ground windspeed " + '%.2g'%(windspeed)

    if (level > 2):
      print "  D " + '%.2g'%(D)
      print "  g " + '%.2g'%(g)
      print "  es " + '%.2g'%(es)
      print "  ea " + '%.2g'%(ea)
      print "  Vapor Pressure Deficit " + '%.2g'%(vaporPressDeficit)
      print "  Radiation at surface " + '%.2g'%(radiationAtSurface)

# The Per Day Routine is finished. Now to print results

  global H2oTod
  global H2oTom

  try:
    hs.WriteLog("Debug","H2oTom: " + str(H2oTom)+ "%. H2oToday: " + str(H2oTod) + '%')
    hs.WriteLog("Debug","Yesterday\'s ET & SR: " + '%.2g'%(EToy) + " mm & " + str('%.4g'%(totalSolarRadiationy)) + ". Today\'s Ratio and Irrigation: " + str('%.3g'%(ETr)) + " & " + str('%.2g'%(EToi))+ " mm ")
    hs.SetDeviceString(HS_ET_Dev,'%.2g'%(EToy))  # Yesterday's ET
    hs.SetDeviceString(HS_WR_Dev,'%.3g'%(ETr))  # Today's watering Ratio
    hs.SetDeviceString(HS_IR_Dev,'%.2g'%(EToi)) # Today's irrigation amount in mm

    if (H2oTom > 40 or H2oTod > 40 or EToi == 0):
      hs.SetDeviceString(HS_RT_Dev,"On")  # "On" Means "blocked'. Sprinklers won't run
      hs.SetDeviceString(HS_RT1_Dev,"On")  # "On" Means "blocked'. Sprinklers won't run
      hs.WriteLog("Debug","D1: On (sprinklers off) and D2: On (sprinklers off)")
    else:
      hs.SetDeviceString(HS_RT_Dev,"Off")    # Sprinklers will run
      hs.WriteLog("Debug","D1: Off (sprinklers run) and D2: Off (sprinklers run)")
  except:
    pass

  print
  print "Summary information"
  print "  H2oTom: " + str(H2oTom)+ "%. H2oToday: " + str(H2oTod) + '%'
  print "  Yesterday\'s ET & SR: " + '%.2g'%(EToy) + " mm & " + str('%.4g'%(totalSolarRadiationy)) + ". Today\'s Ratio and Irrigation: " + str('%.3g'%(ETr)) + " & " + str('%.3g'%(EToi))+ " mm "
  print "  Tomorrow's Forecast " + str(forecast)
#  print "  Balance over " + str(window) + " days = " + '%.2g'%(endBalance)

# Since this script is being run the morning just prior to irrigation, 
# the following saves yesterday's: tSR, ET, and totalBalance and today's Ratio and Irrigation amount.
  fi = open("balance/" + datestring + ".json", "wb")
  fi.write("{\" beginBalance\":\"" + str('%.3g'%(beginBalance1)) +
   "\",\n\"SR\":\"" + str('%.4g'%(totalSolarRadiation1)) +
   "\",\n\"ET\":\"" + str('%.2g'%(ETo1)) +
   "\",\n\"Ratio\":\"" + str('%.2g'%(ETr1)) +
   "\",\n\"irrigation\":\"" + str('%.2g'%(EToi1)) +
   "\",\n\"endBalance\":\"" + str('%.3g'%(endBalance1)) +
   "\"}")
  fi.close()

forecast = getForecastData()
getHistoricalData(forecast)