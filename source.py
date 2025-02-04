import pandas as pd
import numpy as np
from numpy import asarray
import os, os.path
import sys
from urllib.request import (
    urlopen, urlretrieve)
import plotly.express as px
import datetime
from sklearn.metrics import mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots

min_max_scaler = MinMaxScaler()

def start_pipeline(dataf):
    return dataf.copy()


def create_BRC_MonthNum(dataf):
    conditions = [
        dataf['BRCMonth'] == "January",dataf['BRCMonth'] == "February",dataf['BRCMonth'] == "March",
        dataf['BRCMonth'] == "April",dataf['BRCMonth'] == "May",dataf['BRCMonth'] == "June",
        dataf['BRCMonth'] == "July",dataf['BRCMonth'] == "August",dataf['BRCMonth'] == "September",
        dataf['BRCMonth'] == "October",dataf['BRCMonth'] == "November",dataf['BRCMonth'] == "December"
    ]

    outputs = [i for i in range(1, 13)]

    dataf['BRCMonthNum'] = np.select(conditions, outputs)

    return dataf


def check_remove_dup(dataf):
    # Groups footfall data by location and datetime, counting the number of occurrences by calling size.
    # Also Resets the index to restore the grouped columns and renames the size column to UniqueRowsCount
    unq_loc_datetime = dataf.groupby(
        ['Location', 'DateTime']).size().reset_index().rename(columns={0: 'UniqueRowsCount'})
    unq_loc_datetime

    # Check to see if there are any values in the UniqueRowsCount column greater than one (indicating there are
    # duplicate rows)
    if len(unq_loc_datetime[unq_loc_datetime.UniqueRowsCount > 1]) > 1:
        # Drop duplicates from dataframe (amended from initial code to concentrate only on Location and DateTime).
        ffd_no_dup = dataf.drop_duplicates(subset=['Location', 'DateTime'])
        # Rerun duplicate check and print to console.
        unq_loc_datetime = ffd_no_dup.groupby(
            ['Location', 'DateTime']).size().reset_index().rename(columns={0: 'UniqueRowsCount'})
        print(f"There are {len(unq_loc_datetime[unq_loc_datetime.UniqueRowsCount > 1])} duplicates left")
        return ffd_no_dup
    else:
        return dataf



def time_dico():
    time_dico = {
        "interval": ["hours", "day", "week", "month", "year"],
        "code": ["%H", "%a", "%W", "%b", "%y"],
        "freq": ["H", "D", "W", "MS", "Y"]
    }
    return time_dico


def resample_day(data):

    data = data.resample("D").sum()
    data['weekday'] = data.index.dayofweek
    data['weekdayname'] = data.index.day_name()
    data = data.groupby(['weekday', 'weekdayname'])['Count'].agg(['sum', 'mean']).droplevel(level=0)

    return data


def resample_week(data):

    data = data.groupby(['BRCWeekNum'])['Count'].sum()

    return data


def resample_month(data):

    data = data.groupby(['BRCMonth'])['Count'].sum()

    return data


def resample_year(data):

    data = data.groupby(['BRCYear'])['Count'].sum()

    return data


def invalid_op(data):
    raise Exception("Invalid Time Frequency - Needs either 'day', 'week', 'month' or 'year'.")


def mean_hourly(dataf, freq):

    if freq == "day":
        dataf = dataf.groupby([
            pd.Grouper(key="DateTime",freq="D"),'BRCWeekNum','BRCMonth','BRCYear'])['Count'].aggregate(np.mean)
    elif freq == "month":
        dataf = dataf.groupby(
            ['BRCMonthNum',pd.Grouper(key="BRCMonth"),'BRCYear'])['Count'].aggregate(np.mean).reset_index()
    elif freq == "week":
        dataf = dataf.set_index('DateTime').groupby(
            [pd.Grouper(key="BRCWeekNum"),'BRCYear'])['Count'].aggregate(np.mean)
    elif freq == "year":
        dataf = dataf.set_index('DateTime').groupby(
            [pd.Grouper(key="BRCYear")])['Count'].aggregate(np.mean)

    return dataf

def remove_new_cameras(dataf):

    dataf.drop(dataf[ (dataf['Location'] == "Albion Street at McDonalds") & (dataf['Location'] == "Park Row")].index,inplace=True)

    return dataf

def reset_df_index(dataf):
    dataf = dataf.reset_index()
    return dataf

def set_dt_index(dataf):
    dataf = dataf.set_index('DateTime')

    return dataf

def date_range(dataf,startdate,enddate):

    dataf = dataf[(dataf.index >= startdate) & (dataf.index <= enddate)]

    return dataf

