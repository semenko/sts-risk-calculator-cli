<div align="center">
 <h1><strong>Bulk STS Risk Calculator Query Tool</strong></h1>

[![License: GPL v3](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Code
Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)


Repeatedly query the Society of Thoracic Surgeons Adult Cardiac Risk Calculator using bulk .csv patient data.


![demo](./docs/demo.gif)

</div>


# Overview
This is a minimalist Python command line tool to query the STS risk calculator with bulk patient records. There is no upper limit to your query size -- this has been successfully run on datasets of ~500+ patients. 

The STS Calculator itself is a black box — patient parameters are passed to the STS API and a risk is returned (almost no computing happens client side).  A few obvious parameters impact mortality heavily (e.g. ESRD). Unfortunately, the risk calculator somewhat randomly changes its input parameters every few years. This code was inspired in part by [this script](https://github.com/aguirre-lab/sts-ml/blob/main/scripts/query_sts_calculator.py) and by [this documentation](https://github.com/mstubna/STS-Calculator).


## Features
- Programmatically queries the STS [Short-Term Risk Calculator](https://www.sts.org/resources/risk-calculator) (version 4.2)
- Parses input .csv records of patients
- Performs automatic validation of most input records
- Optionally override individual parameters from your bulk records
    - For example, how does mortality change if all patients have the same age or renal function?
- Returns all avalable STS risk model parameters (mortality, prolonged ventilation, reoperation, etc.)


# Example Usage

You must provide a CSV with a unique **id** per row, followed by a minimum of **procid**, **age**, **weightkg**, and **heightkg**.

All other parameters are optional. The most critical step is formatting your data to **exactly** match the STS risk parameter names & values (detailed below). The calculator API is inflexible -- spacing, capitalization, etc. must be identical to the STS database.


### 1. Define input patient .csv (e.g. sample_data.csv)
```
id,procid,age,gender,surgdt,weightkg,heightcm,creatlst,payorprim
1,1,56,Male,08/11/2017,72,124,1.5,"Commercial Health Insurance"
2,3,72,Female,12/16/2018,60,96,2.9,
3,4,42,Male,7/21/2021,50,110,1.2,"Non-U.S. Plan"
```

### 2. Run sts-query

```
$ ./sts-query.py --csv sample_data.csv --output sample_results.csv
Validating CSV entries...
Valid!

Querying STS API.
100%|████████████████████████████████████████████████████████████████| 3/3 [00:01<00:00,  2.34it/s]

Done!
Results written to: sample_results.csv
```

### 3. Inspect results
```
$ cat sample_results.csv
id,predmort,predmm,preddeep,pred14d,predstro,predvent,predrenf,predreop,pred6d
1,0.00698,0.05765,0.00317,0.02174,0.00269,0.03349,0.01563,0.01304,0.65328
2,0.10089,0.48756,0.0028,0.25896,0.01259,0.30205,0.21811,0.04919,0.06589
3,0.01906,0.14991,0.00416,0.04517,0.00802,0.0852,0.02145,0.03302,0.38684
```

# Full Options

```
$ ./sts-query.py
usage: sts-query.py [options]

Query the STS Short-Term Risk Calculator (v4.2) via a CSV.
Please cite this repository if you're using in a publication.

optional arguments:
  -h, --help            show this help message and exit
  --csv patient-data.csv
                        Your input patient data .csv. (default: None)
  --dry-run             Only validate data, do not query the STS API. (default: False)
  --output results.csv  Where to store results. (default: results.csv)
  --override stsvariable=value [stsvariable=value ...]
                        Override values sent to the STS API,
                        e.g. make all patients the same age with --override age=50 (default: None)
```

# Override Parameters

Using the `--override` flag, you can provide parameters to the STS API that override or fill in missing data in your .csv. For example, you can pass `--override age=50` to set the age of *all* patients to 50. You can provide multiple values, for example `--override dialysis=Yes procid=2` will set every patient on dialysis and set the `procid` to 2 (AVR).

This can be useful when comparing mortality predictions associated with population-level interventions. For example, you can ask: *What if all these patients stopped smoking?* or *What if everyone had good diabetes control?*



# Citation
If you use this in your publication, please consider citing this work as: **STS Risk Calculator CLI, Nicholas P. Semenkovich, 2022. https://github.com/semenko/sts-risk-calculator-cli**

# License
Released under the MIT License.  Copyright 2022, Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com/