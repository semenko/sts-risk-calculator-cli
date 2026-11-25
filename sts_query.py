#!/usr/bin/env python3
#
# Copyright (c) 2022 Nick Semenkovich <semenko@alum.mit.edu>.
#   https://nick.semenkovich.com/
#
# This software is released under the MIT License:
#  <https://opensource.org/licenses/mit-license.php>
#
# Source: https://github.com/semenko/sts-risk-calculator-cli
"""Bulk-query the STS Short-Term Risk Calculator from a CSV of patients.

The calculator is a server-side Shiny app, so this tool mimics a browser:
each CSV row is validated, translated to the app's input values
(`row_to_shiny`), sent over a WebSocket (`query_sts`), and the returned HTML
table is parsed into risk fractions (`parse_sts_html`).
"""

import argparse
import asyncio
import csv
import datetime
import html
import json
import os
import re
import sys
from decimal import Decimal

import tqdm
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

STS_HOST = "acsdriskcalc.research.sts.org"
WS_API_URL = f"wss://{STS_HOST}/websocket/"
WS_HEADERS = {
    "Origin": f"https://{STS_HOST}",
    "Referer": f"https://{STS_HOST}/",
    "User-Agent": "Mozilla/5.0",
}

# Row label in the calculator's result table -> output CSV column.
RESULT_LABELS = {
    "Operative Mortality": "predmort",
    "Morbidity & Mortality": "predmm",
    "Deep Sternal Wound Infection": "preddeep",
    "Long Hospital Stay (>14 days)": "pred14d",
    "Stroke": "predstro",
    "Prolonged Ventilation": "predvent",
    "Renal Failure": "predrenf",
    "Reoperation": "predreop",
    "Short Hospital Stay (<6 days)": "pred6d",
}
STS_EXPECTED_RESULTS = list(RESULT_LABELS.values())


class ValidationError(ValueError):
    """A CSV row (or override) the calculator cannot be queried with."""


class STSError(RuntimeError):
    """The calculator could not be reached or returned no usable result."""


# ---------------------------------------------------------------------------
# What the Shiny app accepts
# ---------------------------------------------------------------------------