def per_change(dataf,freq):

    dataf[f'{freq}_per_change'] = dataf.Count.pct_change() * 100

    return dataf

def create_sum_df(data, time, year):
    freq = {
        "day": resample_day,
        "week": resample_week,
        "month": resample_month,
        "year": resample_year
    }

    data = data.set_index('DateTime')

    if year != "none":
        data = data.loc[data.BRCYear == year]

    resample_function = freq.get(time, invalid_op)

    return resample_function(data)

def mean_hourly_location(dataf,freq):

    if freq == "day":
        dataf = dataf.groupby(['Location',
            pd.Grouper(key="DateTime",freq="D"),'BRCWeekNum','BRCMonth','BRCYear'])['Count'].aggregate(np.mean)
    elif freq == "month":
        dataf = dataf.groupby(
            ['Location','BRCMonthNum',pd.Grouper(key="BRCMonth"),'BRCYear'])['Count'].aggregate(np.mean).reset_index()
    elif freq == "week":
        dataf = dataf.set_index('DateTime').groupby(
            ['Location',pd.Grouper(key="BRCWeekNum")])['Count'].aggregate(np.mean)
    elif freq == "year":
        dataf = dataf.set_index('DateTime').groupby(
            ['Location',pd.Grouper(key="BRCYear")])['Count'].aggregate(np.mean)

    return dataf

def set_lockdown_timeframe(dataf):
    dataf = dataf.loc[(dataf.BRCYear == 2020) | (dataf.BRCYear == 2021)]

    return dataf

def calculate_baseline(dataf):

    dataf['Day_Name'] = dataf.index.day_name()

    dataf = dataf.groupby([pd.Grouper(level='DateTime', freq="D"), 'Day_Name'])[
        'Count'].sum().reset_index()
    dataf = dataf.set_index('DateTime')

    baseline = (dataf
                .pipe(start_pipeline)
                .pipe(date_range, "2020-01-03", "2020-03-05"))

    baseline = baseline.groupby([pd.Grouper(key="Day_Name")])['Count'].aggregate(np.median)

    dataf = dataf.loc[dataf.index > "2020-03-05"]
    dataf.loc[:, 'baseline'] = dataf.Day_Name.map(baseline.to_dict())
    dataf.loc[:, 'baseline_change'] = dataf.Count - dataf.baseline
    dataf.loc[:, 'baseline_per_change'] = (dataf.baseline_change / dataf.baseline) * 100

    return dataf

def chart_lockdown_dates(fig):
    # Create a dictionary of annotation parameters for the Plotly vertical lines
    vline_anno = {"date": ['2020-03-16',
                           '2020-03-23',
                           '2020-06-01',
                           '2020-06-15',
                           '2020-07-04',
                           '2020-08-03',
                           '2020-09-22',
                           '2020-10-14',
                           '2020-11-02',
                           '2020-11-05',
                           '2020-12-02',
                           '2021-01-05',
                           '2021-03-08',
                           '2021-03-29',
                           '2021-04-12'],

                  "text2" : ['(1)','(2)','(3)','(4)','(5)','(6)','(7)','(8)','(9)','(10)','(11)','(12)','(13)','(14)','(15)'],

                  "showarrow": [True, False, False, False, False, False, False, False, True, False, False, False,
                                False, True,False]
                  }
    # Create a dictionary of annotation parameters for the Plotly vertical rectangles
    vrec_anno = {"x0": ['2020-03-23', '2020-06-15', '2020-11-05', '2020-12-02', '2021-01-05', '2021-03-29'],
                 "x1": ['2020-06-15', '2020-11-05', '2020-12-02', '2021-01-05', '2021-03-29', '2021-04-25'],
                 "fillcolor": ['red', 'orange', 'red', 'orange', 'red', 'orange']
                 }

    for i, date in enumerate(vline_anno['date']):
        fig.add_vline(
            x=datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() * 1000,
            line_color="green", line_dash="dash",
            annotation_position="top",
            annotation=dict(text=vline_anno['text2'][i],
                            font_size=8,
                            textangle=0,
                            showarrow=vline_anno['showarrow'][i],
                            arrowhead=1)
        )

    for i, x0 in enumerate(vrec_anno['x0']):
        fig.add_vrect(
            x0=datetime.datetime.strptime(x0, "%Y-%m-%d").timestamp() * 1000,
            x1=datetime.datetime.strptime(vrec_anno['x1'][i], "%Y-%m-%d").timestamp() * 1000,
            fillcolor=vrec_anno['fillcolor'][i], opacity=0.25, line_width=0)

    return fig

