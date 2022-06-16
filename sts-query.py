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
from lib2to3.pgen2.parse import Parser
import requests
import time

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
    parser = argparse.ArgumentParser(description="Query the STS Short-Term Risk Calculator (v4.2)",
                                     epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
                                     usage='%(prog)s [options]',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    core_args = parser.add_argument_group("core")
    core_args.add_argument('--procedure', dest="procid", type=str, choices=['CAB', 'AVR', 'MVR', 'AVR+CAB', 'MVR+CAB', 'MVRepair', 'MVRepair+CAB'], required=True)
    core_args.add_argument('--age', dest="age", metavar='{1-110}', type=int, choices=range(1, 111))
    core_args.add_argument('--gender', dest="gender", type=int, choices=['Male', 'Female'])

    group_race = parser.add_argument_group('race')
    group_race.add_argument('--asian', dest="raceasian", action='store_const', const='Yes', default='')
    group_race.add_argument('--black', dest="race_black", action='store_true')
    group_race.add_argument('--indian-alaskan', dest="race_indian", action='store_true')
    group_race.add_argument('--hawaiian-islander', dest="race_hawaiian", action='store_true')
    group_race.add_argument('--hispanic-latino', dest="race_hispanic", action='store_true')

    metadata = parser.add_argument_group('metadata')
    metadata.add_argument('--payor', dest="payor", type=str, choices=['self', 'medicare', 'medicaid', 'commercial', 'hmo', 'military', 'non-US'])
    metadata.add_argument('--supplemental-payor', dest="supp_payor", type=str, choices=['self', 'medicare', 'medicaid', 'commercial', 'hmo', 'military', 'non-US'])
    metadata.add_argument('--date', dest="date", type=str, metavar="8/11/2017")


    # Weight kg
    # Height Cm

    # Labs
    # HCT (or Hgb)
    # WBC
    # PLT
    # Cr

    # Comorbidities 
    # Dialysis
    # HTN
    # Immunocompromised
    # PAD
    # CVD
    # Mediastinal XRT
    # Cancer w/i 5yr
    # Family CAD
    # Sleep apnea
    # Liver disease
    # Unresponsive
    # Syncope
    # Diabetes
    ## Diabetes control
    # endocarditis
    # Chronic lung disease
    # Stenosis R Carotid
    # Stenosis L carotid
    # illicit drug use
    # alcohol use
    # pneumonia
    # smoking use
    # home o2
    # previous cardiac interventions
    # MI when
    # heart failure timing
    # NYHA Class
    # At time angina
    # cardiogenic sock
    # afib
    # afib type
    # afluitter
    # third deg avb
    # second deg 
    # sick sinus
    # VT/VF
    # inotropes
    # ADP inh
    # ACE/ARB
    # BB
    # Steroids
    # GB2B3a
    # Resusc
    # Number diseas
    # LAD involv percent
    # EF
    # AS
    # MS
    # AI
    # MR
    # TR
    # AV etiology
    # Incidence
    # status
    # IABP
    # Catheter used
    # ECMO


    args = parser.parse_args()
    print(vars(args))
    # print(query_sts_api(vars(args)))
    parser.print_help()
    #print("Hello, %s!" % args.name)


if __name__ == '__main__':
    main()
