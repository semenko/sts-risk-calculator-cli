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
import os
import sys
import time

import asyncio
import websockets
import tqdm
import json

# Modern python please (esp for | operator, https://peps.python.org/pep-0584/)
assert sys.version_info >= (3, 9)

WS_API_URL = "wss://acsdriskcalc.research.sts.org/websocket/"

# The required API parameters
STS_PARAMS_REQUIRED = [
    "age",
    "gender",
    "raceasian",
    "raceblack",
    "racenativeam",
    "racnativepacific",
    "ethnicity",
    "payorprim",
    "payorsecond",
    "surgdt",
    "weightkg",
    "heightcm",
    "hct",
    "wbc",
    "platelets",
    "creatlst",
    "dialysis",
    "hypertn",
    "immsupp",
    "pvd",
    "cvd",
    "cvdtia",
    "cvdpcarsurg",
    "mediastrad",
    "cancer",
    "fhcad",
    "slpapn",
    "liverdis",
    "unrespstat",
    "syncope",
    "diabetes",
    "diabctrl",
    "infendo",
    "infendty",
    "cva",
    "cvawhen",
    "chrlungd",
    "cvdstenrt",
    "cvdstenlft",
    "ivdrugab",
    "alcohol",
    "pneumonia",
    "tobaccouse",
    "hmo2",
    "prcvint",
    "prcab",
    "prvalve",
    "prvalveproc1",
    "prvalveproc2",
    "prvalveproc3",
    "prvalveproc4",
    "prvalveproc5",
    "poc",
    "pocint1",
    "pocint2",
    "pocint3",
    "pocint4",
    "pocint5",
    "pocint6",
    "pocint7",
    "pocpci",
    "pocpciwhen",
    "pocpciin",
    "miwhen",
    "heartfailtmg",
    "classnyh",
    "cardsymptimeofadm",
    "carshock",
    "arrhythatrfib",
    "arrhythafib",
    "arrhythaflutter",
    "arrhyththird",
    "arrhythsecond",
    "arrhythsss",
    "arrhythvv",
    "medinotr",
    "medadp5days",
    "medadpidis",
    "medacei48",
    "medbeta",
    "medster",
    "medgp",
    "resusc",
    "numdisv",
    "stenleftmain",
    "laddiststenpercent",
    "hdef",
    "vdstena",
    "vdstenm",
    "vdinsufa",
    "vdinsufm",
    "vdinsuft",
    "vdaoprimet",
    "incidenc",
    "status",
    "iabpwhen",
    "cathbasassistwhen",
    "ecmowhen",
    "calculatedbmi",
    "procid",
]

# An empty API query with all required parmeters defined (but empty)
STS_QUERY_STUB = {key: "" for key in STS_PARAMS_REQUIRED}

# The optional API parameters
# TODO: Add all other optional params from STS? Is the above actually exhaustive?
STS_PARAMS_OPTIONAL = ["id"]  # ID is an internal parameter we allow

STS_EXPECTED_RESULTS = [
    "predmort",
    "predmm",
    "preddeep",
    "pred14d",
    "predstro",
    "predvent",
    "predrenf",
    "predreop",
    "pred6d",
]

# Field mapping configurations
PROCID_TO_PROC = {
    "1": "CABG",
    "2": "AVR", 
    "3": "MVR",
    "4": "AVR + CABG",
    "5": "MVR + CABG",
    "7": "MV Repair",
    "8": "MV Repair + CABG",
}

BOOLEAN_FIELDS = [
    "medacei48", "medgp", "medinotr", "medster", "medadp5days", "fhcad",
    "hypertn", "liverdis", "mediastrad", "unrespstat", "dialysis", "cancer",
    "syncope", "immsupp", "pneumonia", "slpapn", "hmo2", "pvd", "cvdstenrt",
    "cvdpcarsurg", "cvdstenlft", "carshock", "resusc", "stenleftmain",
    "laddiststenpercent", "vdstena", "vdstenm", "vdaoprimet"
]

ARRAY_FIELD_MAPPINGS = {
    "diabetes": "diabetes",
    "ivdrugab": "ivdrugab", 
    "alcohol": "alcohol",
    "tobaccouse": "tobaccouse",
    "chrlungd": "chrlungd",
    "cvd": "cvd",
    "heartfailtmg": "heartfailtmg",
    "classnyh": "classnyh",
    "cardsymptimeofadm": "cardsymptimeofadm",
    "miwhen": "miwhen",
    "numdisv": "numdisv",
    "vdinsufa": "vdinsufa",
    "vdinsufm": "vdinsufm",
    "vdinsuft": "vdinsuft",
    "arrhythatrfib": "arrhythatrfib",
    "arrhythafib": "arrhythafib",
    "arrhythaflutter": "arrhythaflutter",
    "arrhythvv": "arrhythvv",
    "arrhythsss": "arrhythsss",
    "arrhythsecond": "arrhythsecond",
    "arrhyththird": "arrhyththird"
}

