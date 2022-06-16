# CLI for the STS Adult Cardiac Risk Calculator
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code
Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

A minimalist Python command line tool to query the STS (Society of Thoracic Surgeons) [Short-Term Risk Calculator](https://www.sts.org/resources/risk-calculator) (version 4.2).

# Overview
This tool might be helpful if you need to query the STS risk calculator repeatedly, for a bunch of patients.

The STS Calculator itself is a black box — patient parameters are passed to the STS API and a risk is returned (no computing happens client side).  A few (obvious) parameters impact mortality most heavily (e.g. ESRD). Unfortunately, the risk calculator somewhat randomly changes its input parameters every few years.


# Individual Usage

Procedure type and age are required (otherwise the STS calculator will return "NA" for everything). All other parameters are optional.

```
x
```

# Parsing Bulk .csv Records

```
x
```

# Inspiration

This code was inspired in part from [this script](https://github.com/aguirre-lab/sts-ml/blob/main/scripts/query_sts_calculator.py), from the JTCVS paper ["Prediction of operative mortality for patients undergoing cardiac surgical procedures without established risk scores", Ong et. al., 2021](https://pubmed.ncbi.nlm.nih.gov/34607725/).

# Citation
If you use this in your publication, please consider citing this as: **STS Risk Calculator CLI, Nicholas P. Semenkovich, 2022. https://github.com/semenko/sts-risk-calculator-cli**

# License
Released under the MIT License.  Copyright 2021, Nick Semenkovich <semenko@alum.mit.edu> https://nick.semenkovich.com/