def combine_cameras(dataf):
    cameras_to_combine = dataf.loc[dataf.Location.isin(["Commercial Street at Lush",
                                                        "Commercial Street at Sharps"])]

    total_when_seperate = sum(cameras_to_combine['Count'])

    dataf = dataf.replace({'Location': {'Commercial Street at Lush': 'Commercial Street Combined',
                                        'Commercial Street at Sharps': 'Commercial Street Combined'}})

    total_combined = sum(dataf.loc[dataf.Location == "Commercial Street Combined", "Count"])

    if total_when_seperate == total_combined:
        print("Footfall hasn't changed when combining cameras")
    else:
        print("Footfall has changed when combining cameras")

    return dataf


def set_start_date(dataf,date):
    dataf = dataf.loc[dataf.DateTime >= date]

    return dataf



def hosp_indoor(dataf):

    dataf['hosp_indoor'] = 3
    dataf.loc[(dataf.index >= '2020-03-20') & (dataf.index < '2020-06-15'),'hosp_indoor'] = 1
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2020-11-02'), 'hosp_indoor'] = 2
    dataf.loc[(dataf.index >= '2020-11-02') & (dataf.index < '2021-05-17'),'hosp_indoor'] = 1


    return dataf

def hosp_outdoor(dataf):

    dataf['hosp_outdoor'] = 3
    dataf.loc[(dataf.index >= '2020-03-20') & (dataf.index < '2020-06-15'),'hosp_outdoor'] = 1
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2020-11-02'),'hosp_outdoor'] = 2
    dataf.loc[(dataf.index >= '2020-11-02') & (dataf.index < '2021-04-12'),'hosp_outdoor'] = 1


    return dataf

def hotels(dataf):

    dataf['hotels'] = 4
    dataf.loc[(dataf.index >= '2020-03-26') & (dataf.index < '2020-07-04'),'hotels'] = 1
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-11-02'), 'hotels'] = 3
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'),'hotels'] = 1
    dataf.loc[(dataf.index >= '2020-11-02') & (dataf.index < '2020-11-05'), 'hotels'] = 2
    dataf.loc[(dataf.index >= '2020-12-02') & (dataf.index < '2021-01-06'),'hotels'] = 2
    dataf.loc[(dataf.index >= '2021-01-06') & (dataf.index < '2021-05-17'), 'hotels'] = 1

    return dataf

def ent_indoor(dataf):

    #default value of open with no restrictions
    dataf['ent_indoor'] = 5

    #full closure until reopening on 4th July 2020
    dataf.loc[(dataf.index >= '2020-03-20') & (dataf.index < '2020-07-04'), 'ent_indoor'] = 1

    #reopens on 4th July with up to 30 people legally allowed until rule of 6 legally introduced on 14th Sept 2020
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'ent_indoor'] = 4

    #open with rule of 6 until 14th October 2020 when put into tier 2
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-10-14'),'ent_indoor'] = 3

    #open but only with household until 2nd November when put into tier 3
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2021-11-02'), 'ent_indoor'] = 2

    #full closed after being put in tier 3, through national lockdown 2, Christmas in tier 3 and national lockdown 3.
    dataf.loc[(dataf.index >= '2020-11-02') & (dataf.index < '2021-05-17'), 'ent_indoor'] = 1

    #Reopens to rule of 6 on 17th May 2020
    dataf.loc[(dataf.index >= '2021-05-17'),'ent_indoor'] = 3

    return dataf

def ent_outdoor(dataf):

    # default value of open with no restrictions
    dataf['ent_outdoor'] = 5

    # full closure until reopening on 4th July 2020
    dataf.loc[(dataf.index >= '2020-03-20') & (dataf.index < '2020-07-04'), 'ent_outdoor'] = 1

    # reopens on 4th July with up to 30 people legally allowed until rule of 6 legally introduced on 14th Sept 2020
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'ent_outdoor'] = 5

    # open with rule of 6 until 5th november 2020 when national lockdown starts
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-11-05'), 'ent_outdoor'] = 3

    # full closure during 2nd national lockdown until put back into tier 3 on 2nd December 2020.
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'), 'ent_outdoor'] = 1

    # open with rule of 6 until 6th January 2021 when 3rd national lockdown starts
    dataf.loc[(dataf.index >= '2020-12-02') & (dataf.index < '2021-01-06'), 'ent_outdoor'] = 3

    # full closure during 3rd national lockdown until reopens on 12th April 2021
    dataf.loc[(dataf.index >= '2021-01-06') & (dataf.index < '2021-04-12'), 'ent_outdoor'] = 1

    # Reopens to rule of 6 on 12th April 2021
    dataf.loc[(dataf.index >= '2021-04-12'), 'ent_outdoor'] = 3

    return dataf