RACE_MAPPINGS = {
    "raceasian": "Asian",
    "raceblack": "Black or African American", 
    "racenativeam": "American Indian or Alaska Native",
    "racnativepacific": "Native Hawaiian or Other Pacific Islander",
    "ethnicity": "Hispanic or Latino"
}

def create_websocket_init_data():
    """Create the initial websocket data structure."""
    return {
        "prcvint": [],
        "Proc": [],
        "incidenc": [],
        "status": [],
        "gender": [],
        "racemulti": [],
        "payordata": [],
        "diabetes": [],
        "endocarditis": [],
        "ivdrugab": [],
        "alcohol": [],
        "tobaccouse": [],
        "chrlungd": [],
        "cvd": [],
        "heartfailtmg": [],
        "classnyh": [],
        "mcs": [],
        "cardsymptimeofadm": [],
        "miwhen": [],
        "numdisv": [],
        "vdinsufa": [],
        "vdinsufm": [],
        "vdinsuft": [],
        "arrhythatrfib": [],
        "arrhythafib": [],
        "arrhythaflutter": [],
        "arrhythvv": [],
        "arrhythsss": [],
        "arrhythsecond": [],
        "arrhyththird": [],
        "prvalveproc": [],
        "pocpci": [],
        "pocint": [],
        "tab": "Clinical Summary",
        "decline:shiny.action": 0,
        "reset:shiny.action": 0,
        "copybuttonestimates:shiny.action": 0,
        "copybuttonsummary:shiny.action": 0,
        "vstrpr": False,
        **{field: False for field in BOOLEAN_FIELDS},
        "ageN:shiny.number": None,
        "heightN:shiny.number": None,
        "weightN:shiny.number": None,
        "BMI:shiny.number": None,
        "creatlstN:shiny.number": None,
        "hctN:shiny.number": None,
        "wbcN:shiny.number": None,
        "plateletsN:shiny.number": None,
        "medadpidis:shiny.number": None,
        "hdef:shiny.number": None,
        ".clientdata_output_errorMessage_hidden": False,
        ".clientdata_output_text2_hidden": False,
        ".clientdata_output_summary_hidden": False,
        ".clientdata_pixelratio": 1,
        ".clientdata_url_protocol": "https:",
        ".clientdata_url_hostname": "acsdriskcalc.research.sts.org",
        ".clientdata_url_port": "",
        ".clientdata_url_pathname": "/",
        ".clientdata_url_search": "",
        ".clientdata_url_hash_initial": "",
        ".clientdata_url_hash": "",
        ".clientdata_singletons": "add739c82ab207ed2c80be4b7e4b181525eb7a75",
    }

def map_basic_fields(sts_query_dict, update_data):
    """Map basic scalar fields."""
    # Procedure
    if "procid" in sts_query_dict and sts_query_dict["procid"] in PROCID_TO_PROC:
        update_data["Proc"] = [PROCID_TO_PROC[sts_query_dict["procid"]]]
    
    # Demographics
    if "age" in sts_query_dict and sts_query_dict["age"]:
        update_data["ageN"] = int(sts_query_dict["age"])
    if "gender" in sts_query_dict and sts_query_dict["gender"]:
        update_data["gender"] = [sts_query_dict["gender"]]
    if "status" in sts_query_dict and sts_query_dict["status"]:
        update_data["status"] = [sts_query_dict["status"]]
    if "incidenc" in sts_query_dict and sts_query_dict["incidenc"]:
        update_data["incidenc"] = [sts_query_dict["incidenc"]]

def map_biometric_fields(sts_query_dict, update_data):
    """Map height, weight, and BMI fields."""
    if "heightcm" in sts_query_dict and sts_query_dict["heightcm"]:
        update_data["heightN"] = float(sts_query_dict["heightcm"])
    if "weightkg" in sts_query_dict and sts_query_dict["weightkg"]:
        update_data["weightN"] = float(sts_query_dict["weightkg"])
    
    # Calculate BMI if both height and weight are available
    if ("weightkg" in sts_query_dict and "heightcm" in sts_query_dict and 
        sts_query_dict["weightkg"] and sts_query_dict["heightcm"]):
        bmi = float(sts_query_dict["weightkg"]) / ((float(sts_query_dict["heightcm"]) / 100.0) ** 2)
        update_data["BMI"] = round(bmi, 2)