# Every <select> input of the app and its options (calculator version 2.0.7).
# The app silently ignores any value not listed here, so nothing else may be
# sent. tests/test_sts_query.py::test_live_options_match detects drift.
SHINY_OPTIONS = {
    "Proc": [
        "Isolated CABG",
        "Isolated AVR",
        "Isolated MVR",
        "AVR + CABG",
        "MVR + CABG",
        "MV Repair",
        "Isolated Primary MR Repair",
        "MV Repair + CABG",
    ],
    "incidenc": [
        "First CV surgery",
        "ReOp#1 CV surgery",
        "ReOp#2 CV surgery",
        "ReOp#3 CV surgery",
        "ReOp≥4 CV surgery",
    ],
    "status": ["Elective", "Urgent", "Emergent", "Emergent Salvage"],
    "gender": ["Male", "Female"],
    "racemulti": [
        "White",
        "Black/African American",
        "Asian",
        "Am Indian/Alaskan",
        "Hawaiian/Pacific Islander",
        "Hispanic",
        "Other",
    ],
    "payordata": [
        "None / self",
        "Medicare (any type)",
        "Medicaid (any type)",
        "Commercial",
        "HMO",
        "Military",
        "Non-U.S. Plan",
        "Other",
    ],
    "diabetes": [
        "No",
        "Yes, Diet Only",
        "Yes, Oral",
        "Yes, Insulin",
        "Yes, Other SubQ",
        "Yes, Other Control",
        "Yes, No Control Method",
        "Yes, Unknown Control",
        "Unknown",
    ],
    "endocarditis": ["No", "Yes, treated", "Yes, active", "Yes, unknown"],
    "ivdrugab": ["No", "Yes", "Unknown"],
    "alcohol": [
        "None",
        "≤ 1 drink/week",
        "2-7 drinks/week",
        "≥ 8 drinks/week",
        "Unknown",
    ],
    "tobaccouse": [
        "Never smoker",
        "Current smoker",
        "Former smoker",
        "Smoking status unknown",
    ],
    "chrlungd": ["No", "Mild", "Moderate", "Severe", "Severity Unknown", "Unknown"],
    "cvd": [
        "No",
        "CVA ≤ 30 days",
        "CVA > 30 days",
        "CVA timing unk",
        "TIA",
        "Other CVD",
    ],
    "heartfailtmg": ["None", "Yes - Acute", "Yes - Chronic", "Yes - Both"],
    "classnyh": ["Class I", "Class II", "Class III", "Class IV"],
    "mcs": ["Catheter based assist device", "ECMO (any)", "IABP", "Other"],
    "cardsymptimeofadm": [
        "No coronary symptoms",
        "Stable Angina",
        "Unstable Angina",
        "Non-ST Elevation MI",
        "STEMI",
        "Angina equivalent",
        "Other",
    ],
    "miwhen": [
        "No MI",
        "≤ 6 Hrs",
        ">6 Hrs but <24 Hrs",
        "1 to 7 Days",
        "8 to 21 Days",
        "> 21 Days",
        "Unknown time",
        "Unknown",
    ],
    "numdisv": ["None", "One", "Two", "Three"],
    "vdinsufa": ["None", "Trivial/Trace", "Mild", "Moderate", "Severe", "Unknown"],
    "vdinsufm": ["None", "Trivial/Trace", "Mild", "Moderate", "Severe", "Unknown"],
    "vdinsuft": ["None", "Trivial/Trace", "Mild", "Moderate", "Severe", "Unknown"],
    "arrhythatrfib": ["None", "Remote", "Recent"],
    "arrhythafib": ["Paroxysmal", "Persistent", "Unknown"],
    "arrhythaflutter": ["None", "Remote", "Recent"],
    "arrhythvv": ["None", "Remote", "Recent"],
    "arrhythsss": ["None", "Remote", "Recent"],
    "arrhythsecond": ["None", "Remote", "Recent"],
    "arrhyththird": ["None", "Remote", "Recent"],
    "prvalveproc": [
        "Aortic valve balloon valvotomy/valvuloplasty",
        "Aortic valve repair, surgical",
        "Aortic valve replacement, surgical",
        "Mitral valve balloon valvotomy/valvuloplasty",
        "Mitral valve commissurotomy, surgical",
        "Mitral valve repair, surgical",
        "Mitral valve replacement, surgical",
        "Tricuspid valve balloon valvotomy/valvuloplasty",
        "Tricuspid valve repair, surgical",
        "Tricuspid valve replacement, surgical",
        "Tricuspid valvectomy",
        "Pulmonary valve balloon valvotomy/valvuloplasty",
        "Pulmonary valve repair, surgical",
        "Pulmonary valve replacement, surgical",
        "Pulmonary valvectomy",
        "Other valve procedure",
    ],
    "pocpci": [
        "At this facility ≤ 6 hours",
        "At this facility > 6 hours",
        "At this facility timing unknown",
        "Not at this facility ≤ 6 hours",
        "Not at this facility > 6 hours",
        "Not at this facility timing unknown",
        "Not during this episode of care",
    ],
    "pocint": [
        "Ablation, catheter, atrial arrhythmia",
        "Ablation, catheter, other or unknown",
        "Ablation, catheter, ventricular arrhythmia",
        "Ablation, surgical, atrial arrhythmia",
        "Ablation, surgical, other or unknown",
        "Aneurysmectomy, LV",
        "Aortic procedure, arch",
        "Aortic procedure, ascending",
        "Aortic procedure, descending",
        "Aortic procedure, root",
        "Aortic procedure, thoracoabdominal",
        "Aortic Procedure, TEVAR",
        "Aortic root procedure, valve sparing",
        "Atrial appendage obliteration, left, surgical",
        "Atrial appendage obliteration, left, transcatheter",
        "Cardiac Tumor",
        "Cardioversion(s)",
        "Closure device, atrial septal defect",
        "Closure device, ventricular septal defect",
        "Congenital cardiac repair, surgical",
        "ECMO",
        "Myectomy (not congenital)",
        "Permanent Pacemaker",
        "Pericardial window / Pericardiocentesis",
        "Pericardiectomy",
        "Implantable Cardioverter Defibrillator (ICD) with or without pacer",
        "Pulmonary Thromboembolectomy",
        "Total Artificial Heart (TAH)",
        "Transmyocardial Laser Revascularization (TMR)",
        "Transplant heart & lung",
        "Transplant, heart",
        "Transplant, lung(s)",
        "Ventricular Assist Device (VAD), BiVAD",
        "Ventricular Assist Device (VAD), left",
        "Ventricular Assist Device (VAD), right",
        "Other Cardiac Intervention (not listed)",
    ],
}