def weddings(dataf):

    # default value of Yes with no restrictions
    dataf['weddings'] = 5

    #Fully banned during lockdown 1 until restrictions eased on 4th July
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-07-04'), 'weddings'] = 1

    #Weddings of up to 30 people allowed
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-28'), 'weddings'] = 4

    #Weddings of up to 15 people allowed
    dataf.loc[(dataf.index >= '2020-09-28') & (dataf.index < '2020-11-05'), 'weddings'] = 3

    #Weddings banned during lockdown 2 until restrictions eased on 2nd December
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'), 'weddings'] = 1

    # Weddings of up to 15 people allowed until start of lockdown 3 in January 2021
    dataf.loc[(dataf.index >= '2020-12-02') & (dataf.index < '2021-01-06'), 'weddings'] = 3

    # Weddings banned during lockdown 3 until restrictions eased on 29th March 2021
    dataf.loc[(dataf.index >= '2021-01-05') & (dataf.index < '2021-03-29'), 'weddings'] = 1

    # Weddings of up to 6 people allowed until 12th April 2021
    dataf.loc[(dataf.index >= '2021-03-29') & (dataf.index < '2021-04-12'), 'weddings'] = 2

    # Weddings of up to 15 people allowed until 17th May 2021
    dataf.loc[(dataf.index >= '2021-04-12') & (dataf.index < '2021-05-17'), 'weddings'] = 3

    # Weddings of up to 30 people allowed until 21st June 2021
    dataf.loc[(dataf.index >= '2021-05-17') & (dataf.index < '2021-06-21'), 'weddings'] = 4

    return dataf

def self_acc(dataf):

    dataf['self_acc'] = 5

    #Fully banned during lockdown 1 until restrictions eased on 4th July
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-07-04'), 'self_acc'] = 1

    #Allowed with max legal limits of 30 people up to rule of 6 on 14th September
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'self_acc'] = 4

    #Rule of 6
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-10-14'), 'self_acc'] = 3

    #Household only
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2020-11-05'), 'self_acc'] = 2

    #Fully banned during lockdown 2 until special Christmas rules 24-26th December
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-24'), 'self_acc'] = 1

    #Special christmas rules allow more than one household of any size up to 3 households to get together.  Just classify as rule of 6 for the purposes of modelling
    dataf.loc[(dataf.index >= '2020-12-24') & (dataf.index < '2020-12-27'), 'self_acc'] = 3

    #Fully banned under tier 3 and all through national lockdown 3 until 12th April 2021
    dataf.loc[(dataf.index >= '2020-12-27') & (dataf.index < '2021-04-12'), 'self_acc'] = 1

    #Household only
    dataf.loc[(dataf.index >= '2021-04-12') & (dataf.index < '2021-05-17'), 'self_acc'] = 2

    #Household only
    dataf.loc[dataf.index >= '2021-05-17', 'self_acc'] = 2

    return dataf

def sport_lei_indoor(dataf):

    #Default values of open with no restrictions
    dataf['sport_lei_indoor'] = 5

    #Fully banned during lockdown 1 until restrictions eased on 25th July
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-07-25'), 'sport_lei_indoor'] = 1

    #Reopen legally for groups of up to 30 (although guidance states rule of 6)
    dataf.loc[(dataf.index >= '2020-07-25') & (dataf.index < '2020-09-14'), 'sport_lei_indoor'] = 4

    #Open with rule of 6
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-10-14'), 'sport_lei_indoor'] = 3

    #Household only
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2020-11-05'), 'sport_lei_indoor'] = 4

    #Fully banned during lockdown 2, through tier 3 and lockdown 3 until restrictions eased on 12 April
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2021-04-12'), 'sport_lei_indoor'] = 1

    #Open to household only
    dataf.loc[(dataf.index >= '2021-04-12'), 'sport_lei_indoor'] = 1

    return dataf

def sport_lei_outdoor(dataf):

    dataf['sport_lei_outdoor'] = 5

    #Fully banned during lockdown 1 until restrictions eased on 4th July
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-07-04'), 'sport_lei_outdoor'] = 1

    #No restrictions on organised sport or leisure organised formally
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-11-05'), 'sport_lei_outdoor'] = 5

    #Fully banned during lockdown 2, through tier 3 until restrictions eased on
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2021-03-29'), 'sport_lei_outdoor'] = 1

    #Fully banned during lockdown 1 until restrictions eased on 4th July
    dataf.loc[(dataf.index >= '2021-03-29'), 'sport_lei_outdoor'] = 5

    return dataf