def map_lab_fields(sts_query_dict, update_data):
    """Map laboratory values."""
    lab_mappings = {
        "creatlst": ("creatlstN", float),
        "hct": ("hctN", int),
        "wbc": ("wbcN", float),
        "platelets": ("plateletsN", int),
        "hdef": ("hdef", float),
        "medadpidis": ("medadpidis", int)
    }
    
    for sts_field, (ws_field, converter) in lab_mappings.items():
        if sts_field in sts_query_dict and sts_query_dict[sts_field]:
            update_data[ws_field] = converter(sts_query_dict[sts_field])

def map_boolean_fields(sts_query_dict, update_data):
    """Map boolean fields."""
    for field in BOOLEAN_FIELDS:
        if field in sts_query_dict and sts_query_dict[field] == "Yes":
            update_data[field] = True

def map_array_fields(sts_query_dict, update_data):
    """Map fields that should be arrays."""
    for sts_field, ws_field in ARRAY_FIELD_MAPPINGS.items():
        if sts_field in sts_query_dict and sts_query_dict[sts_field]:
            update_data[ws_field] = [sts_query_dict[sts_field]]

def map_procedure_fields(sts_query_dict, update_data):
    """Map previous procedure fields."""
    # Previous cardiovascular intervention
    if "prcvint" in sts_query_dict and sts_query_dict["prcvint"] == "Yes":
        update_data["prcvint"] = ["Yes"]
    if "pocpci" in sts_query_dict and sts_query_dict["pocpci"] == "Yes":
        update_data["pocpci"] = ["Yes"]
    
    # Valve procedures
    valve_procs = [sts_query_dict[f"prvalveproc{i}"] 
                   for i in range(1, 6) 
                   if f"prvalveproc{i}" in sts_query_dict and sts_query_dict[f"prvalveproc{i}"]]
    if valve_procs:
        update_data["prvalveproc"] = valve_procs
    
    # Other cardiac interventions
    poc_ints = [sts_query_dict[f"pocint{i}"] 
                for i in range(1, 8) 
                if f"pocint{i}" in sts_query_dict and sts_query_dict[f"pocint{i}"]]
    if poc_ints:
        update_data["pocint"] = poc_ints

def map_race_ethnicity_fields(sts_query_dict, update_data):
    """Map race and ethnicity fields."""
    race_fields = [race_name 
                   for sts_field, race_name in RACE_MAPPINGS.items() 
                   if sts_query_dict.get(sts_field) == "Yes"]
    if race_fields:
        update_data["racemulti"] = race_fields

def map_payor_fields(sts_query_dict, update_data):
    """Map payor fields."""
    payors = [payor for payor in [sts_query_dict.get("payorprim"), sts_query_dict.get("payorsecond")] 
              if payor]
    if payors:
        update_data["payordata"] = payors

def map_special_condition_fields(sts_query_dict, update_data):
    """Map special condition fields that require multiple field checks."""
    # Endocarditis
    if sts_query_dict.get("infendo") == "Yes" and sts_query_dict.get("infendty"):
        update_data["endocarditis"] = [sts_query_dict["infendty"]]
    
    # Diabetes control
    if sts_query_dict.get("diabetes") == "Yes" and sts_query_dict.get("diabctrl"):
        update_data["diabetes"] = [sts_query_dict["diabctrl"]]

def prepare_websocket_messages(sts_query_dict):
    """Prepare init and update messages for websocket communication."""
    init_data = create_websocket_init_data()
    update_data = {}
    
    # Apply all field mappings
    map_basic_fields(sts_query_dict, update_data)
    map_biometric_fields(sts_query_dict, update_data)
    map_lab_fields(sts_query_dict, update_data)
    map_boolean_fields(sts_query_dict, update_data)
    map_array_fields(sts_query_dict, update_data)
    map_procedure_fields(sts_query_dict, update_data)
    map_race_ethnicity_fields(sts_query_dict, update_data)
    map_payor_fields(sts_query_dict, update_data)
    map_special_condition_fields(sts_query_dict, update_data)
    
    return (
        '{"method":"init","data":' + json.dumps(init_data) + '}',
        '{"method":"update","data":' + json.dumps(update_data) + '}'
    )

def print_debug_info(init_msg, update_msg):
    """Print debugging information for websocket requests."""
    ws_headers = [
        ("Origin", "https://acsdriskcalc.research.sts.org"),
        ("Referer", "https://acsdriskcalc.research.sts.org/"),
        ("User-Agent", "Mozilla/5.0"),
    ]
    
    print("\nTo replicate the websocket requests with wscat or curl, use:")
    print("wscat example:")
    print("wscat -c wss://acsdriskcalc.research.sts.org/websocket/ " + 
          " ".join(f'-H "{k}: {v}"' for k, v in ws_headers))
    print(init_msg)
    print(update_msg)
    print()