PROCEDURES = {
    "1": "Isolated CABG",
    "2": "Isolated AVR",
    "3": "Isolated MVR",
    "4": "AVR + CABG",
    "5": "MVR + CABG",
    # There is no 6.
    "7": "MV Repair",
    "8": "MV Repair + CABG",
}

# ---------------------------------------------------------------------------
# The CSV format (parameter names and values of the retired STS REST API,
# plus the current Shiny values where the two differ)
# ---------------------------------------------------------------------------

# CSV column -> (Shiny numeric input, minimum, maximum)
NUMERIC_FIELDS = {
    "age": ("ageN", 1, 110),
    "heightcm": ("heightN", 20, 251),
    "weightkg": ("weightN", 10, 250),
    "creatlst": ("creatlstN", 0.1, 30),
    "hct": ("hctN", 1, 100),
    "wbc": ("wbcN", 0.1, 100),
    "platelets": ("plateletsN", 1000, 900000),
    "medadpidis": ("medadpidis", 0, 5),
    "hdef": ("hdef", 1, 99),
}

VALVE_ETIOLOGIES_ROOT_ABSCESS = (
    "Endocarditis, native valve with root abscess",
    "Endocarditis, prosthetic valve with root abscess",
)
VALVE_ETIOLOGIES_OTHER = (
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
    "Endocarditis, native valve without root abscess",
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
)

_YES = (("Yes",), ())
_CAROTID = (("80% to 99%", "100%"), ("50% to 79%", "Not documented"))

# CSV column (= Shiny checkbox) -> (values that tick it, other accepted values).
# The second group is accepted for compatibility but leaves the box unticked,
# because the app's checkbox is narrower than the old multi-valued field.
CHECKBOX_FIELDS = {
    "medacei48": _YES,
    "medgp": _YES,
    "medinotr": _YES,
    "medster": _YES,
    "medadp5days": _YES,
    "fhcad": _YES,
    "hypertn": _YES,
    "liverdis": _YES,
    "mediastrad": _YES,
    "unrespstat": _YES,
    "dialysis": _YES,
    "cancer": _YES,
    "syncope": _YES,
    "immsupp": _YES,
    "slpapn": _YES,
    "pvd": _YES,
    "cvdpcarsurg": _YES,
    "vdstena": _YES,
    "vdstenm": _YES,
    # "Left Main Sten. >= 50%"
    "stenleftmain": (("Yes",), ("No", "N/A")),
    # "Home O2"
    "hmo2": (("Yes", "Yes, PRN", "Yes, oxygen dependent"), ("No", "Unknown")),
    # "Recent Pneumonia" (within 30 days)
    "pneumonia": (("Yes", "Recent"), ("Remote", "No", "Unknown")),
    # "Cardiogenic Shock" at the time of the procedure
    "carshock": (
        ("Yes", "Yes - At the time of the procedure"),
        ("Yes, not at the time of the procedure but within prior 24 hours",),
    ),
    # "Resuscitation <= 1hr"
    "resusc": (
        ("Yes", "Yes - Within 1 hour of the start of the procedure"),
        (
            "Yes - More than 1 hour but less than 24 hours of the start of the procedure",
        ),
    ),
    # "Right/Left Carotid Sten. >= 80%"
    "cvdstenrt": _CAROTID,
    "cvdstenlft": _CAROTID,
    # "Proximal LAD Sten. >= 70%"
    "laddiststenpercent": ((">=70%",), ("50 - 69%",)),
    # "Aortic Root Abscess"
    "vdaoprimet": (VALVE_ETIOLOGIES_ROOT_ABSCESS, VALVE_ETIOLOGIES_OTHER),
}