def non_essential_retail(dataf):

    dataf['non_ess_retail'] = 1

    #Fully closed during lockdown 1 until restrictions eased on 15th June
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-06-15'), 'non_ess_retail'] = 0

    #Fully closed during lockdown  until restrictions eased on 2nd December
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'), 'non_ess_retail'] = 0

    #Fully closed during lockdown 3 until restrictions eased on 12th April
    dataf.loc[(dataf.index >= '2021-01-05') & (dataf.index < '2021-04-12'), 'non_ess_retail'] = 0

    return dataf

def primary_schools(dataf):

    dataf['prim_sch'] = 1

    #Fully closed during lockdown 1 until restrictions eased on 1st June 2020
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-06-01'), 'prim_sch'] = 0

    #Fully closed during lockdown 3 until restrictions eased on 8th March 2021
    dataf.loc[(dataf.index >= '2021-01-06') & (dataf.index < '2021-03-08'), 'prim_sch'] = 0

    return dataf

def secondary_schools(dataf):

    dataf['sec_sch'] = 1

    #Fully closed during lockdown until restrictions eased on
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-06-15'), 'sec_sch'] = 0

    #Fully closed during lockdown until restrictions eased on
    dataf.loc[(dataf.index >= '2021-01-06') & (dataf.index < '2021-03-08'), 'sec_sch'] = 0

    return dataf

def university(dataf):

    #Open or blended learning
    dataf['uni_campus'] = 1

    #Mostly closed during lockdown until start of 2020/2021 academic year
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-09-01'), 'uni_campus'] = 0

    #Mostly closed during lockdown 3 until restrictions eased on 17th May
    dataf.loc[(dataf.index >= '2021-01-05'), 'uni_campus'] = 0

    return dataf

def outdoor_grp_public(dataf):

    dataf['outdoor_grp_public'] = 5

    #Max two people gathering outside of household
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-06-01'), 'outdoor_grp_public'] = 2

    #Max 6 people gathering
    dataf.loc[(dataf.index >= '2020-06-01') & (dataf.index < '2020-07-04'), 'outdoor_grp_public'] = 3

    #Max 30 people gathering (although rule of 6 as 'guidance')
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'outdoor_grp_public'] = 4

    #Rule of 6 becomes legal
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-11-05'), 'outdoor_grp_public'] = 3

    #Max two people gathering outside of household
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'), 'outdoor_grp_public'] = 2

    #Rule of 6
    dataf.loc[(dataf.index >= '2020-12-02') & (dataf.index < '2021-01-05'), 'outdoor_grp_public'] = 3

    #Max two people gathering outside of household
    dataf.loc[(dataf.index >= '2021-01-05') & (dataf.index < '2021-03-29'), 'outdoor_grp_public'] = 2

    #Rule of 6
    dataf.loc[(dataf.index >= '2021-03-29'), 'outdoor_grp_public'] = 3

    return dataf

def outdoor_grp_private(dataf):

    dataf['outdoor_grp_private'] = 5

    # Max two people gathering outside of household
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-06-01'), 'outdoor_grp_private'] = 2

    #Max 6 people gathering
    dataf.loc[(dataf.index >= '2020-06-01') & (dataf.index < '2020-07-04'), 'outdoor_grp_private'] = 3

    #Max 30 people gathering (although rule of 6 as 'guidance')
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'outdoor_grp_private'] = 4

    #Rule of 6 becomes legal
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-11-02'), 'outdoor_grp_private'] = 3

    #Household only
    dataf.loc[(dataf.index >= '2020-11-02') & (dataf.index < '2020-11-05'), 'outdoor_grp_private'] = 1

    #Max two people gathering outside of household
    dataf.loc[(dataf.index >= '2020-11-05') & (dataf.index < '2020-12-02'), 'outdoor_grp_private'] = 2

    #Household only
    dataf.loc[(dataf.index >= '2020-12-02') & (dataf.index < '2021-03-29'), 'outdoor_grp_private'] = 1

    #Rule of 6
    dataf.loc[(dataf.index >= '2021-03-29'), 'outdoor_grp_private'] = 3

    return dataf

def indoor_grp(dataf):

    dataf['indoor_grp'] = 4

    # Household group only
    dataf.loc[(dataf.index >= '2020-03-23') & (dataf.index < '2020-07-04'), 'indoor_grp'] = 1

    #Max 30 people gathering (although rule of 6 as 'guidance')
    dataf.loc[(dataf.index >= '2020-07-04') & (dataf.index < '2020-09-14'), 'indoor_grp'] = 3

    #Rule of 6
    dataf.loc[(dataf.index >= '2020-09-14') & (dataf.index < '2020-10-14'), 'indoor_grp'] = 2

    #Household only
    dataf.loc[(dataf.index >= '2020-10-14') & (dataf.index < '2020-12-24'), 'indoor_grp'] = 1

    #Special christmas rules allow more than one household of any size up to 3 households to get together.  Just classify as rule of 6 for the purposes of modelling
    dataf.loc[(dataf.index >= '2020-12-24') & (dataf.index < '2020-12-27'), 'indoor_grp'] = 2

    #Household only
    dataf.loc[(dataf.index >= '2020-12-27'), 'indoor_grp'] = 1

    return dataf

