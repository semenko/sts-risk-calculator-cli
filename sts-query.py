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
import csv
import datetime
import sys
import time

import json
import requests

# Modern python please (esp for | operator, https://peps.python.org/pep-0584/)
assert sys.version_info >= (3, 9)

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

# An empty API query with all required parmeters defined (but empty)
STS_QUERY_STUB = {key:'' for key in STS_PARAMS_REQUIRED}

# The optional API parameters
# TODO: Add all other params
STS_PARAMS_OPTIONAL = ["id"] # ID is an internal parameter we allow

def query_sts_api(sts_query_dict):
    # The STS client side computes BMI (why?)
    sts_query_dict['calculatedbmi'] = round(
        (float(sts_query_dict['weightkg']) /
        ((float(sts_query_dict['heightcm']) / 100.0) ** 2)),
        2)

    print(sts_query_dict)
    #a = json.dumps(sts_query_dict)
    #print(a)
    response = requests.post(url=STS_API_URL, json=sts_query_dict)
    time.sleep(1)

    if response.status_code != requests.codes.ok:
        raise Exception("STS API returned status code %d" % response.status_code)

    print("ALIVE!")
    print(response.json())
    return response.json()

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


def validate_and_return_csv_data(csv_entry):
    """
    Validate the dict we're about to pass to the STS API.

    NOTE: We perform some validation, but it's not complete.

    Input: patient_data (dict)
    Output: returns an entry that passed validation
    """
    # Check the required parameters are present
   # assert all(key in data.keys() for key in STS_PARAMS_REQUIRED)

    # Check the parameters are all allowable
    assert all(key in STS_PARAMS_REQUIRED + STS_PARAMS_OPTIONAL for key in csv_entry.keys()), "You have a column that's not one of the defined STS keys."

    # Union of these two dicts, overwriting keys from the user supplied CSV entries where able
    data = STS_QUERY_STUB | csv_entry

    procedure_dict = {
        'CAB': '1',
        'AVR': '2',
        'MVR': '3',
        'AVR+CAB': '4',
        'MVR+CAB': '5',
        'MVRepair': '6',
        'MVRepair+CAB': '7',
    }
    assert data['procid'] in procedure_dict.values()

    assert int(data['age']) in range(1,111)
    assert data['gender'] in ['Male', 'Female', '']

    yes_or_empty = ['Yes', '']
    ## Race/Ethnicity Parameters
    assert data['raceasian'] in yes_or_empty
    assert data['raceblack'] in yes_or_empty
    assert data['racenativeam'] in yes_or_empty
    # Missing an "e" in race -- on STS's end.
    assert data['racnativepacific'] in yes_or_empty
    # Hispanic/latino
    assert data['ethnicity'] in yes_or_empty


    ## Patient Metadata
    payors = ['None / self', 'Medicare (includes commercially managed options)', 'Medicaid (includes commercially managed options)',
     'Commercial Health Insurance', 'Health Maintenance Organization', 'Non-U.S. Plan', 'Other', '']
    assert data['payorprim'] in payors
    assert data['payorsecond'] in payors
    if data['payorsecond'] != "":
        assert data['payorprim'] != ""

    datetime.datetime.strptime(data['surgdt'], "%m/%d/%Y")

    ## Biometrics

    # We require weight/height for BMI calc later
    assert (int(data['weightkg']) in range(10,251))
    assert (int(data['heightcm']) in range(20, 252))

    assert (data['hct'] == "") or (1 <= int(data['hct']) <= 100)
    assert (data['wbc'] == "") or (0.1 <= float(data['wbc']) <= 100)
    assert (data['platelets'] == "") or (int(data['platelets']) in range(1000, 900001))
    assert (data['creatlst'] == "") or (0.10 <= float(data['creatlst']) <= 30)

    ## Comorbidities
    assert data['dialysis'] in yes_or_empty
    assert data['hypertn'] in yes_or_empty
    assert data['immsupp'] in yes_or_empty
    assert data['pvd'] in yes_or_empty

    assert data['cvd'] in yes_or_empty
    assert data['cvdtia'] in yes_or_empty
    assert data['cvdpcarsurg'] in yes_or_empty

    if data['cvdtia'] != '' or data['cvdpcarsurg'] != '':
        assert data['cvd'] == 'Yes', "cvd must be set if a TIA or prior cartoid procedure is true."

    assert data['cva'] in yes_or_empty
    assert data['cvawhen'] in ['<= 30 days', '> 30 days', '']
    if data['cvawhen'] != '':
        assert data['cva'] != ''

    assert data['mediastrad'] in yes_or_empty
    assert data['cancer'] in yes_or_empty
    assert data['fhcad'] in yes_or_empty
    assert data['slpapn'] in yes_or_empty
    assert data['liverdis'] in yes_or_empty
    assert data['unrespstat'] in yes_or_empty
    assert data['syncope'] in yes_or_empty

    assert data['diabetes'] in yes_or_empty
    assert data['diabctrl'] in ['None', 'Diet only', 'Oral','Insulin', 'Other SubQ', 'Other', 'Unknown', '']
    if data['diabctrl'] != '':
        assert data['diabetes'] != ''

    assert data['infendo'] in yes_or_empty
    assert data['infendty'] in ['Treated', 'Active', '']
    if data['infendty'] != '':
        assert data['infendo'] != ''

    assert data['chrlungd'] in ['No', 'Mild', 'Moderate', 'Severe', 'Lung disease documented, severity unknown', 'Unknown', '']
 
    stenosis_pct = ['50% to 79%', '80% to 99%', '100%', 'Not documented', '']
    assert data['cvdstenrt'] in stenosis_pct
    assert data['cvdstenlft'] in stenosis_pct

    assert data['ivdrugab'] in yes_or_empty
    assert data['alcohol'] in ['<= 1 drink/week', '2-7 drinks/week', '>= 8 drinks/week', 'None', 'Unknown', '']

    assert data['pneumonia'] in ['Recent', 'Remote', 'No', 'Unknown', '']

    assert data['tobaccouse'] in ['Never smoker', 'Current every day smoker', 'Current some day smoker', 'Smoker, current status (frequency) unknown', 'Former smoker', 'Smoking status unknown', '']

    assert data['hmo2'] in ['Yes, PRN', 'Yes, oxygen dependent', 'No', 'Unknown', '']

    # Not Validated Yet
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
    
    assert data['miwhen'] in ['<=6 Hrs', '>6 Hrs but <24 Hrs', '1 to 7 Days', '8 to 21 Days', '>21 Days', '']
    assert data['heartfailtmg'] in ['Acute', 'Chronic', 'Both', '']

    assert data['classnyh'] in ['Class I', 'Class II', 'Class III','Class IV', 'Not documented', '']

    #  "cardsymptimeofadm": "Stable Angina",
    #  "carshock": "Yes, not at the time of the procedure but within prior 24 hours",
    
    rhythm_onset = ['None', 'Remote (> 30 days preop)', 'Recent (<= 30 days preop)', '']
    assert data['arrhythatrfib'] in rhythm_onset
    # "arrhythafib": "Persistent",
    assert data['arrhythaflutter'] in rhythm_onset
    assert data['arrhyththird'] in rhythm_onset
    assert data['arrhythsecond'] in rhythm_onset
    assert data['arrhythsss'] in rhythm_onset
    assert data['arrhythvv'] in rhythm_onset
    
    assert data['medinotr'] in yes_or_empty

    # TODO: Fix
    # NOTE: The API allows more complex values here (contraindicated / unknown), which we ignore.  Yes/No/Empty.
    assert data['medadp5days'] in yes_or_empty
    assert data['medadpidis'] in yes_or_empty # ????

    assert data['medacei48'] in yes_or_empty
    assert data['medbeta'] in yes_or_empty
    assert data['medster'] in yes_or_empty
    assert data['medgp'] in yes_or_empty

    # "resusc": "Yes - More than 1 hour but less than 24 hours of the start of the procedure",
    # "numdisv": "One",
    # "stenleftmain": "N/A",
    # "laddiststenpercent": "50 - 69%",

    assert (data['hdef'] == '') or  (1.0 <= float(hdef) <= 99.0)
    # AS & MS
    assert data['vdstena'] in yes_or_empty
    assert data['vdstenm'] in yes_or_empty

    valve_severity = ['Trivial/Trace', 'Mild', 'Severe', 'Not documented', '']
    assert data['vdinsufa'] in valve_severity
    assert data['vdinsufm'] in valve_severity
    assert data['vdinsuft'] in valve_severity

    #  "vdaoprimet": "Congenital (other than Bicuspid, Unicuspid, or Quadricuspid)",

    assert data['incidenc'] in ['First cardiovascular surgery', 'First re-op cardiovascular surgery', 'Second re-op cardiovascular surgery',
                                'Third re-op cardiovascular surgery', 'Fourth or more re-op cardiovascular surgery', 'NA - Not a cardiovascular surgery', '']

    assert data['status'] in ['Elective', 'Urgent', 'Emergent', 'Emergent Salvage', '']

    assert data['iabpwhen'] in ['Preop', 'Intraop', 'Postop', '']
    assert data['cathbasassistwhen'] in ['Preop', 'Intraop', 'Postop', '']
    
    assert data['ecmowhen'] in ['Preop', 'Intraop', 'Postop', 'Non-operative', '']

    return data