_ARRHYTHMIA_TIMING = {
    "Remote (> 30 days preop)": "Remote",
    "Recent (<= 30 days preop)": "Recent",
}
_VALVE_INSUFFICIENCY = {"Not documented": "Unknown"}

# CSV column (= single-choice Shiny select) -> {legacy CSV value: Shiny value}.
# Every option of the Shiny select is accepted as-is too. A legacy value
# mapped to None has no Shiny equivalent and is accepted but not sent.
SELECT_FIELDS = {
    "gender": {},
    "status": {},
    "incidenc": {
        "First cardiovascular surgery": "First CV surgery",
        "First re-op cardiovascular surgery": "ReOp#1 CV surgery",
        "Second re-op cardiovascular surgery": "ReOp#2 CV surgery",
        "Third re-op cardiovascular surgery": "ReOp#3 CV surgery",
        "Fourth or more re-op cardiovascular surgery": "ReOp≥4 CV surgery",
        "ReOp#4+ CV surgery": "ReOp≥4 CV surgery",
        "NA - Not a cardiovascular surgery": None,
        "Not CV surgery": None,
    },
    "ivdrugab": {},
    "alcohol": {
        "<= 1 drink/week": "≤ 1 drink/week",
        ">= 8 drinks/week": "≥ 8 drinks/week",
    },
    "tobaccouse": {
        "Current every day smoker": "Current smoker",
        "Current some day smoker": "Current smoker",
        "Smoker, current status (frequency) unknown": "Current smoker",
    },
    "chrlungd": {"Lung disease documented, severity unknown": "Severity Unknown"},
    "heartfailtmg": {
        "Acute": "Yes - Acute",
        "Chronic": "Yes - Chronic",
        "Both": "Yes - Both",
    },
    "classnyh": {"Not documented": None},
    "cardsymptimeofadm": {
        "No Symptoms": "No coronary symptoms",
        "Stable angina": "Stable Angina",
        "Unstable angina": "Unstable Angina",
        "Non-ST Elevation MI (Non-STEMI)": "Non-ST Elevation MI",
        "ST Elevation MI (STEMI)": "STEMI",
        "Angina Equivalent": "Angina equivalent",
    },
    "miwhen": {"<=6 Hrs": "≤ 6 Hrs", ">21 Days": "> 21 Days"},
    "numdisv": {},
    "vdinsufa": _VALVE_INSUFFICIENCY,
    "vdinsufm": _VALVE_INSUFFICIENCY,
    "vdinsuft": _VALVE_INSUFFICIENCY,
    "arrhythatrfib": _ARRHYTHMIA_TIMING,
    "arrhythafib": {},
    "arrhythaflutter": _ARRHYTHMIA_TIMING,
    "arrhythvv": _ARRHYTHMIA_TIMING,
    "arrhythsss": _ARRHYTHMIA_TIMING,
    "arrhythsecond": _ARRHYTHMIA_TIMING,
    "arrhyththird": _ARRHYTHMIA_TIMING,
}

