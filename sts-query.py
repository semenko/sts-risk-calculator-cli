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

def query_sts_api(argparse_vars_as_dict):

    # NOTE: The STS API requires *all* parameters be passed, even if they're empty, otherwise it throws a 500 error.
    # There must be at *least* 99 parameters, but some conditional parameters can be omitted. (e.g. secondary insurance)
    assert(len(argparse_vars_as_dict) >= 99)

    response = requests.post(url=STS_API_URL, params=argparse_vars_as_dict)
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

def main():
    """
    Essentially all heavy lifting happens here -- the argparse parameters encode the right STS API variable names,
    and then calls the minimalist query_sts_api() function to get the results.

    Note that the STS API is a little odd -- it requires *all* parameters to be passed (even if they're empty)
    it includes misspellings (race is sometimes "rac"), it does almost nothing client side (except BMI calculation?).
    """
    parser = argparse.ArgumentParser(description="Query the STS Short-Term Risk Calculator (v4.2)",
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
    biometrics.add_argument('--weight-kg', dest="weightkg", metavar='{10-250}', type=int, choices=range(1, 111))
    biometrics.add_argument('--height-cm', dest="heightcm", metavar='{20-251}', type=int, choices=range(1, 111))
    biometrics.add_argument('--hct', dest="hct", metavar='{1.00-99.99}', type=float, choices=range(1, 111))
    biometrics.add_argument('--wbc', dest="wbc", metavar='{0.10-99.99}', type=float, choices=range(1, 111))
    biometrics.add_argument('--platelets', dest="platelets", metavar='{1000-900000}', type=int, choices=range(1000, 900001))
    biometrics.add_argument('--creatinine', dest="creatlst", metavar='{0.10-30.00}', type=int, choices=range(1, 111))
    # ?? Calculated BMI parameter calculatedbmi

    comorbidities = parser.add_argument_group('comorbidities')
    comorbidities.add_argument('--dialysis', dest="dialysis", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--hypertension', dest="hypertn", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--immunosuppressed', dest="immsupp", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--pvd', dest="pvd", action='store_const', const='Yes', default='')

    comorbidities.add_argument('--cvd', dest="cvd", action='store_const', const='Yes', default='')
    # comorbidities.add_argument('--', dest="cvdtia", action='store_const', const='Yes', default='')
    # comorbidities.add_argument('--', dest="cvdpcarsurg", action='store_const', const='Yes', default='')

    comorbidities.add_argument('--mediastinal-radiation', dest="mediastrad", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--cancer', dest="cancer", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--fh-cad', dest="fhcad", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--sleep-apnea', dest="slpapn", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--liver-disease', dest="liverdis", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--unresponsive', dest="unrespstat", action='store_const', const='Yes', default='')
    comorbidities.add_argument('--syncope', dest="syncope", action='store_const', const='Yes', default='')

    comorbidities.add_argument('--diabetes', dest="diabetes", action='store_const', const='Yes', default='')
    # diabctrl
    comorbidities.add_argument('--endocarditis', dest="infendo", action='store_const', const='Yes', default='')
    # infendty

    comorbidities.add_argument('--cva', dest="cva", action='store_const', const='Yes', default='')
    # cvawhen
   
    comorbidities.add_argument('--illicits', dest="ivdrugab", action='store_const', const='Yes', default='')


    args = parser.parse_args()
    print(vars(args))
    # print(query_sts_api(vars(args)))
    parser.print_help()
    #print("Hello, %s!" % args.name)


if __name__ == '__main__':
    main()
