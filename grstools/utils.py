"""
Utilities to manage files.
"""

import logging

import pandas as pd

from genetest.subscribers import ResultsMemory
from genetest.analysis import execute_formula
from genetest.phenotypes.text import TextPhenotypes


logger = logging.getLogger(__name__)


COL_TYPES = {
    "name": str, "chrom": str, "pos": int, "reference": str, "risk": str,
    "p-value": float, "effect": float
}


def parse_computed_grs_file(filename):
    return pd.read_csv(filename, sep=",", index_col="sample")


def parse_grs_file(filename, p_threshold=1, maf_threshold=0, sep=",",
                   log=False):
    """Parse a GRS file.

    The mandatory columns are:
        - name (variant name)
        - chrom (chromosome, a str))
        - pos (position, a int)
        - reference (reference allele)
        - risk (effect/risk allele)
        - p-value (p-value, a float)
        - effect (beta or OR or other form of weight, a float)

    Optional columns are:
        - maf

    Returns:
        A pandas dataframe.

    """
    df = pd.read_csv(filename, sep=sep, dtype=COL_TYPES)

    cols = list(COL_TYPES.keys())

    # Optional columns.
    if "maf" in df.columns:
        cols.append("maf")

    # This will raise a KeyError if needed.
    df = df[cols]

    # Make the alleles uppercase.
    df["reference"] = df["reference"].str.upper()
    df["risk"] = df["risk"].str.upper()

    # Apply thresholds.
    if log:
        logger.info("Applying p-value threshold (p <= {})."
                    "".format(p_threshold))

    df = df.loc[df["p-value"] <= p_threshold, :]

    if "maf" in df.columns:
        if log:
            logger.info("Applying MAF threshold (MAF >= {})."
                        "".format(maf_threshold))
        df = df.loc[df["maf"] >= maf_threshold, :]

    return df


def mr_effect_estimate():
    # TODO
    pass


def regress(model, test, grs_filename, phenotypes_filename,
            phenotypes_sample_column="sample", phenotypes_separator=","):
    """Regress a GRS on a phenotype."""
    # Read the GRS.
    grs = TextPhenotypes(grs_filename, "sample", ",", "", False)

    # Read the other phenotypes.
    phenotypes = TextPhenotypes(
        phenotypes_filename,
        phenotypes_sample_column,
        phenotypes_separator, "", False
    )

    phenotypes.merge(grs)

    subscriber = ResultsMemory()

    # Check that the GRS was included in the formula.
    if "grs" not in model:
        raise ValueError(
            "The grs should be included in the regression model. For example, "
            "'phenotype ~ grs + age' would be a valid model, given that "
            "'phenotype' and 'age' are defined in the phenotypes file."
        )

    # Make sure the test is linear or logistic.
    if test not in {"linear", "logistic"}:
        raise ValueError("Statistical test should be logistic or linear.")

    # Execute the test.
    execute_formula(
        phenotypes, None, model, test,
        test_kwargs=None,
        subscribers=[subscriber],
        variant_predicates=None,
    )

    # Get the R2, the beta, the CI and the p-value.
    results = subscriber.results
    if len(results) != 1:
        raise NotImplementedError(
            "Only simple, single-group regression models are supported."
        )
    results = results[0]

    out = {}

    out["beta"] = results["grs"]["coef"]
    out["CI"] = (results["grs"]["lower_ci"], results["grs"]["upper_ci"])
    out["p-value"] = results["grs"]["p_value"]

    if test == "linear":
        out["intercept"] = results["intercept"]["coef"]
        out["R2"] = results["MODEL"]["r_squared_adj"]

    return out