# Several CSV columns are merged into one multi-choice Shiny select.
RACES = {
    "raceasian": "Asian",
    "raceblack": "Black/African American",
    "racenativeam": "Am Indian/Alaskan",
    "racnativepacific": "Hawaiian/Pacific Islander",  # (sic) STS dropped the "e"
    "ethnicity": "Hispanic",
}
PAYORS = {
    "Commercial Health Insurance": "Commercial",
    "Medicare (includes commercially managed options)": "Medicare (any type)",
    "Medicaid (includes commercially managed options)": "Medicaid (any type)",
    "Health Maintenance Organization": "HMO",
}
DIABETES_CONTROL = {  # diabetes=Yes + diabctrl
    "": "Yes, Unknown Control",
    "None": "Yes, No Control Method",
    "Diet only": "Yes, Diet Only",
    "Diet Only": "Yes, Diet Only",
    "Oral": "Yes, Oral",
    "Insulin": "Yes, Insulin",
    "Other SubQ": "Yes, Other SubQ",
    "Other": "Yes, Other Control",
    "Unknown": "Yes, Unknown Control",
}
ENDOCARDITIS_TYPE = {  # infendo=Yes + infendty
    "": "Yes, unknown",
    "Treated": "Yes, treated",
    "Active": "Yes, active",
}
CVA_TIMING = {  # cva=Yes + cvawhen
    "": "CVA timing unk",
    "<= 30 days": "CVA ≤ 30 days",
    "> 30 days": "CVA > 30 days",
}
MCS_DEVICES = {  # column -> (device, accepted timings); any timing selects it
    "iabpwhen": ("IABP", ("Preop", "Intraop", "Postop")),
    "cathbasassistwhen": (
        "Catheter based assist device",
        ("Preop", "Intraop", "Postop"),
    ),
    "ecmowhen": ("ECMO (any)", ("Preop", "Intraop", "Postop", "Non-operative")),
}
PRIOR_INTERVENTIONS = {
    "prcab": "CABG",
    "prvalve": "Valve",
    "pocpci": "PCI",
    "poc": "Other",
}
PCI_FACILITY = {  # pocpciwhen + pocpciin
    "Yes, at this facility": "At this facility",
    "Yes, at some other acute care facility": "Not at this facility",
}
PCI_INTERVAL = {
    "": "timing unknown",
    "<= 6 Hours": "≤ 6 hours",
    ">6 Hours": "> 6 hours",
    "> 6 Hours": "> 6 hours",
}
PRIOR_VALVE_COLUMNS = [f"prvalveproc{i}" for i in range(1, 6)]
PRIOR_OTHER_COLUMNS = [f"pocint{i}" for i in range(1, 8)]

# Accepted non-empty values of every non-numeric column ("" is always
# accepted). None means free text.
CSV_CHOICES = {
    "id": None,
    "procid": tuple(PROCEDURES),
    **{col: ticked + other for col, (ticked, other) in CHECKBOX_FIELDS.items()},
    **{
        col: tuple(dict.fromkeys([*SHINY_OPTIONS[col], *legacy]))
        for col, legacy in SELECT_FIELDS.items()
    },
    **{col: ("Yes",) for col in RACES},
    "payorprim": tuple(dict.fromkeys([*SHINY_OPTIONS["payordata"], *PAYORS])),
    "payorsecond": tuple(dict.fromkeys([*SHINY_OPTIONS["payordata"], *PAYORS])),
    "diabetes": ("Yes",),
    "diabctrl": tuple(v for v in DIABETES_CONTROL if v),
    "infendo": ("Yes",),
    "infendty": tuple(v for v in ENDOCARDITIS_TYPE if v),
    "cvd": ("Yes",),
    "cvdtia": ("Yes",),
    "cva": ("Yes",),
    "cvawhen": tuple(v for v in CVA_TIMING if v),
    **{col: timings for col, (_, timings) in MCS_DEVICES.items()},
    **{col: ("Yes",) for col in PRIOR_INTERVENTIONS},
    "pocpciwhen": (*PCI_FACILITY, "No", *SHINY_OPTIONS["pocpci"]),
    "pocpciin": tuple(v for v in PCI_INTERVAL if v),
    **{col: tuple(SHINY_OPTIONS["prvalveproc"]) for col in PRIOR_VALVE_COLUMNS},
    **{col: tuple(SHINY_OPTIONS["pocint"]) for col in PRIOR_OTHER_COLUMNS},
    # Accepted for compatibility with the old REST API; the app has no such input.
    "surgdt": None,
    "prcvint": ("Yes",),
    "medbeta": ("Yes",),
    "calculatedbmi": None,
}
CSV_COLUMNS = {*CSV_CHOICES, *NUMERIC_FIELDS}

# (columns, column that must be set whenever any of them is)
DEPENDENCIES = [
    (["payorsecond"], "payorprim"),
    (["cvdtia", "cvdpcarsurg"], "cvd"),
    (["cvawhen"], "cva"),
    (["diabctrl"], "diabetes"),
    (["infendty"], "infendo"),
    # The app ignores these details unless the matching prior intervention is ticked.
    (PRIOR_VALVE_COLUMNS, "prvalve"),
    (PRIOR_OTHER_COLUMNS, "poc"),
    (["pocpciwhen"], "pocpci"),
    (["pocpciin"], "pocpciwhen"),
]

