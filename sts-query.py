#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Nick Semenkovich <semenko@alum.mit.edu>.
#   https://nick.semenkovich.com/
#
# This software is released under the MIT License:
#  <https://opensource.org/licenses/mit-license.php>
#
# Source: https://github.com/semenko/sts-risk-calculator-cli

import argparse
import time

import requests

STS_API_URL = "https://riskcalc.sts.org/stswebriskcalc/v1/calculate/stsall"

# The required API parameters
STS_PARAMS_REQUIRED = ["age", "gender", "raceasian", "raceblack", "racenativeam", "racnativepacific", "ethnicity", "payorprim", "payorsecond",
"surgdt", "weightkg", "heightcm", "hct", "wbc", "platelets", "creatlst", "dialysis", "hypertn", "immsupp", "pvd", "cvd", "cvdtia", "cvdpcarsurg",
"mediastrad", "cancer", "fhcad", "slpapn", "liverdis", "unrespstat", "syncope", "diabetes", "diabctrl", "infendo", "infendty", "cva", "cvawhen",
"chrlungd", "cvdstenrt", "cvdstenlft", "ivdrugab", "alcohol", "pneumonia", "tobaccouse", "hmo2", "prcvint", "prcab", "prvalve", "prvalveproc1",
"prvalveproc2", "prvalveproc3", "prvalveproc4", "prvalveproc5", "poc", "pocint1", "pocint2", "pocint3", "pocint4", "pocint5", "pocint6", "pocint7",
"pocpci", "pocpciwhen", "pocpciin", "miwhen", "heartfailtmg", "classnyh", "cardsymptimeofadm", "carshock", "arrhythatrfib", "arrhythafib",
"arrhythaflutter", "arrhyththird", "arrhythsecond", "arrhythsss", "arrhythvv", "medinotr", "medadp5days", "medadpidis", "medacei48", "medbeta",
"medster", "medgp", "resusc", "numdisv", "stenleftmain", "laddiststenpercent", "hdef", "vdstena", "vdstenm", "vdinsufa", "vdinsufm", "vdinsuft",
"vdaoprimet", "incidenc", "status", "iabpwhen", "cathbasassistwhen", "ecmowhen", "calculatedbmi", "procid"]

# The optional API parameters
STS_PARAMS_OPTIONAL = []

def validate_sts_data(patient_data):
    """
    Validate the dict we're about to pass to the STS API.

    Input: patient_data (dict)
    Output: True if the data is valid, False otherwise
    """
    # Check the required parameters are present
    assert all(key in patient_data.keys() for key in STS_PARAMS_REQUIRED)

    # Check the parameters are all allowable
    assert all(key in STS_PARAMS_REQUIRED + STS_PARAMS_OPTIONAL for key in patient_data.keys())

    if patient_data['cvdtia'] != "" or patient_data['cvdpcarsurg'] != "":
        assert patient_data['cvd'] == "Yes", "cvd must be set if a TIA or prior cartoid procedure is true."

    # TODO: Add more tests here.

    return True


def query_sts_api(patient_data):
    # calculatedbmi

    # NOTE: The STS API requires *all* parameters be passed, even if they're empty, otherwise it throws a 500 error.
    # There must be at *least* 99 parameters, but some conditional parameters can be omitted. (e.g. secondary insurance)
    assert(len(patient_data) >= 99)

    # The STS client side computes BMI (why)?
    patient_data['calculatedbmi'] = round(
        (float(patient_data['weight-kg']) /
        ((100 * patient_data['height-cm']) ** 2)),
        2)

    print(patient_data)

    response = requests.post(url=STS_API_URL, params=patient_data)
    time.sleep(1)

    if response.status_code != requests.codes.ok:
        raise Exception("STS API returned status code %d" % response.status_code)

    return response.json()

#
"""
pred6d: 0.37929
pred14d: 0.04021
preddeep: 0.00116
predmm: 0.06003
predmort: 0.02005
predrenf: 0.01222
predreop: 0.01626
predstro: 0.00402
predvent: 0.03045
"""

def parse_csv(csv_file):
    """
    Load an input CSV of STS queries.
    
    NOTE: Your CSV header must be the same as the STS API parameters.
    Your CSV entries must *exactly* match the STS query parameters.

    We do limited validity testing here.

    Input: csv_file (str)
    Output: list of dicts
    """
    with open(csv_file, 'r') as f:
        lines = f.readlines()

    # The first line is the header, so skip it.
    lines = lines[1:]

    