async def query_sts_api_async(sts_query_dict):
    """
    Query the STS API via websocket.
    Input: a dict of STS query parameters.
    Output: the STS results dict.
    """
    init_msg, update_msg = prepare_websocket_messages(sts_query_dict)
    print_debug_info(init_msg, update_msg)
    
    ws_headers = [
        ("Origin", "https://acsdriskcalc.research.sts.org"),
        ("Referer", "https://acsdriskcalc.research.sts.org/"),
        ("User-Agent", "Mozilla/5.0"),
    ]

    async with websockets.connect(WS_API_URL, additional_headers=ws_headers) as ws:
        await ws.send(init_msg)
        await asyncio.sleep(1)  # Give the server time to process init
        await ws.send(update_msg)
        
        # Wait for response(s)
        for _ in range(30):  # Try up to 30 messages
            msg = await ws.recv()
            try:
                msg_data = json.loads(msg)
                # Look for the response with errors and values.text2.html structure
                if (msg_data.get("errors") is not None and 
                    msg_data.get("values", {}).get("text2", {}).get("html")):
                    # Parse the HTML content to extract risk values
                    html_content = msg_data["values"]["text2"]["html"]
                    result = parse_sts_html_response(html_content)
                    if result and any(k in result for k in STS_EXPECTED_RESULTS):
                        return result
            except Exception:
                continue
        
        raise Exception("No valid response from STS websocket API")

def parse_sts_html_response(html_content):
    """
    Parse the HTML response from STS API to extract risk values.
    The HTML contains the risk predictions that we need to extract.
    """
    import re
    
    result = {}
    
    # Define patterns to extract each risk value from HTML
    risk_patterns = {
        "predmort": r"Operative Mortality.*?(\d+\.?\d*)%",
        "predmm": r"Major Morbidity.*?(\d+\.?\d*)%", 
        "preddeep": r"Deep Sternal Wound Infection.*?(\d+\.?\d*)%",
        "pred14d": r"Renal Failure.*?(\d+\.?\d*)%",
        "predstro": r"Stroke.*?(\d+\.?\d*)%",
        "predvent": r"Prolonged Ventilation.*?(\d+\.?\d*)%",
        "predrenf": r"Renal Failure.*?(\d+\.?\d*)%",
        "predreop": r"Re-operation.*?(\d+\.?\d*)%",
        "pred6d": r"Short Length of Stay.*?(\d+\.?\d*)%"
    }
    
    # Try to extract values using regex patterns
    for key, pattern in risk_patterns.items():
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                # Convert percentage to decimal
                result[key] = float(match.group(1)) / 100.0
            except ValueError:
                continue
    
    # If regex fails, try a more general approach looking for percentage values
    if not result:
        # Look for any percentage values in the HTML
        percentage_matches = re.findall(r'(\d+\.?\d*)%', html_content)
        if len(percentage_matches) >= len(STS_EXPECTED_RESULTS):
            # Map the found percentages to expected results in order
            for i, key in enumerate(STS_EXPECTED_RESULTS):
                if i < len(percentage_matches):
                    try:
                        result[key] = float(percentage_matches[i]) / 100.0
                    except ValueError:
                        continue
    
    return result

def query_sts_api(sts_query_dict):
    """
    Synchronous wrapper for async websocket API call.
    """
    return asyncio.run(query_sts_api_async(sts_query_dict))