# The state a browser reports when the page first loads: everything empty.
SHINY_INIT = {
    **{name: [] for name in SHINY_OPTIONS},
    "prcvint": [],
    **{name: False for name in CHECKBOX_FIELDS},
    "vstrpr": False,
    **{f"{name}:shiny.number": None for name, _, _ in NUMERIC_FIELDS.values()},
    "BMI:shiny.number": None,
    "tab": "Clinical Summary",
    "decline:shiny.action": 0,
    "reset:shiny.action": 0,
    "copybuttonestimates:shiny.action": 0,
    "copybuttonsummary:shiny.action": 0,
    ".clientdata_output_errorMessage_hidden": False,
    ".clientdata_output_text2_hidden": False,
    ".clientdata_output_summary_hidden": False,
    ".clientdata_pixelratio": 1,
    ".clientdata_url_protocol": "https:",
    ".clientdata_url_hostname": STS_HOST,
    ".clientdata_url_port": "",
    ".clientdata_url_pathname": "/",
    ".clientdata_url_search": "",
    ".clientdata_url_hash_initial": "",
    ".clientdata_url_hash": "",
    ".clientdata_singletons": "add739c82ab207ed2c80be4b7e4b181525eb7a75",
}


def _describe(options):
    if len(options) > 12:
        return "see the README for accepted values"
    return "expected one of: " + ", ".join(map(repr, options)) + ", or empty"


def row_to_shiny(row):
    """Validate one CSV row and translate it to the Shiny inputs to set.

    `row` maps CSV column -> string; missing columns count as empty. Returns
    the data of a Shiny "update" message. Raises ValidationError naming every
    problem in the row.
    """
    errors = []
    unknown = sorted(set(row) - CSV_COLUMNS)
    if unknown:
        errors.append(f"unknown column(s): {', '.join(unknown)}")
    data = {col: (row.get(col) or "").strip() for col in CSV_COLUMNS}

    for col in ("procid", "age"):
        if not data[col]:
            errors.append(f"{col} is required")

    for col, options in CSV_CHOICES.items():
        if options is not None and data[col] and data[col] not in options:
            errors.append(f"invalid {col} {data[col]!r} ({_describe(options)})")

    update = {}
    for col, (input_id, low, high) in NUMERIC_FIELDS.items():
        if not data[col]:
            continue
        try:
            number = float(data[col])
        except ValueError:
            number = float("nan")
        if low <= number <= high:
            update[f"{input_id}:shiny.number"] = (
                int(number) if number.is_integer() else number
            )
        else:
            errors.append(
                f"invalid {col} {data[col]!r} (expected a number from {low} to {high})"
            )

    if data["surgdt"]:
        try:
            datetime.datetime.strptime(data["surgdt"], "%m/%d/%Y")
        except ValueError:
            errors.append(f"invalid surgdt {data['surgdt']!r} (expected MM/DD/YYYY)")

    for columns, parent in DEPENDENCIES:
        used = [col for col in columns if data[col]]
        if used and not data[parent]:
            errors.append(f"{parent} must be set when {', '.join(used)} is set")

    if errors:
        raise ValidationError("; ".join(errors))

    update["Proc"] = [PROCEDURES[data["procid"]]]
    if data["heightcm"] and data["weightkg"]:
        # The browser computes BMI client-side.
        bmi = float(data["weightkg"]) / (float(data["heightcm"]) / 100) ** 2
        update["BMI:shiny.number"] = round(bmi, 2)

    for col, (ticked, _) in CHECKBOX_FIELDS.items():
        if data[col] in ticked:
            update[col] = True

    for col, legacy in SELECT_FIELDS.items():
        value = legacy.get(data[col], data[col])
        if value:
            update[col] = [value]

    multi = {
        "racemulti": [race for col, race in RACES.items() if data[col]],
        "payordata": [
            PAYORS.get(data[col], data[col])
            for col in ("payorprim", "payorsecond")
            if data[col]
        ],
        "diabetes": [DIABETES_CONTROL[data["diabctrl"]]] if data["diabetes"] else [],
        "endocarditis": (
            [ENDOCARDITIS_TYPE[data["infendty"]]] if data["infendo"] else []
        ),
        "cvd": [CVA_TIMING[data["cvawhen"]]] * bool(data["cva"])
        + ["TIA"] * bool(data["cvdtia"]),
        "mcs": [device for col, (device, _) in MCS_DEVICES.items() if data[col]],
        "prcvint": [
            name for col, name in PRIOR_INTERVENTIONS.items() if data[col] == "Yes"
        ],
        "prvalveproc": [data[col] for col in PRIOR_VALVE_COLUMNS if data[col]],
        "pocint": [data[col] for col in PRIOR_OTHER_COLUMNS if data[col]],
    }
    if data["cvd"] and not multi["cvd"]:
        multi["cvd"] = ["Other CVD"]

    pci = data["pocpciwhen"]
    if pci in PCI_FACILITY:
        pci = f"{PCI_FACILITY[pci]} {PCI_INTERVAL[data['pocpciin']]}"
    elif pci == "No":
        pci = "Not during this episode of care"
    multi["pocpci"] = [pci] if pci else []

    # Drop duplicates (e.g. the same payor twice), keeping order.
    update.update(
        {name: list(dict.fromkeys(values)) for name, values in multi.items() if values}
    )
    return update