def main():
    """
    Essentially all heavy lifting happens here -- the argparse parameters encode the right STS API variable names,
    and then calls the minimalist query_sts_api() function to get the results.

    Note that the STS API is a little odd -- it requires *all* parameters to be passed (even if they're empty)
    it includes oddities (race is sometimes "rac"), it does almost nothing client side (except BMI calculation?).

    If you use this code, please consider citing me and this repository.
    """
    parser = argparse.ArgumentParser(description="Query the STS Short-Term Risk Calculator (v4.2) via a CSV." +
                                                 "\nPlease cite this repository if you're using in a publication.",
                                     epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
                                     usage='%(prog)s [options]',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--csv', dest='csv_file', metavar='patient-data.csv', type=argparse.FileType('r'), required=True)

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()


    print("Validating CSV entries.")
    # NOTE: Other than an "ID" column your CSV header must be the same as the STS API parameters,
    # and your CSV entries must *exactly* match the STS query parameters.

    validated_patient_data = []

    csv_dictreader = csv.DictReader(args.csv_file)
    for row in csv_dictreader:
        print(f"\tID: {row['id']}", end='')
        validated_patient_data.append(validate_and_return_csv_data(row))
        print(' OK.')


    print("Querying STS API.")
    # Query the API for all CSV entries
    for entry in validated_patient_data:
        print(f"ID: {entry['id']}")
        del entry['id']
        print(query_sts_api(entry))
        break

    print("Done.")

if __name__ == '__main__':
    main()