def main():
    """
    Essentially all heavy lifting happens here -- the argparse parameters encode the right STS API variable names,
    and then calls the minimalist query_sts_api() function to get the results.

    Note that the STS API is a little odd -- it requires *all* parameters to be passed (even if they're empty)
    it includes oddities (race is sometimes "rac"), it does almost nothing client side (except BMI calculation?).

    If you use this code, please consider citing me and this repository.
    """
    parser = argparse.ArgumentParser(description="Query the STS Short-Term Risk Calculator (v4.2)\nPlease cite this if using in a publication.",
                                     epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
                                     usage='%(prog)s [options]',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    core_args = parser.add_argument_group("core")
    procedure_dict = {
        'CAB': 1,
        'AVR': 2,
        'MVR': 3,
        'AVR+CAB': 4,
        'MVR+CAB': 5,
        'MVRepair': 6,
        'MVRepair+CAB': 7,
    }
    core_args.add_argument('--procedure', dest="procid", type=lambda x: procedure_dict[x], metavar=list(procedure_dict.keys()), required=True)
    core_args.add_argument('--age', dest="age", metavar='{1-110}', type=int, choices=range(1, 111), required=True)
    core_args.add_argument('--gender', dest="gender", type=int, choices=['Male', 'Female'])

    group_race = parser.add_argument_group('race')
    # Note: These labels match the web interface.
    group_race.add_argument('--asian', dest="raceasian", action='store_const', const='Yes', default='')
    group_race.add_argument('--black', dest="raceblack", action='store_const', const='Yes', default='')
    group_race.add_argument('--indian-alaskan', dest="racenativeam", action='store_const', const='Yes', default='')
    # Missing an "e" in race -- on STS's end.
    group_race.add_argument('--hawaiian-islander', dest="racnativepacific", action='store_const', const='Yes', default='')
    group_race.add_argument('--hispanic-latino', dest="ethnicity", action='store_const', const='Yes', default='')

    metadata = parser.add_argument_group('metadata')

    payor_dict = {
        'self': 'None / self',
        'medicare': 'Medicare (includes commercially managed options)',
        'medicaid': 'Medicaid (includes commercially managed options)',
        'commercial': 'Commercial Health Insurance',
        'hmo': 'Health Maintenance Organization',
        'non-US': 'Non-U.S. Plan',
        'other': 'Other',
        }
    metadata.add_argument('--payor', dest="payorprim", type=lambda x: payor_dict[x], metavar=list(payor_dict.keys()))
    metadata.add_argument('--supplemental-payor', dest="payorsecond", type=lambda x: payor_dict[x], metavar=list(payor_dict.keys()))
    metadata.add_argument('--date', dest="surgdt", type=str, metavar="8/11/2017")

    biometrics = parser.add_argument_group('biometrics')
    biometrics.add_argument('--weight-kg', dest="weightkg", metavar='{10-250}', type=int, choices=range(10, 251))
    biometrics.add_argument('--height-cm', dest="heightcm", metavar='{20-251}', type=int, choices=range(20, 252))
    biometrics.add_argument('--hct', dest="hct", metavar='{1.00-99.99}', type=float)
    biometrics.add_argument('--wbc', dest="wbc", metavar='{0.10-99.99}', type=float)
    biometrics.add_argument('--platelets', dest="platelets", metavar='{1000-900000}', type=int, choices=range(1000, 900001))
    biometrics.add_argument('--creatinine', dest="creatlst", metavar='{0.10-30.00}', type=float)

    comorbidities = parser.add_argument_group('comorbidities')
    comorbidities.add_argument('--dialysis', dest="dialysis", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--hypertension', dest="hypertn", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--immunosuppressed', dest="immsupp", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--pvd', dest="pvd", action='store_const', const='Yes', default='')

    comorbidities.add_argument('--cvd', dest="cvd", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--cvd-tia', dest="cvdtia", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--cvd-carotid-procedure', dest="cvdpcarsurg", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--cva', dest="cva", action='store_const', const='Yes', default='')
    cvawhen_dict = {
    'this-month': '<= 30 days',
    'older': '> 30 days',
    }
    comorbidities.add_argument('--cva-when', dest="cvawhen", type=lambda x: cvawhen_dict[x], metavar=list(cvawhen_dict.keys()))

    comorbidities.add_argument('--mediastinal-radiation', dest="mediastrad", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--cancer', dest="cancer", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--fh-cad', dest="fhcad", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--sleep-apnea', dest="slpapn", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--liver-disease', dest="liverdis", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--unresponsive', dest="unrespstat", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--syncope', dest="syncope", action='store_const', const='Yes', default='')

    comorbidities.add_argument('--diabetes', dest="diabetes", action='store_const', const='Yes', default='')
    diabctrl_dict = {
        'none': 'None',
        'diet': 'Diet only',
        'oral': 'Oral',
        'insulin': 'Insulin',
        'other-injection': 'Other SubQ',
        'other': 'Other',
        'unknown': 'Unknown',
        }
    comorbidities.add_argument('--diabetes-control', dest="diabctrl", type=lambda x: diabctrl_dict[x], metavar=list(diabctrl_dict.keys()))

    comorbidities.add_argument('--endocarditis', dest="infendo", action='store_const', const='Yes', default='')
    infendty_dict = {
    'treated': 'Treated',
    'active': 'Active',
    }
    comorbidities.add_argument('--endocarditis-type', dest="infendty", type=lambda x: infendty_dict[x], metavar=list(infendty_dict.keys()))

    chrlungd_dict = {
    'no': 'No',
    'mild': 'Mild',
    'moderate': 'Moderate',
    'severe': 'Severe',
    'unknown-severity': 'Lung disease documented, severity unknown',
    'unknown': 'Unknown',
    }
    comorbidities.add_argument('--chronic-lung-disease', dest="chrlungd", type=lambda x: chrlungd_dict[x], metavar=list(chrlungd_dict.keys()))
 
    stenosis_dict = {
        '50-79': '50% to 79%',
        '80-99': '80% to 99%',
        '100': '100%',
        'unknown': 'Not documented',
    }
    comorbidities.add_argument('--right-carotid-stenosis', dest="cvdstenrt", type=lambda x: stenosis_dict[x], metavar=list(stenosis_dict.keys()))
    comorbidities.add_argument('--left-carotid-stenosis', dest="cvdstenlft", type=lambda x: stenosis_dict[x], metavar=list(stenosis_dict.keys()))

    comorbidities.add_argument('--illicits', dest="ivdrugab", action='store_const', const='Yes', default='')

    alcohol_dict = {
        '1': '<= 1 drink/week',
        '2-7': '2-7 drinks/week',
        '8': '>= 8 drinks/week',
        'none' : 'None',
        'unknown': 'Unknown',
    }
    comorbidities.add_argument('--alcohol', dest="alcohol", type=lambda x: alcohol_dict[x], metavar=list(alcohol_dict.keys()))

    pneumonia_dict = {
        'recent': 'Recent',
        'remote': 'Remote',
        'no': 'No',
        'unknown': 'Unknown',
    }
    comorbidities.add_argument('--pneumonia', dest="pneumonia", type=lambda x: pneumonia_dict[x], metavar=list(pneumonia_dict.keys()))

    tobaccouse_dict = {
        'never': 'Never smoker',
        'every-day': 'Current every day smoker',
        'some-days': 'Current some day smoker',
        'current': 'Smoker, current status (frequency) unknown',
        'former': 'Former smoker',
        'unknown': 'Smoking status unknown',
    }
    comorbidities.add_argument('--tobacco', dest="tobaccouse", type=lambda x: tobaccouse_dict[x], metavar=list(tobaccouse_dict.keys()))

    hmo2_dict = {
        'prn': 'Yes, PRN',
        'yes': 'Yes, oxygen dependent',
        'no': 'No',
        'unknown': 'Unknown',
    }
    comorbidities.add_argument('--home-o2', dest="hmo2", type=lambda x: hmo2_dict[x], metavar=list(hmo2_dict.keys()))

    # Previous Interventions
    # NOT IMPLEMENTED
    """
    "prcvint": "Yes",
    "prcab": "",
    "prvalve": "",
    "prvalveproc1": "",
    "prvalveproc2": "",
    "prvalveproc3": "",
    "prvalveproc4": "",
    "prvalveproc5": "",
    "poc": "",
    "pocint1": "",
    "pocint2": "",
    "pocint3": "",
    "pocint4": "",
    "pocint5": "",
    "pocint6": "",
    "pocint7": "",
    "pocpci": "",
    "pocpciwhen": "",
    "pocpciin": "",
    """
    
    miwhen_dict = {
        '6hr': '<=6 Hrs',
        '6-24hr': '>6 Hrs but <24 Hrs',
        '1-7days': '1 to 7 Days',
        '8-21days': '8 to 21 Days',
        '>21days': '>21 Days',
    }
    comorbidities.add_argument('--mi', dest="miwhen", type=lambda x: miwhen_dict[x], metavar=list(miwhen_dict.keys()))

    hfwhen_dict = {
        'acute': 'Acute',
        'chronic': 'Chronic',
        'both': 'Both'
    }
    comorbidities.add_argument('--hf-timing', dest="heartfailtmg", type=lambda x: hfwhen_dict[x], metavar=list(hfwhen_dict.keys()))


     "classnyh": "Class III",
     "cardsymptimeofadm": "Stable Angina",
     "carshock": "Yes, not at the time of the procedure but within prior 24 hours",
    
    rhythm_timing_dict = {
        'none': 'None',
        'remote': 'Remote (> 30 days preop)',
        'recent': 'Recent (<= 30 days preop)'
    }
    comorbidities.add_argument('--afib', dest="arrhythatrfib", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))

    "arrhythafib": "Persistent",

    comorbidities.add_argument('--aflutter', dest="arrhythaflutter", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))
    comorbidities.add_argument('--3deg-block', dest="arrhyththird", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))
    comorbidities.add_argument('--2deg-block', dest="arrhythsecond", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))
    comorbidities.add_argument('--sick-sinus', dest="arrhythsss", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))
    comorbidities.add_argument('--vt-vf', dest="arrhythvv", type=lambda x: rhythm_timing_dict[x], metavar=list(rhythm_timing_dict.keys()))
    
    "medinotr": "Yes",
    "medadp5days": "No",
    "medadpidis": "",
    "medacei48": "Contraindicated",
    "medbeta": "No",
    "medster": "No",
    "medgp": "Yes",
    "resusc": "Yes - More than 1 hour but less than 24 hours of the start of the procedure",
    "numdisv": "One",
    "stenleftmain": "N/A",
    "laddiststenpercent": "50 - 69%",

    comorbidities.add_argument('--ef', dest="hdef", metavar='{1.0-99.0}', type=float, choices=range(1, 111), required=True)
    comorbidities.add_argument('--aortic-stenosis', dest="vdstena", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--mitral-stenosis', dest="vdstenm", action='store_const', const='Yes', default='')

    valve_severity = {
        'trace': 'Trivial/Trace',
        'mild': 'Mild',
        'moderate': 'Moderate',
        'severe': 'Severe'
        'unknown': 'Not documented'
    }
    comorbidities.add_argument('--ar', dest="vdinsufa", type=lambda x: valve_severity[x], metavar=list(valve_severity.keys()))
    comorbidities.add_argument('--mr', dest="vdinsufm", type=lambda x: valve_severity[x], metavar=list(valve_severity.keys()))
    comorbidities.add_argument('--tr', dest="vdinsuft", type=lambda x: valve_severity[x], metavar=list(valve_severity.keys()))

      "vdaoprimet": "Congenital (other than Bicuspid, Unicuspid, or Quadricuspid)",

    incidence_dict = {
        'first': 'First cardiovascular surgery',
        'reop': 'First re-op cardiovascular surgery',
        'second-reop': 'Second re-op cardiovascular surgery',
        'third-reop': 'Third re-op cardiovascular surgery',
        'fourth-reop': 'Fourth or more re-op cardiovascular surgery'
        'na': 'NA - Not a cardiovascular surgery'
    }
    comorbidities.add_argument('--incidence', dest="incidenc", type=lambda x: incidence_dict[x], metavar=list(incidence_dict.keys()))


    status_dict = {
        'elective': 'Elective',
        'urgent': 'Urgent',
        'emergent': 'Emergent',
        'emergent-salvage': 'Emergent Salvage',
    }
    comorbidities.add_argument('--status', dest="status", type=lambda x: status_dict[x], metavar=list(status_dict.keys()))

    optime_dict = {
        'preop': 'Preop',
        'intraop': 'Intraop',
        'postop': 'Postop',
    }
    comorbidities.add_argument('--iabp', dest="iabpwhen", type=lambda x: optime_dict[x], metavar=list(optime_dict.keys()))
    comorbidities.add_argument('--catheter-assist', dest="cathbasassistwhen", type=lambda x: optime_dict[x], metavar=list(optime_dict.keys()))

    ecmowhen_dict = {
        'preop': 'Preop',
        'intraop': 'Intraop',
        'postop': 'Postop',
        'non-operative': 'Non-operative'
    }
    comorbidities.add_argument('--ecmo', dest="ecmowhen", type=lambda x: ecmowhen_dict[x], metavar=list(ecmowhen_dict.keys()))



    args = parser.parse_args()
    print(vars(args))
    # print(query_sts_api(vars(args)))
    parser.print_help()
    #print("Hello, %s!" % args.name)


if __name__ == '__main__':
    main()