# ---------------------------------------------------------------------------
# Talking to the calculator
# ---------------------------------------------------------------------------


def parse_sts_html(html_content):
    """Extract {result column: risk as a fraction} from the app's result table.

    The table is a flat sequence of <td> cells: a label, then its percentage.
    """
    cells = [
        html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", html_content, re.DOTALL)
    ]
    result = {}
    for label, value in zip(cells, cells[1:]):
        key = next((k for known, k in RESULT_LABELS.items() if known in label), None)
        percent = re.search(r"(\d+(?:\.\d+)?)\s*%", value)
        if key and percent and key not in result:
            # Decimal avoids float noise such as 0.027000000000000003.
            result[key] = float(Decimal(percent.group(1)) / 100)
    return result


async def _query_once(init_msg, update_msg):
    async with connect(
        WS_API_URL, additional_headers=WS_HEADERS, open_timeout=30
    ) as ws:
        await ws.send(init_msg)
        await asyncio.sleep(1)  # Give the server time to process init
        await ws.send(update_msg)

        # Skip progress chatter and the initial "Selection Required" error
        # until the rendered result table arrives.
        for _ in range(30):
            try:
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                table = message["values"]["text2"]["html"]
            except (ValueError, KeyError, TypeError):
                continue
            result = parse_sts_html(table)
            if result:
                return result
    raise STSError("No valid response from the STS calculator")


async def query_sts(update, debug=False, max_retries=3):
    """Send one patient's Shiny inputs (from `row_to_shiny`); return its risks.

    Retries transient network errors with exponential backoff. Raises STSError.
    """
    init_msg = json.dumps({"method": "init", "data": SHINY_INIT})
    update_msg = json.dumps({"method": "update", "data": update})
    if debug:
        headers = " ".join(f'-H "{k}: {v}"' for k, v in WS_HEADERS.items())
        print(f"\nTo replicate: wscat -c {WS_API_URL} {headers}", file=sys.stderr)
        print(init_msg, update_msg, sep="\n", file=sys.stderr)

    for attempt in range(1, max_retries + 1):
        try:
            return await _query_once(init_msg, update_msg)
        except (OSError, asyncio.TimeoutError, ConnectionClosed, InvalidHandshake) as e:
            if attempt == max_retries:
                raise STSError(
                    f"STS request failed after {max_retries} attempts: {e!r}"
                ) from e
            if debug:
                print(f"Attempt {attempt} failed ({e!r}), retrying", file=sys.stderr)
            await asyncio.sleep(2 ** (attempt - 1))


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def parse_overrides(entries):
    """Parse ["column=value", ...] into a dict. Raises ValidationError."""
    overrides = {}
    for entry in entries or []:
        column, separator, value = entry.partition("=")
        column = column.strip()
        if not separator:
            raise ValidationError(f"override {entry!r} is not of the form column=value")
        if column == "id":
            raise ValidationError("cannot override the patient id")
        if column not in CSV_COLUMNS:
            raise ValidationError(f"override {column!r} is not a known column")
        overrides[column] = value
    return overrides