def validate_and_return_csv_data(csv_entry):
    """
    Extensively validate the dict we're about to pass to the STS API.

    Note that we validate ~most fields, but not all prior procedures if those are entered.

    (Please open a Github issue if you find a problem with your data validation.)

    Input: patient_data (dict)
    Output: returns a dict that passed validation, union with the STS_QUERY_STUB
    """
    # Check the required parameters are present
    # assert all(key in data.keys() for key in STS_PARAMS_REQUIRED)

    # Check the parameters are all allowable
    provided_keys = csv_entry.keys()
    valid_keys = STS_PARAMS_REQUIRED + STS_PARAMS_OPTIONAL
    key_difference = set(provided_keys) - set(valid_keys)
    assert (
        len(key_difference) == 0
    ), f"You have one or more columns that are not defined STS keys: {key_difference}"

    # Union of these two dicts, overwriting keys from the user supplied CSV entries where able
    data = STS_QUERY_STUB | csv_entry

    # Procedure
    procedure_dict = {
        "CAB": "1",
        "AVR": "2",
        "MVR": "3",
        "AVR+CAB": "4",
        "MVR+CAB": "5",
        # There's no 6 ?!
        "MVRepair": "7",
        "MVRepair+CAB": "8",
    }
    assert data["procid"] in procedure_dict.values(), "Invalid procid"

    # Key Patient Data
    assert int(data["age"]) in range(1, 111), "Invalid age"
    assert data["gender"] in ["Male", "Female", ""], "Invalid gender"

    yes_or_empty = ["Yes", ""]

    ## Race/Ethnicity Parameters
    assert data["raceasian"] in yes_or_empty, "Invalid raceasian"
    assert data["raceblack"] in yes_or_empty, "Invalid raceblack"
    assert data["racenativeam"] in yes_or_empty, "Invalid racenativeam"
    # Missing an "e" in race -- on STS's end.
    assert data["racnativepacific"] in yes_or_empty, "Invalid racnativepacific"
    # Hispanic/latino
    assert data["ethnicity"] in yes_or_empty, "Invalid ethnicity"

    ## Patient Metadata
    payors = [
        "None / self",
        "Medicare (includes commercially managed options)",
        "Medicaid (includes commercially managed options)",
        "Commercial Health Insurance",
        "Health Maintenance Organization",
        "Non-U.S. Plan",
        "Other",
        "",
    ]
    assert data["payorprim"] in payors, "Invalid payorprim"
    assert data["payorsecond"] in payors, "Invalid payorsecond"
    if data["payorsecond"] != "":
        assert (
            data["payorprim"] != ""
        ), "If payorsecond is set, payorprim must also be set"

    # TODO: Double check the STS API handles 0 padding
    data["surgdt"] = datetime.datetime.strptime(data["surgdt"], "%m/%d/%Y").strftime(
        "%m/%d/%Y"
    )

    ## Biometrics
    # We require weight/height for BMI calc later
    assert 10 <= float(data["weightkg"]) <= 250, "Invalid weightkg"
    assert 20 <= float(data["heightcm"]) <= 251, "Invalid heightcm"

    ## Labs
    assert (data["hct"] == "") or (1 <= int(data["hct"]) <= 100), "Invalid hct"
    assert (data["wbc"] == "") or (0.1 <= float(data["wbc"]) <= 100), "Invalid wbc"
    assert (data["platelets"] == "") or (
        int(data["platelets"]) in range(1000, 900001)
    ), "Invalid platelets"
    assert (data["creatlst"] == "") or (
        0.10 <= float(data["creatlst"]) <= 30
    ), "Invalid creatlst"

    ## Comorbidities
    assert data["dialysis"] in yes_or_empty, "Invalid dialysis"
    assert data["hypertn"] in yes_or_empty, "Invalid hypertn"
    assert data["immsupp"] in yes_or_empty, "Invalid immsupp"
    assert data["pvd"] in yes_or_empty, "Invalid pvd"

    assert data["cvd"] in yes_or_empty, "Invalid cvd"
    assert data["cvdtia"] in yes_or_empty, "Invalid cvdtia"
    assert data["cvdpcarsurg"] in yes_or_empty, "Invalid cvdpcarsurg"

    if data["cvdtia"] != "" or data["cvdpcarsurg"] != "":
        assert (
            data["cvd"] == "Yes"
        ), "Invalid cvdpcarsurg, cvd must be set if a TIA or prior cartoid procedure is true."

    assert data["cva"] in yes_or_empty, "Invalid cva"
    assert data["cvawhen"] in ["<= 30 days", "> 30 days", ""], "Invalid when"
    if data["cvawhen"] != "":
        assert (
            data["cva"] != ""
        ), "Invalid cvawhen: cva must be set to Yes if cvdwhen is defined"

    assert data["mediastrad"] in yes_or_empty, "Invalid mediastrad"
    assert data["cancer"] in yes_or_empty, "Invalid cancer"
    assert data["fhcad"] in yes_or_empty, "Invalid fhcad"
    assert data["slpapn"] in yes_or_empty, "Invalid slpapn"
    assert data["liverdis"] in yes_or_empty, "Invalid liverdis"
    assert data["unrespstat"] in yes_or_empty, "Invalid unrespstat"
    assert data["syncope"] in yes_or_empty, "Invalid syncope"

    assert data["diabetes"] in yes_or_empty, "Invalid diabetes"
    assert data["diabctrl"] in [
        "None",
        "Diet only",
        "Oral",
        "Insulin",
        "Other SubQ",
        "Other",
        "Unknown",
        "",
    ], "Invalid diabctrl"
    if data["diabctrl"] != "":
        assert (
            data["diabetes"] != ""
        ), "Invalid diabctrl: diabetes must be set if diabctrl is set"

    assert data["infendo"] in yes_or_empty, "Invalid infendo"
    assert data["infendty"] in ["Treated", "Active", ""], "Invalid infendty"
    if data["infendty"] != "":
        assert (
            data["infendo"] != ""
        ), "Invalid infendty; infendo must be set if infendty is set"

    assert data["chrlungd"] in [
        "No",
        "Mild",
        "Moderate",
        "Severe",
        "Lung disease documented, severity unknown",
        "Unknown",
        "",
    ], "Invalid chrlungd"

    stenosis_pct = ["50% to 79%", "80% to 99%", "100%", "Not documented", ""]
    assert data["cvdstenrt"] in stenosis_pct, "Invalid cvdstenrt"
    assert data["cvdstenlft"] in stenosis_pct, "Invalid cvdstenlft"

    assert data["ivdrugab"] in yes_or_empty, "Invalid ivdrugab"
    assert data["alcohol"] in [
        "<= 1 drink/week",
        "2-7 drinks/week",
        ">= 8 drinks/week",
        "None",
        "Unknown",
        "",
    ], "Invalid alcohol"

    assert data["pneumonia"] in [
        "Recent",
        "Remote",
        "No",
        "Unknown",
        "",
    ], "Invalid pneumonia"

    assert data["tobaccouse"] in [
        "Never smoker",
        "Current every day smoker",
        "Current some day smoker",
        "Smoker, current status (frequency) unknown",
        "Former smoker",
        "Smoking status unknown",
        "",
    ], "Invalid tobaccouse"

    assert data["hmo2"] in [
        "Yes, PRN",
        "Yes, oxygen dependent",
        "No",
        "Unknown",
        "",
    ], "Invalid hmo2"

    ## Previous interventions
    assert data["prcvint"] in yes_or_empty, "Invalid prcvint"

    assert data["prcab"] in yes_or_empty, "Invalid prcab"  # cabg
    assert data["prvalve"] in yes_or_empty, "Invalid prvalve"  # valve
    assert data["poc"] in yes_or_empty, "Invalid poc"  # other cardiac
    assert data["pocpci"] in yes_or_empty, "Invalid pocpci"  # pci

    ## Details of previous procedures are not validated yet
    """
    "prvalveproc1": "",
    "prvalveproc2": "",
    "prvalveproc3": "",
    "prvalveproc4": "",
    "prvalveproc5": "",
    "pocint1": "",
    "pocint2": "",
    "pocint3": "",
    "pocint4": "",
    "pocint5": "",
    "pocint6": "",
    "pocint7": "",
    "pocpciwhen": "",
    """
    assert data["pocpciin"] in ["<= 6 Hours", ">6 Hours", ""], "Invalid pocpciin"

    assert data["miwhen"] in [
        "<=6 Hrs",
        ">6 Hrs but <24 Hrs",
        "1 to 7 Days",
        "8 to 21 Days",
        ">21 Days",
        "",
    ], "Invalid miwhen"
    assert data["heartfailtmg"] in [
        "Acute",
        "Chronic",
        "Both",
        "",
    ], "Invalid heartfailtmg"

    assert data["classnyh"] in [
        "Class I",
        "Class II",
        "Class III",
        "Class IV",
        "Not documented",
        "",
    ], "Invalid classnyh"

    # Angina sx not yet validated
    #  "cardsymptimeofadm": "Stable Angina",

    assert data["carshock"] in [
        "Yes - At the time of the procedure",
        "Yes, not at the time of the procedure but within prior 24 hours",
        "",
    ], "Invalid carshock"

    rhythm_onset = ["None", "Remote (> 30 days preop)", "Recent (<= 30 days preop)", ""]
    assert data["arrhythatrfib"] in rhythm_onset, "Invalid arrhythatrfib"
    assert data["arrhythafib"] in ["Persistent", "Paroxysmal", ""], "Invalid arrhythafib"
    assert data["arrhythaflutter"] in rhythm_onset, "Invalid arrhythaflutter"
    assert data["arrhyththird"] in rhythm_onset, "Invalid arrhyththird"
    assert data["arrhythsecond"] in rhythm_onset, "Invalid arrhythsecond"
    assert data["arrhythsss"] in rhythm_onset, "Invalid arrhythsss"
    assert data["arrhythvv"] in rhythm_onset, "Invalid arrhythvv"

    ## Medications
    assert data["medinotr"] in yes_or_empty, "Invalid medinotr"  # Inotropes

    # NOTE: The API allows contraindicated & unknown, which we ignore.  Yes/No/Empty.
    assert data["medadp5days"] in yes_or_empty, "Invalid medadp5days"  # ADPi
    assert (data["medadpidis"] == "") or 1 <= int(
        float(data["medadpidis"])
    ) <= 5, "Invalid medadpidis"

    assert data["medacei48"] in yes_or_empty, "Invalid medacei48"  # ACE
    assert data["medbeta"] in yes_or_empty, "Invalid medbeta"  # BB
    assert data["medster"] in yes_or_empty, "Invalid medster"  # Steroids
    assert data["medgp"] in yes_or_empty, "Invalid medgp"  # GP2B3A

    assert data["resusc"] in [
        "Yes - Within 1 hour of the start of the procedure",
        "Yes - More than 1 hour but less than 24 hours of the start of the procedure",
        "",
    ], "Invalid resusc"

    # Why is this not an int?!!
    assert data["numdisv"] in ["None", "One", "Two", "Three", ""], "Invalid numdisv"
    assert data["stenleftmain"] in ["Yes", "No", "N/A", ""], "Invalid stenleftmain"
    # Left main > 50%
    assert data["laddiststenpercent"] in [
        "50 - 69%",
        ">=70%",
        "",
    ], "Invalid laddiststenpercent"

    # EF
    assert (data["hdef"] == "") or (1.0 <= float(data["hdef"]) <= 99.0), "Invalid hdef"

    ## Valves
    assert data["vdstena"] in yes_or_empty, "Invalid vdstena"  # AS
    assert data["vdstenm"] in yes_or_empty, "Invalid vdstenm"  # MS

    valve_severity = [
        "Trivial/Trace",
        "Mild",
        "Moderate",
        "Severe",
        "Not documented",
        "",
    ]
    assert data["vdinsufa"] in valve_severity, "Invalid vdinsufa"  # AI
    assert data["vdinsufm"] in valve_severity, "Invalid vdinsufm"  # MR
    assert data["vdinsuft"] in valve_severity, "Invalid vdinsuft"  # TR

    valve_indications = [
        "Bicuspid valve disease",
        "Unicuspid valve disease",
        "Quadricuspid valve disease",
        "Congenital (other than Bicuspid, Unicuspid, or Quadricuspid)",
        "Degenerative- Calcified",
        "Degenerative- Leaflet prolapse with or without annular dilatation",
        "Degenerative- Pure annular dilatation without leaflet prolapse",
        "Degenerative - Commissural Rupture",
        "Degenerative - Extensive Fenestration",
        "Degenerative - Leaflet perforation / hole",
        "Endocarditis, native valve with root abscess",
        "Endocarditis, native valve without root abscess",
        "Endocarditis, prosthetic valve with root abscess",
        "Endocarditis, prosthetic valve without root abscess",
        "LV Outflow Tract Pathology, HOCM",
        "LV Outflow Tract Pathology, Sub-aortic membrane",
        "LV Outflow Tract Pathology, Sub-aortic tunnel",
        "LV Outflow Tract Pathology, Other",
        "Primary Aortic Disease, Aortic Dissection",
        "Primary Aortic Disease, Atherosclerotic Aneurysm",
        "Primary Aortic Disease, Ehler-Danlos Syndrome",
        "Primary Aortic Disease, Hypertensive Aneurysm",
        "Primary Aortic Disease, Idiopathic Root dilatation",
        "Primary Aortic Disease, Inflammatory",
        "Primary Aortic Disease, Loeys-Dietz Syndrome",
        "Primary Aortic Disease, Marfan Syndrome",
        "Primary Aortic Disease, Other Connective tissue disorder",
        "Radiation induced heart disease",
        "Reoperation - Failure of previous AV repair or replacement",
        "Rheumatic",
        "Supravalvular Aortic Stenosis",
        "Trauma",
        "Carcinoid",
        "Tumor, Myxoma",
        "Tumor, Papillary Fibroelastoma",
        "Tumor, Other",
        "Mixed Etiology",
        "Not documented",
        "",
    ]
    assert data["vdaoprimet"] in valve_indications, "Invalid vdaoprimet"

    assert data["incidenc"] in [
        "First cardiovascular surgery",
        "First re-op cardiovascular surgery",
        "Second re-op cardiovascular surgery",
        "Third re-op cardiovascular surgery",
        "Fourth or more re-op cardiovascular surgery",
        "NA - Not a cardiovascular surgery",
        "",
    ], "Invalid incidenc"

    assert data["status"] in [
        "Elective",
        "Urgent",
        "Emergent",
        "Emergent Salvage",
        "",
    ], "Invalid status"

    assert data["iabpwhen"] in ["Preop", "Intraop", "Postop", ""], "Invalid iabpwhen"
    assert data["cathbasassistwhen"] in [
        "Preop",
        "Intraop",
        "Postop",
        "",
    ], "Invalid cathbasassistwhen"

    assert data["ecmowhen"] in [
        "Preop",
        "Intraop",
        "Postop",
        "Non-operative",
        "",
    ], "Invalid ecmowhen"

    return data