def eat_out(dataf):

    dataf['eat_out'] = 0

    #Eat out to Help out scheme active, encouraging people to go and use hospitality venues.
    dataf.loc[(dataf.index >= '2020-08-03') & (dataf.index <= '2020-08-31'), 'eat_out'] = 1

    return dataf


def create_lockdown_predictors(dataf):

    lockdown_var_list = [hosp_indoor,
                         hosp_outdoor,
                         hotels,
                         ent_indoor,
                         ent_outdoor,
                         weddings,
                         self_acc,
                         sport_lei_indoor,
                         sport_lei_outdoor,
                         non_essential_retail,
                         primary_schools,
                         secondary_schools,
                         university,
                         outdoor_grp_public,
                         outdoor_grp_private,
                         indoor_grp,
                         eat_out]

    for func in lockdown_var_list:
        dataf = func(dataf)

    return dataf

def validation_plot(y,yhat):
    # plot expected vs predicted
    fig = make_subplots()
    # Add traces
    fig.add_trace(
        go.Scatter(x=pd.Series(y).index, y=pd.Series(y), name="Expected",mode='lines',hovertemplate='%{y}'),
    )
    fig.add_trace(
        go.Scatter(x=pd.Series(y).index, y=pd.Series(yhat), name="Predicted",mode='lines',hovertemplate='%{y}'),
    )

    # Set x-axis title
    fig.update_xaxes(title_text="Time Series (Day)")

    # Set y-axes titles
    fig.update_yaxes(title_text="Daily Footfall")

    return fig

def movecol(df, cols_to_move=[], ref_col='', place='After'):

    cols = df.columns.tolist()
    if place == 'After':
        seg1 = cols[:list(cols).index(ref_col) + 1]
        seg2 = cols_to_move
    if place == 'Before':
        seg1 = cols[:list(cols).index(ref_col)]
        seg2 = cols_to_move + [ref_col]

    seg1 = [i for i in seg1 if i not in seg2]
    seg3 = [i for i in cols if i not in seg1 + seg2]

    return(df[seg1 + seg2 + seg3])

# Function to process date and recreate it in a different format
def create_date_format (col, old_time_format, new_time_format):
    col = pd.to_datetime(col, format = old_time_format )
    if type(col) == pd.core.series.Series:
        col = col.apply(lambda x: x.strftime(new_time_format))
    elif type(col) ==  pd.tslib.Timestamp:
        col = col.strftime(new_time_format)
    return col

def create_weather_predictors(dataf,new_weather,previous_weather):
    """Create weather dataset and normalise values across the same range.

    PARAMETERS:
      - weather 1 is a pandas dataframe containing combined weather data from the NCAS archive from 01/04/2017.
      - weather 2 is a pandas dataframe containing weather data from a previous intern project up to 31/03/2017.
    """

    new_weather = new_weather.loc[new_weather.index >'2017-03-31']
    new_weather = new_weather.resample("D").agg({'temp_°C':'mean',
                                                'rain_mm': 'sum',
                                                "wind_ms¯¹": 'mean'})
    new_weather = new_weather.rename(columns={'temp_°C':'mean_temp',
                                                'rain_mm': 'rain',
                                                "wind_ms¯¹": 'wind_speed'})
    previous_weather = previous_weather.drop(['abnormal_rain','high_temp',	'low_temp','high_wind'],axis=1)

    comb_weather = pd.concat([previous_weather,new_weather])

    #Either interpolate missing data or drop.  Decide after consultations.
    #comb_weather = comb_weather.interpolate(method='time')
    comb_weather = comb_weather.dropna()

    dataf = dataf.merge(comb_weather,how='left',left_on=dataf.index,right_on=comb_weather.index).set_index('key_0')

    return dataf


def create_date_predictors(dataf):

    #dataf['year'] = pd.DatetimeIndex(dataf.index).year
    dataf['month'] = pd.DatetimeIndex(dataf.index).month_name()
    dataf['dayofweek'] = pd.DatetimeIndex(dataf.index).day_name()

    #dataf = pd.get_dummies(dataf, columns=['year'], drop_first=True, prefix='year')
    dataf = pd.get_dummies(dataf, columns=['month'], drop_first=True, prefix='month')
    dataf = pd.get_dummies(dataf, columns=['dayofweek'], drop_first=True, prefix='wday')

    return dataf

