<div align="center">
 <h1><strong>Bulk STS Risk Calculator Query Tool</strong></h1>

[![License: GPL v3](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Code
Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)


Repeatedly query the Society of Thoracic Surgeons Adult Cardiac Risk Calculator using bulk .csv patient data.

</div>

![demo](./docs/demo.gif)

# Overview
This is a minimalist Python command line tool to query the STS risk calculator with bulk patient records. There is no upper limit to your query size -- this has been successfully run on datasets of ~500+ patients. 

The STS Calculator itself is a black box — patient parameters are passed to the STS API and a risk is returned (almost no computing happens client side).  A few (obvious) parameters impact mortality most heavily (e.g. ESRD). Unfortunately, the risk calculator somewhat randomly changes its input parameters every few years. This code was inspired in part by [this script](https://github.com/aguirre-lab/sts-ml/blob/main/scripts/query_sts_calculator.py) and by [this documentation](https://github.com/mstubna/STS-Calculator).

## Features
- Programmatically queries the STS [Short-Term Risk Calculator](https://www.sts.org/resources/risk-calculator) (version 4.2)
- Parses input .csv records of patients
- Performs automatic validation of most input records
- Optionally override individual parameters from your bulk records
    - For example, how does mortality change if all patients have the same age or renal function?
- Returns all avalable STS risk model parameters (mortality, prolonged ventilation, reoperation, etc.)


# Example Usage

Procedure type and age are required (otherwise the STS calculator will return "NA" for everything). This script also requires `weightkg` and `heightcm`. All other parameters are optional.




## Full Options

```
$ ./sts-query.py
usage: sts-query.py [options]

Query the STS Short-Term Risk Calculator (v4.2) via a CSV. Please cite this repository if you're using in a publication.

optional arguments:
  -h, --help            show this help message and exit
  --csv patient-data.csv
                        Your input patient data .csv. (default: None)
  --dry-run             Only validate data, do not query the STS API. (default: False)
  --output results.csv  Where to store results. (default: results.csv)
  --override stsvariable=value [stsvariable=value ...]
                        Override values sent to the STS API, e.g. make all patients the same age with --override age=50 (default: None)
```


# Citation
If you use this in your publication, please consider citing this work as: **STS Risk Calculator CLI, Nicholas P. Semenkovich, 2022. https://github.com/semenko/sts-risk-calculator-cli**

# License
Released under the MIT License.  Copyright 2022, Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com/