def main():
    """
    Essentially all heavy lifting happens here -- the argparse parameters encode the right STS API variable names,
    and then calls the minimalist query_sts_api() function to get the results.

    Note that the STS API is a little odd -- it requires *all* parameters to be passed (even if they're empty)
    it includes oddities (race is sometimes "rac"), it does almost nothing client side (except BMI calculation?).

    If you use this code, please consider citing me and this repository.
    """
    parser = argparse.ArgumentParser(
        description="Query the STS Short-Term Risk Calculator (v4.2) via a CSV."
        + "\nPlease cite this repository if you're using in a publication.",
        epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
        usage="%(prog)s [options]",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--csv",
        dest="csv_file",
        metavar="patient-data.csv",
        type=argparse.FileType("r", encoding="utf-8-sig"),
        required=True,
        help="Your input patient data .csv.",
    )

    parser.add_argument(
        "--dry-run",
        dest="dryrun",
        action="store_true",
        help="Only validate data, do not query the STS API.",
    )

    parser.add_argument(
        "--output",
        dest="output_csv_file",
        metavar="results.csv",
        type=str,
        help="Where to store results.",
        default="results.csv",
    )

    parser.add_argument(
        "--override",
        dest="override",
        nargs="+",
        help="Override values sent to the STS API, e.g. "
        + "make all patients the same age with --override age=50",
        metavar="stsvariable=value",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    assert not os.path.exists(
        args.output_csv_file
    ), f"Output file already exists: {args.output_csv_file}"

    ## Parse potential override values, which will take priority over anything passed in the .csv
    override_dict = {}
    if args.override:
        print(
            "NOTE: Override values supplied -- these will be sent to the STS API instead of the values in your .csv"
        )

        for entry in args.override:
            split_entry = entry.split("=")
            assert len(split_entry) == 2, "Can't handle multiple = in override value."
            assert split_entry[0] != "id", "Cannot override patient ID."
            override_dict[split_entry[0]] = split_entry[1]

        assert all(
            key in STS_PARAMS_REQUIRED + STS_PARAMS_OPTIONAL
            for key in override_dict.keys()
        ), "Override value is not one of the defined STS keys."
        print(f"\tOverriding: {override_dict}")

    print("Validating CSV entries...")
    # NOTE: Other than an "ID" column your CSV header must be the same as the STS API parameters,
    # and your CSV entries must *exactly* match the STS query parameters.

    validated_patient_data = []

    csv_dictreader = csv.DictReader(args.csv_file)
    errors_exist = False
    for line_num, row in enumerate(csv_dictreader, start=1):
        overriden_row = row | override_dict
        try:
            assert (row["id"]) != "", "No ID exists for this row. (Is it empty?)"
            validated_patient_data.append(validate_and_return_csv_data(overriden_row))
        except (AssertionError, ValueError) as error_val:
            print(
                f"\tError in .csv line: {line_num}, patient ID: {row['id']}: {error_val}"
            )
            errors_exist = True
    if errors_exist:
        print("Errors exist in your input .csv, unable to query STS API.")
        sys.exit()
    else:
        print("Valid!\n")

    ## Actually query the STS API (if not a dry run)
    if not args.dryrun:
        # A dict of patient_id to the STS risk values
        # e.g. '1': {pred6d: 0.37929, pred14d: 0.04021 …}
        sts_results = {}

        print("Querying STS API.")
        # Query the API for all CSV entries
        for entry in tqdm.tqdm(validated_patient_data):
            patient_id = entry["id"]
            del entry["id"]
            assert patient_id not in sts_results, "Your patient IDs were not unique!"
            sts_results[patient_id] = query_sts_api(entry)

        with open(args.output_csv_file, "w") as csv_output:
            writer = csv.DictWriter(
                csv_output, fieldnames=["id"] + STS_EXPECTED_RESULTS
            )
            writer.writeheader()
            for patient_id, patient_results in sts_results.items():
                # Shove the ID back in for DictWriter
                patient_results["id"] = patient_id
                writer.writerow(patient_results)

        print(f"\nDone!\nResults written to: {args.output_csv_file}")
    else:
        print(f"(Dry run requested, STS API not queried.)")


if __name__ == "__main__":
    main()