def read_patients(csv_file, overrides=None):
    """Read and validate a patient CSV.

    Returns ([(patient id, Shiny update)], [error message]).
    """
    reader = csv.DictReader(csv_file, restval="")
    columns = [(name or "").strip() for name in reader.fieldnames or []]
    reader.fieldnames = columns
    unknown = sorted(set(columns) - CSV_COLUMNS)
    if "id" not in columns:
        return [], ["The CSV needs an 'id' column."]
    if unknown:
        return [], [f"Columns that are not STS parameters: {', '.join(unknown)}"]

    patients, errors, seen = [], [], set()
    for row in reader:
        where = f"line {reader.line_num}, patient ID {row['id'].strip() or '?'}"
        try:
            if None in row:
                raise ValidationError("more values than columns in the header")
            patient_id = row.pop("id").strip()
            if not patient_id:
                raise ValidationError("no id for this row (is it empty?)")
            if patient_id in seen:
                raise ValidationError("duplicate patient id")
            seen.add(patient_id)
            patients.append((patient_id, row_to_shiny(row | (overrides or {}))))
        except ValidationError as error:
            errors.append(f"{where}: {error}")
    return patients, errors


async def query_patients(patients, output, debug=False):
    """Query every patient, writing each result to `output` as it arrives."""
    writer = csv.DictWriter(output, fieldnames=["id", *STS_EXPECTED_RESULTS])
    writer.writeheader()
    for i, (patient_id, update) in enumerate(tqdm.tqdm(patients)):
        if i:
            # Be gentle with the Shiny backend; this also reduces transient
            # handshake timeouts on large batches.
            await asyncio.sleep(0.3)
        try:
            result = await query_sts(update, debug=debug)
        except STSError as error:
            raise STSError(f"patient ID {patient_id}: {error}") from error
        writer.writerow({"id": patient_id, **result})
        output.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Query the STS Short-Term Risk Calculator via a CSV. "
        "Please cite this repository if you use it in a publication.",
        epilog="Written by Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--csv",
        dest="csv_file",
        metavar="patient-data.csv",
        required=True,
        help="Your input patient data .csv.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dryrun",
        action="store_true",
        help="Only validate data, do not query the STS calculator.",
    )
    parser.add_argument(
        "--output",
        dest="output_csv_file",
        metavar="results.csv",
        default="results.csv",
        help="Where to store results (must not exist yet).",
    )
    parser.add_argument(
        "--override",
        nargs="+",
        metavar="stsvariable=value",
        help="Override values for every patient, e.g. --override age=50",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print the WebSocket messages sent for each patient.",
    )
    if argv is None and len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return 1
    args = parser.parse_args(argv)

    if not args.dryrun and os.path.exists(args.output_csv_file):
        parser.error(f"Output file already exists: {args.output_csv_file}")
    try:
        overrides = parse_overrides(args.override)
    except ValidationError as error:
        parser.error(str(error))
    if overrides:
        print(f"NOTE: overriding these values for every patient: {overrides}")

    print("Validating CSV entries...")
    try:
        with open(args.csv_file, encoding="utf-8-sig", newline="") as csv_file:
            patients, errors = read_patients(csv_file, overrides)
    except OSError as error:
        parser.error(str(error))
    if errors:
        for error in errors:
            print(f"\tError: {error}", file=sys.stderr)
        print("Errors exist in your input .csv, STS not queried.", file=sys.stderr)
        return 1
    print(f"Valid! ({len(patients)} patients)\n")

    if args.dryrun:
        print("(Dry run requested, STS calculator not queried.)")
        return 0

    print("Querying STS calculator.")
    with open(args.output_csv_file, "x", encoding="utf-8", newline="") as output:
        try:
            asyncio.run(query_patients(patients, output, debug=args.debug))
        except (STSError, KeyboardInterrupt) as error:
            print(
                f"\nStopped: {error or 'interrupted'}\n"
                f"Results so far were kept in: {args.output_csv_file}",
                file=sys.stderr,
            )
            return 1
    print(f"\nDone!\nResults written to: {args.output_csv_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