def create_holiday_predictors(dataf,bankholdf,schooltermdf):
    bankholdf['bank_hols'] = 1

    schooltermdf['schoolholidays'] = np.where(schooltermdf['schoolStatus']=='Close',1,0)
    schooltermdf = schooltermdf.loc[schooltermdf.index >= '2008'].sort_index()
    schooltermdf = schooltermdf.asfreq('D')
    schooltermdf.ffill(inplace=True)

    dataf = dataf.merge(bankholdf, left_on=dataf.index,right_on='ukbankhols',how='left')
    dataf = dataf.set_index('ukbankhols')
    dataf.bank_hols = dataf.bank_hols.fillna(0)

    dataf = dataf.merge(schooltermdf,how='left',left_on=dataf.index,right_on=schooltermdf.index).set_index('key_0').drop(['schoolStatus'],axis=1)

    return dataf

#The following workflow performs some data management to account for the dataframe requiring transformation into a numpy array to work with the walk forward validation code
def arrange_cols(dataf,n_in):
#Extract columns that need moving for walk forward validation later
    #cols_to_move = [col for col in dataf.iloc[:,0:7]] DEPRECATED, MAY NEED IN FutureWarning
    cols_to_move = []
    n_in = n_in+1
    for i in range(1,n_in):
        cols_to_move.append(f'var1(t-{i})')

    cols_to_move.append('var1(t)')
    #Identify reference column as last column
    ref_col = [col for col in dataf.iloc[:,-1:]][0]

    #Calls a function that moves specified columns to the end of the dataframe.
    dataf = movecol(dataf,
                 cols_to_move=cols_to_move,
                 ref_col=ref_col,
                 place='After')

    return dataf

def drop_na(dataf):

    dataf = dataf.dropna()

    return dataf

# transform a time series dataset into a supervised learning dataset
def series_to_supervised(data, n_in=1, n_out=1, dropnan=True):
    n_vars = 1 if type(data) is list else data.shape[1]
    df = pd.DataFrame(data)
    cols,names = list(),list()
    # input sequence (t-n, ... t-1)
    for i in range(n_in, 0, -1):
        cols.append(df.shift(i))
        names += [('var%d(t-%d)' % (j+1, i)) for j in range(n_vars)]
    # forecast sequence (t, t+1, ... t+n)
    for i in range(0, n_out):
        cols.append(df.shift(-i))
        if i == 0:
            names += [('var%d(t)' % (j+1)) for j in range(n_vars)]
        else:
            names += [('var%d(t+%d)' % (j+1, i)) for j in range(n_vars)]
    # put it all together
    agg = pd.concat(cols, axis=1)
    agg.columns = names
    # drop rows with NaN values
    if dropnan:
        agg.dropna(inplace=True)
    return agg

# split a univariate dataset into train/test sets
def train_test_split(data, n_test):
    return data.iloc[:-n_test, :].copy(), data.iloc[-n_test:, :].copy()

# fit an random forest model and make a one step prediction
def random_forest_forecast(train, testX,tree):
    # transform list into array
    train = asarray(train)
    # split into input and output columns
    trainX, trainy = train[:, :-1], train[:, -1]
    # fit model
    model = RandomForestRegressor(n_estimators=tree)
    model.fit(trainX, trainy)
    # make a one-step prediction
    yhat = model.predict([testX])
    return yhat[0]

# walk-forward validation for univariate data - NEEDS SOME WORK TO ADAPT FOR REFITTING SCALING TO TRAINING DATA AND APPLYING TO TEST
def walk_forward_validation(data, n_test, scalecols,n_in,tree):
    print(f'Validation has started on {tree} trees with {n_in} time lag(s).  Please be patient, it may take a while and a message will be displayed when finished.')
    predictions = list()

    # split dataset
    train, test = train_test_split(data, n_test)
    #scale numerical data
    train.loc[:,scalecols] = min_max_scaler.fit_transform(train.loc[:,scalecols])
    test.loc[:,scalecols] = min_max_scaler.transform(test.loc[:,scalecols])
    #rearrange columns and record variable names in a dictionary
    train, test = arrange_cols(train,n_in), arrange_cols(test,n_in)
    #convert dataframes to numpy arrays
    train, test = train.values, test.values
    # seed history with training dataset
    history = [x for x in train]
    # step over each time-step in the test set
    for i in range(len(test)):
        # split test row into input and output columns
        testX, testy = test[i, :-1], test[i, -1]
        # fit model on history and make a prediction
        yhat = random_forest_forecast(history, testX,tree)
        # store forecast in list of predictions
        predictions.append(yhat)
        # add actual observation to history for the next loop
        history.append(test[i])
        # summarize progress
        #print(i,'>expected=%.1f, predicted=%.1f' % (testy, yhat))
    # estimate prediction error
    error = mean_absolute_error(test[:, -1], predictions)
    return error, test[:, -1], predictions

