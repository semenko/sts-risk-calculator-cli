#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Nick Semenkovich <semenko@alum.mit.edu>.
#   https://nick.semenkovich.com/
#
# This software is released under the MIT License:
#  <https://opensource.org/licenses/mit-license.php>
#
# Source: https://github.com/semenko/sts-risk-calculator-cli

import argparse

def main():
    parser = argparse.ArgumentParser(description="Query the STS Short-Term Risk Calculator (v4.2)",
                                     epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
                                     usage='%(prog)s [options]',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--procedure', dest="procid", type=str, choices=['CAB', 'AVR', 'MVR', 'AVR+CAB', 'MVR+CAB', 'MVRepair', 'MVRepair+CAB'], required=True)

    parser.add_argument('--age', dest="age", metavar='##', type=int, choices=range(1, 111),
                        help='Age of the patient in years (1-110)', required=True)

    # Gender

    # Race / Ethnicity 

    # Payor
    # Surgery Date

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



    #parser = ArgumentParser(prog='cli')
    #parser.add_argument('name', help="The user's name.")
    # args = parser.parse_args()
    parser.print_help()
    #print("Hello, %s!" % args.name)


if __name__ == '__main__':
    main()
