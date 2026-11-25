"""Offline tests. Set STS_LIVE=1 to also run the tests that contact the STS site."""

import asyncio
import html
import io
import os
import re
import urllib.request

import pytest

import sts_query as sts

live = pytest.mark.skipif(not os.environ.get("STS_LIVE"), reason="set STS_LIVE=1")

BASE = {"procid": "1", "age": "60"}
SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data.csv")


def shiny(**columns):
    return sts.row_to_shiny(BASE | columns)


def test_minimal_row():
    assert shiny() == {"Proc": ["Isolated CABG"], "ageN:shiny.number": 60}


def test_every_accepted_value_maps_to_a_real_shiny_option():
    """The app silently ignores unknown options, so we must never send one."""
    parents = {
        child: parent for children, parent in sts.DEPENDENCIES for child in children
    }
    for column, values in sts.CSV_CHOICES.items():
        for value in values or ():
            row = {column: value}
            needed = column
            while needed in parents:  # satisfy the dependency chain
                needed = parents[needed]
                row.setdefault(needed, sts.CSV_CHOICES[needed][0])
            for name, sent in shiny(**row).items():
                if name in sts.SHINY_OPTIONS:
                    assert set(sent) <= set(sts.SHINY_OPTIONS[name]), (row, name, sent)


@pytest.mark.parametrize(
    "columns, name, expected",
    [
        (
            {"incidenc": "Fourth or more re-op cardiovascular surgery"},
            "incidenc",
            ["ReOp≥4 CV surgery"],
        ),
        ({"incidenc": "NA - Not a cardiovascular surgery"}, "incidenc", None),
        ({"diabetes": "Yes"}, "diabetes", ["Yes, Unknown Control"]),
        (
            {"diabetes": "Yes", "diabctrl": "None"},
            "diabetes",
            ["Yes, No Control Method"],
        ),
        ({"diabetes": "Yes", "diabctrl": "Diet only"}, "diabetes", ["Yes, Diet Only"]),
        ({"infendo": "Yes"}, "endocarditis", ["Yes, unknown"]),
        ({"infendo": "Yes", "infendty": "Active"}, "endocarditis", ["Yes, active"]),
        ({"cva": "Yes"}, "cvd", ["CVA timing unk"]),
        (
            {"cva": "Yes", "cvawhen": "<= 30 days", "cvd": "Yes", "cvdtia": "Yes"},
            "cvd",
            ["CVA ≤ 30 days", "TIA"],
        ),
        ({"cvd": "Yes"}, "cvd", ["Other CVD"]),
        ({"classnyh": "Not documented"}, "classnyh", None),
        ({"vdinsufm": "Not documented"}, "vdinsufm", ["Unknown"]),
        ({"tobaccouse": "Current some day smoker"}, "tobaccouse", ["Current smoker"]),
        (
            {"raceblack": "Yes", "ethnicity": "Yes"},
            "racemulti",
            ["Black/African American", "Hispanic"],
        ),
        (
            {"payorprim": "Commercial Health Insurance", "payorsecond": "Commercial"},
            "payordata",
            ["Commercial"],
        ),
        (
            {"iabpwhen": "Preop", "ecmowhen": "Non-operative"},
            "mcs",
            ["IABP", "ECMO (any)"],
        ),
        ({"prcab": "Yes", "pocpci": "Yes"}, "prcvint", ["CABG", "PCI"]),
        (
            {
                "pocpci": "Yes",
                "pocpciwhen": "Yes, at this facility",
                "pocpciin": "<= 6 Hours",
            },
            "pocpci",
            ["At this facility ≤ 6 hours"],
        ),
        (
            {"pocpci": "Yes", "pocpciwhen": "No"},
            "pocpci",
            ["Not during this episode of care"],
        ),
        # Checkboxes are narrower than the old multi-valued fields.
        ({"cvdstenrt": "80% to 99%"}, "cvdstenrt", True),
        ({"cvdstenrt": "50% to 79%"}, "cvdstenrt", None),
        ({"laddiststenpercent": ">=70%"}, "laddiststenpercent", True),
        ({"laddiststenpercent": "50 - 69%"}, "laddiststenpercent", None),
        (
            {"vdaoprimet": "Endocarditis, native valve with root abscess"},
            "vdaoprimet",
            True,
        ),
        ({"vdaoprimet": "Rheumatic"}, "vdaoprimet", None),
        ({"pneumonia": "Recent"}, "pneumonia", True),
        ({"pneumonia": "Remote"}, "pneumonia", None),
        ({"hmo2": "Yes, PRN"}, "hmo2", True),
        ({"stenleftmain": "No"}, "stenleftmain", None),
        # Numbers
        ({"age": "56.0"}, "ageN:shiny.number", 56),
        ({"hct": "38.5"}, "hctN:shiny.number", 38.5),
        ({"medadpidis": "3.0"}, "medadpidis:shiny.number", 3),
        ({"heightcm": "160", "weightkg": "102.4"}, "BMI:shiny.number", 40.0),
    ],
)
def test_translation(columns, name, expected):
    assert shiny(**columns).get(name) == expected