def create_prediction_data(yhatdf,test):
    yhatdf = pd.DataFrame(yhatdf)
    test = test.reset_index()

    yhatdf['datetime'] = test['key_0']
    yhatdf = yhatdf.set_index('datetime').rename(columns={0:'predicted'})
    yhatdf['roll_7_mean'] = yhatdf['predicted'].rolling(7).mean()

    return yhatdf

def daily_predicted_chart(yhat_list,finaldata):
    finaldata = finaldata.loc[finaldata.index >= '2018']
    fig = make_subplots()

    # Add traces
    fig.add_trace(
        go.Scatter(x=finaldata.index, y=finaldata['roll_7_mean'], name="Observed"),
    )

    fig.add_trace(
        go.Scatter(x=yhat_list[0].index, y=yhat_list[0]['roll_7_mean'], name="Predicted_1_lag"),
    )

    fig.add_trace(
        go.Scatter(x=yhat_list[1].index, y=yhat_list[1]['roll_7_mean'], name="Predicted_3_lag"),
    )

    fig.add_trace(
        go.Scatter(x=yhat_list[2].index, y=yhat_list[2]['roll_7_mean'], name="Predicted_7_lag"),
    )

    # Add figure title
    fig.update_layout(
        title_text="Rolling 7 day mean predictions"
    )

    # Set x-axis title
    fig.update_xaxes(title_text="DateTime")

    # Set y-axes titles
    fig.update_yaxes(title_text="Footfall")

    return fig

def weekly_predicted_chart(yhat_dataf,finaldata):
    finaldata = finaldata.loc[finaldata.index >= '2018']
    finaldata = finaldata.resample('W').agg({'var1(t)':'sum'})
    yhat_dataf = yhat_dataf.resample('W').agg({'predicted':'sum'})
    # Create figure with secondary y-axis
    fig = make_subplots()

    # Add traces
    fig.add_trace(
        go.Scatter(x=finaldata.index, y=finaldata['var1(t)'], name="yaxis data", connectgaps=False),
    )

    fig.add_trace(
        go.Scatter(x=yhat_dataf.index, y=yhat_dataf['predicted'], name="yaxis2 data",connectgaps=False),
    )

    # Add figure title
    fig.update_layout(
        title_text="Double Y Axis Example"
    )

    # Set x-axis title
    fig.update_xaxes(title_text="xaxis title")

    # Set y-axes titles
    fig.update_yaxes(title_text="<b>primary</b> yaxis title", secondary_y=False)
    fig.update_yaxes(title_text="<b>secondary</b> yaxis title", secondary_y=True)

    return fig

def monthly_predicted_chart(yhat_dataf,finaldata):
    finaldata = finaldata.loc[finaldata.index >= '2019']
    finaldata = finaldata.resample('M').agg({'var1(t)':'sum'})
    yhat_dataf = yhat_dataf.resample('M').agg({'predicted':'sum'})
    # Create figure with secondary y-axis
    fig = make_subplots()

    # Add traces
    fig.add_trace(
        go.Scatter(x=finaldata.index, y=finaldata['var1(t)'], name="yaxis data", connectgaps=False),
    )

    fig.add_trace(
        go.Scatter(x=yhat_dataf.index, y=yhat_dataf['predicted'], name="yaxis2 data",connectgaps=False),
    )

    # Add figure title
    fig.update_layout(
        title_text="Double Y Axis Example"
    )

    # Set x-axis title
    fig.update_xaxes(title_text="xaxis title")

    # Set y-axes titles
    fig.update_yaxes(title_text="<b>primary</b> yaxis title", secondary_y=False)
    fig.update_yaxes(title_text="<b>secondary</b> yaxis title", secondary_y=True)

    return fig

def create_data_cols(dataf):
    data_cols = [col for col in dataf] #List containing column names from daily dataframe
    data_col_keys = list(range(len(data_cols))) # List containing integer positions of dataframe columns

    #Creates a dictionary of column names with integer keys representing position
    data_col_dict = dict(zip(data_col_keys, data_cols))

    return data_col_keys, data_cols


def create_importance_df(feature_import,datacols,lag):
    importance = pd.DataFrame(feature_import)
    importance['feature_name'] = datacols[:-1]
    importance = importance.set_index('feature_name')
    importance = importance.rename(columns={0:f'feat_importance_lag{lag}'}).sort_values(by=f'feat_importance_lag{lag}',ascending=False)

    return importance