@pytest.mark.parametrize(
    "columns, message",
    [
        ({"procid": "6"}, "invalid procid"),
        ({"procid": ""}, "procid is required"),
        ({"age": ""}, "age is required"),
        ({"age": "111"}, "invalid age"),
        ({"age": "old"}, "invalid age"),
        ({"hct": "nan"}, "invalid hct"),
        ({"gender": "male"}, "invalid gender"),
        ({"surgdt": "2021-07-21"}, "invalid surgdt"),
        ({"bogus": "1"}, "unknown column"),
        ({"diabctrl": "Oral"}, "diabetes must be set"),
        ({"payorsecond": "Other"}, "payorprim must be set"),
        ({"cvdtia": "Yes"}, "cvd must be set"),
        ({"prvalveproc1": "Tricuspid valvectomy"}, "prvalve must be set"),
        ({"pocint2": "Transplant, heart"}, "poc must be set"),
        ({"pocpci": "Yes", "pocpciin": ">6 Hours"}, "pocpciwhen must be set"),
    ],
)
def test_validation_errors(columns, message):
    with pytest.raises(sts.ValidationError, match=re.escape(message)):
        shiny(**columns)


def test_all_errors_in_a_row_are_reported():
    with pytest.raises(sts.ValidationError) as error:
        shiny(age="0", gender="X")
    assert "invalid age" in str(error.value) and "invalid gender" in str(error.value)


def test_surgdt_is_optional_and_unpadded_dates_are_fine():
    shiny(surgdt="7/21/2021")


def test_overrides():
    assert sts.parse_overrides(
        ["age=50", "cvawhen=<= 30 days", "laddiststenpercent=>=70%"]
    ) == {
        "age": "50",
        "cvawhen": "<= 30 days",
        "laddiststenpercent": ">=70%",
    }
    for bad in ("age", "id=3", "bogus=1"):
        with pytest.raises(sts.ValidationError):
            sts.parse_overrides([bad])


def test_read_patients_reports_line_numbers_and_duplicates():
    text = "id, procid,age\n1,1,60\n1,1,61\n,1,62\n4,1,999\n5,1,63,extra\n6,2, 64 \n"
    patients, errors = sts.read_patients(io.StringIO(text), {"gender": "Female"})
    assert [patient_id for patient_id, _ in patients] == ["1", "6"]
    assert patients[1][1] == {
        "Proc": ["Isolated AVR"],
        "ageN:shiny.number": 64,
        "gender": ["Female"],
    }
    assert [error.split(":")[0] for error in errors] == [
        "line 3, patient ID 1",
        "line 4, patient ID ?",
        "line 5, patient ID 4",
        "line 6, patient ID 5",
    ]


def test_read_patients_header_problems():
    assert sts.read_patients(io.StringIO("procid,age\n1,60\n"))[1] == [
        "The CSV needs an 'id' column."
    ]
    assert "bogus" in sts.read_patients(io.StringIO("id,procid,age,bogus\n"))[1][0]


def test_parse_sts_html():
    table = (
        '<table><tr><td class="l"><b>Operative Mortality</b></td><td class="r">2.7%</td></tr>'
        "<tr><td>Morbidity &amp; Mortality</td><td> 10.089 % </td></tr>"
        "<tr><td>Long Hospital Stay (&gt;14 days)</td><td>0.698%</td></tr>"
        "<tr><td>Something else</td><td>5%</td></tr></table>"
    )
    assert sts.parse_sts_html(table) == {
        "predmort": 0.027,
        "predmm": 0.10089,
        "pred14d": 0.00698,
    }
    assert sts.parse_sts_html("<p>Selection Required</p>") == {}


def test_cli_dry_run(tmp_path, capsys):
    existing = tmp_path / "results.csv"
    existing.write_text("keep me")
    # A dry run writes nothing, so an existing output file is not an error.
    assert sts.main(["--csv", SAMPLE, "--dry-run", "--output", str(existing)]) == 0
    assert existing.read_text() == "keep me"

    bad = tmp_path / "bad.csv"
    bad.write_text("﻿id,procid,age\n7,9,60\n", encoding="utf-8")
    assert sts.main(["--csv", str(bad), "--dry-run"]) == 1
    assert "line 2, patient ID 7: invalid procid '9'" in capsys.readouterr().err

    with pytest.raises(SystemExit):  # refuses to overwrite results
        sts.main(["--csv", SAMPLE, "--output", str(existing)])


@live
def test_live_options_match():
    """Fails when STS changes the app's inputs: update SHINY_OPTIONS and the mappings."""
    request = urllib.request.Request(
        f"https://{sts.STS_HOST}/", headers={"User-Agent": "Mozilla/5.0"}
    )
    page = urllib.request.urlopen(request, timeout=30).read().decode("utf-8")
    selects = {
        name: [
            html.unescape(option)
            for option in re.findall(r'<option value="([^"]*)"', body)
        ]
        for name, body in re.findall(
            r'<select[^>]*id="([^"]+)"[^>]*>(.*?)</select>', page, re.DOTALL
        )
    }
    assert selects == sts.SHINY_OPTIONS
    for name in [*sts.CHECKBOX_FIELDS, *(i for i, _, _ in sts.NUMERIC_FIELDS.values())]:
        assert f'id="{name}"' in page, name


@live
def test_live_query():
    result = asyncio.run(
        sts.query_sts(shiny(gender="Male", incidenc="ReOp≥4 CV surgery"))
    )
    assert set(result) == set(sts.STS_EXPECTED_RESULTS)
    assert all(0 < risk < 1 for risk in result.values())
    # Guards against the app silently ignoring an input (first-time CABG is 0.0025).
    assert result["predmort"] > 0.005
