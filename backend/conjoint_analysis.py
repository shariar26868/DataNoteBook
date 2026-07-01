import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression


CHOICE_COLUMNS = [
    "chosen",
    "choice",
    "selected",
    "selected_option",
    "choice_option",
    "choice_label",
]
RESPONDENT_COLUMNS = ["respondent_id", "respondent", "person_id", "id"]
TASK_COLUMNS = ["task", "task_id", "question", "choice_task"]
SPECIALTY_COLUMNS = ["specialty", "segment", "group", "doctor_type", "role"]
ATTRIBUTE_NAMES = ["efficacy", "safety", "dosing", "price"]
PRICE_SYNONYMS = ["price", "cost", "amount", "fee"]
OPTION_PREFIX_CANDIDATES = [
    ("option_a_", "option_b_"),
    ("option_a_", "option_b_"),
    ("a_", "b_"),
    ("A_", "B_"),
    ("alt_a_", "alt_b_"),
]


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)
    if path.suffix.lower() in {".xls", ".xlsx"}:
        return pd.read_excel(path)
    raise ValueError("Unsupported file format. Use .csv, .xls or .xlsx")


def summarize_dataset(df: pd.DataFrame) -> None:
    print(f"Rows: {len(df)}, columns: {len(df.columns)}")
    print("Columns:")
    for name, dtype in df.dtypes.items():
        print(f"  - {name} ({dtype})")

    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if not missing.empty:
        print("\nTop columns with missing values:")
        print(missing.head(20).to_string())

    print("\nSample data:")
    print(df.head(5).to_string(index=False))


def find_choice_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.lower() in CHOICE_COLUMNS:
            return col
    return None


def normalize_choice_values(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.upper()
    s = s.replace(
        {
            "1": "A",
            "2": "B",
            "OPTION A": "A",
            "OPTION B": "B",
            "OPTION_A": "A",
            "OPTION_B": "B",
            "A": "A",
            "B": "B",
        }
    )
    return s


def find_option_prefixes(df: pd.DataFrame) -> tuple[str, str] | None:
    columns = set(df.columns)
    for prefix_a, prefix_b in OPTION_PREFIX_CANDIDATES:
        suffixes_a = {col[len(prefix_a) :] for col in columns if col.startswith(prefix_a)}
        suffixes_b = {col[len(prefix_b) :] for col in columns if col.startswith(prefix_b)}
        common = suffixes_a & suffixes_b
        if len(common) >= 2:
            return prefix_a, prefix_b
    # fallback: detect A_ / B_ style with identical suffixes
    suffixes_a = {col[2:] for col in columns if col.startswith("A_")}
    suffixes_b = {col[2:] for col in columns if col.startswith("B_")}
    if suffixes_a & suffixes_b:
        return "A_", "B_"
    suffixes_a = {col[2:] for col in columns if col.startswith("a_")}
    suffixes_b = {col[2:] for col in columns if col.startswith("b_")}
    if suffixes_a & suffixes_b:
        return "a_", "b_"
    return None


def infer_attribute_columns(df: pd.DataFrame, prefix_a: str, prefix_b: str) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    for attr in ATTRIBUTE_NAMES:
        left = prefix_a + attr
        right = prefix_b + attr
        if left in df.columns and right in df.columns:
            mapping[attr] = (left, right)
    if "price" not in mapping:
        for syn in PRICE_SYNONYMS:
            left = prefix_a + syn
            right = prefix_b + syn
            if left in df.columns and right in df.columns:
                mapping["price"] = (left, right)
                break
    return mapping


def has_conjoint_structure(df: pd.DataFrame) -> bool:
    choice_col = find_choice_column(df)
    prefixes = find_option_prefixes(df)
    if choice_col is None or prefixes is None:
        return False
    mapping = infer_attribute_columns(df, prefixes[0], prefixes[1])
    return bool(mapping)


def prepare_conjoint_data(df: pd.DataFrame) -> tuple[pd.DataFrame, str, dict[str, tuple[str, str]]]:
    choice_col = find_choice_column(df)
    if choice_col is None:
        raise ValueError("No choice column detected. Expected one of: " + ", ".join(CHOICE_COLUMNS))

    prefix_a, prefix_b = find_option_prefixes(df) or (None, None)
    if prefix_a is None or prefix_b is None:
        raise ValueError("No option A/B prefix pattern detected.")

    mapping = infer_attribute_columns(df, prefix_a, prefix_b)
    if not mapping:
        raise ValueError("No matching attribute columns found for option A/B prefixes.")

    cbc = df.copy()
    cbc[choice_col] = normalize_choice_values(cbc[choice_col])
    cbc = cbc[cbc[choice_col].isin(["A", "B"])].copy()
    cbc["y_choose_a"] = (cbc[choice_col] == "A").astype(int)

    for attr, (left, right) in mapping.items():
        if attr == "price":
            continue
        cbc[f"diff_{attr}"] = cbc[left].astype(str) + " vs " + cbc[right].astype(str)

    if "price" in mapping:
        left, right = mapping["price"]
        cbc["diff_price"] = pd.to_numeric(cbc[left], errors="coerce") - pd.to_numeric(cbc[right], errors="coerce")
        cbc = cbc.dropna(subset=["diff_price"])
    else:
        cbc["diff_price"] = np.nan

    return cbc, choice_col, mapping


def fit_choice_model(cbc: pd.DataFrame, mapping: dict[str, tuple[str, str]]):
    diff_cols = [f"diff_{attr}" for attr in mapping.keys() if attr != "price"]
    X_cat = pd.get_dummies(cbc[diff_cols], drop_first=True) if diff_cols else pd.DataFrame(index=cbc.index)
    if "price" in mapping:
        X_num = cbc[["diff_price"]].copy()
        X = pd.concat([X_cat, X_num], axis=1)
    else:
        X = X_cat

    if X.empty:
        raise ValueError("No design features could be built from the conjoint attributes.")

    y = cbc["y_choose_a"]
    model = LogisticRegression(max_iter=5000, solver="lbfgs")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        model.fit(X, y)
    coef_series = pd.Series(model.coef_[0], index=X.columns).sort_values(ascending=False)
    return model, coef_series, X, y


def estimate_level_utilities_from_diffs(cbc: pd.DataFrame, attr: str, mapping: dict[str, tuple[str, str]]):
    if attr not in mapping or attr == "price":
        return pd.Series(dtype=float), None

    left, right = mapping[attr]
    levels = sorted(
        pd.unique(
            pd.concat([cbc[left].astype(str), cbc[right].astype(str)], ignore_index=True)
        )
    )

    if len(levels) < 2:
        return pd.Series(dtype=float), None

    baseline = levels[0]
    rows = []
    targets = []
    for _, row in cbc.iterrows():
        a_level = str(row[left])
        b_level = str(row[right])
        vec = {lvl: int(a_level == lvl) - int(b_level == lvl) for lvl in levels[1:]}
        rows.append(vec)
        targets.append(row["y_choose_a"])

    X_attr = pd.DataFrame(rows).fillna(0.0)
    if X_attr.shape[1] == 0:
        return pd.Series({baseline: 0.0}), baseline

    y_attr = np.array(targets, dtype=float)
    attr_model = LogisticRegression(fit_intercept=False, max_iter=5000, solver="lbfgs")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        attr_model.fit(X_attr, y_attr)

    util = pd.Series(0.0, index=levels, dtype=float)
    util.loc[levels[1:]] = attr_model.coef_[0]
    util.loc[baseline] = 0.0
    return util.sort_values(ascending=False), baseline


def compute_relative_importance(attribute_utils: dict[str, pd.Series], price_coef: float | np.ndarray):
    rows = []
    for attr, util in attribute_utils.items():
        if attr == "price":
            continue
        if len(util) > 0:
            rng = util.max() - util.min()
        else:
            rng = np.nan
        rows.append({"attribute": attr, "utility_range": rng})

    if price_coef is not None and not pd.isna(price_coef):
        rows.append({"attribute": "price", "utility_range": abs(price_coef)})
    importance_df = pd.DataFrame(rows)
    total = importance_df["utility_range"].sum()
    importance_df["relative_importance_pct"] = (
        100 * importance_df["utility_range"] / total
        if total and not np.isnan(total)
        else np.nan
    )
    return importance_df.sort_values("relative_importance_pct", ascending=False).reset_index(drop=True)


def compute_alternative_importance(coef_series: pd.Series) -> pd.DataFrame:
    alt_rows = []
    for attr in ["efficacy", "safety", "dosing"]:
        cols = [c for c in coef_series.index if c.startswith(f"diff_{attr}_")]
        alt_score = coef_series.loc[cols].abs().sum() if cols else 0.0
        alt_rows.append({"attribute": attr, "alt_abs_coef_score": alt_score})
    alt_rows.append({"attribute": "price", "alt_abs_coef_score": abs(coef_series.get("diff_price", 0.0))})
    alt_df = pd.DataFrame(alt_rows)
    total = alt_df["alt_abs_coef_score"].sum()
    alt_df["alt_importance_pct"] = (
        100 * alt_df["alt_abs_coef_score"] / total
        if total and not np.isnan(total)
        else np.nan
    )
    return alt_df.sort_values("alt_importance_pct", ascending=False).reset_index(drop=True)


def build_profile(reference: dict[str, object], changes: dict[str, object]) -> dict[str, object]:
    out = reference.copy()
    out.update(changes)
    return out


def profile_diff_vector(profile: dict[str, object], competitor: dict[str, object], coef_series: pd.Series):
    diff = {}
    for coef_name in coef_series.index:
        if coef_name.startswith("diff_"):
            if coef_name == "diff_price":
                diff[coef_name] = float(profile["price"]) - float(competitor["price"])
            else:
                _, attr, level = coef_name.split("_", 2)
                diff[coef_name] = int(profile[attr] == level) - int(competitor[attr] == level)
    return diff


def choice_probability(profile: dict[str, object], competitor: dict[str, object], coef_series: pd.Series):
    diff = profile_diff_vector(profile, competitor, coef_series)
    delta_u = sum(coef_series.get(k, 0.0) * v for k, v in diff.items())
    return float(np.exp(delta_u) / (1 + np.exp(delta_u)))


def report_conjoint_results(df_path: Path):
    df = load_dataset(df_path)
    if not has_conjoint_structure(df):
        print("No detected conjoint structure in this dataset.")
        summarize_dataset(df)
        return None

    cbc, choice_col, mapping = prepare_conjoint_data(df)
    print(f"✅ Usable choice tasks: {len(cbc)}")
    print(f"✅ Respondents: {cbc[choice_col].nunique()}")
    print(f"✅ Detected attributes: {', '.join(sorted(mapping.keys()))}")

    model, coef_series, X, y = fit_choice_model(cbc, mapping)
    print(f"✅ Conjoint model fit on {X.shape[0]} tasks and {X.shape[1]} features")

    print("\nTop positive coefficients favoring Option A:")
    print(coef_series.head(10).to_string())
    print("\nTop negative coefficients favoring Option B:")
    print(coef_series.tail(10).to_string())

    attribute_utils = {}
    baselines = {}
    for attr in ["efficacy", "safety", "dosing"]:
        util, base = estimate_level_utilities_from_diffs(cbc, attr, mapping)
        attribute_utils[attr] = util
        baselines[attr] = base
        if not util.empty:
            print(f"\n{attr.capitalize()} part-worth utilities:")
            print(util.to_string())
            print(f"Baseline level fixed at 0: {base}")

    if "price" in mapping:
        price_coef = coef_series.get("diff_price", np.nan)
        print("\nPrice coefficient:")
        print(price_coef)
        attribute_utils["price"] = price_coef
    else:
        price_coef = np.nan
        print("\nPrice not detected; skipping price coefficient.")

    importance_df = compute_relative_importance(attribute_utils, price_coef)
    print("\nRelative importance of treatment attributes (%):")
    print(importance_df.to_string(index=False))

    alt_df = compute_alternative_importance(coef_series)
    print("\nAlternative importance definition (sum of absolute coefficients):")
    print(alt_df.to_string(index=False))

    return cbc, mapping, coef_series, importance_df, alt_df


def simulate_price_reduction(df_path: Path, price_from: float = 400.0, price_to: float = 300.0):
    df = load_dataset(df_path)
    if not has_conjoint_structure(df):
        print("Price reduction simulation skipped because dataset does not appear to be conjoint choice data.")
        return None

    cbc, choice_col, mapping = prepare_conjoint_data(df)
    if "price" not in mapping:
        print("Price reduction simulation skipped because no price attribute was detected.")
        return None

    model, coef_series, X, y = fit_choice_model(cbc, mapping)
    safety_ref = cbc[mapping["safety"][0]].mode().iloc[0] if "safety" in mapping else cbc[mapping[next(iter(mapping))][0]].mode().iloc[0]
    dosing_ref = cbc[mapping["dosing"][0]].mode().iloc[0] if "dosing" in mapping else cbc[mapping[next(iter(mapping))][0]].mode().iloc[0]
    price_ref = float(cbc[[mapping["price"][0], mapping["price"][1]]].stack().median())

    competitor_profile = {
        "efficacy": cbc[mapping["efficacy"][1]].mode().iloc[0] if "efficacy" in mapping else cbc[mapping[next(iter(mapping))][1]].mode().iloc[0],
        "safety": safety_ref,
        "dosing": dosing_ref,
        "price": price_ref,
    }
    baseline_profile = {
        "efficacy": cbc[mapping["efficacy"][0]].mode().iloc[0] if "efficacy" in mapping else competitor_profile["efficacy"],
        "safety": safety_ref,
        "dosing": dosing_ref,
        "price": price_from,
    }
    improved_profile = {**baseline_profile, "price": price_to}

    share_from = choice_probability(baseline_profile, competitor_profile, coef_series)
    share_to = choice_probability(improved_profile, competitor_profile, coef_series)
    gain = share_to - share_from

    print("\nPrice reduction simulation")
    print(f"Competitor profile: {competitor_profile}")
    print(f"Baseline profile at £{price_from}: {baseline_profile}")
    print(f"New profile at £{price_to}: {improved_profile}")
    print(f"Predicted share at £{price_from}: {share_from:.4f}")
    print(f"Predicted share at £{price_to}: {share_to:.4f}")
    print(f"Predicted share gain: {gain:.4f} ({gain * 100:.2f} pp)")
    return gain


def main():
    parser = argparse.ArgumentParser(description="Run conjoint analysis and dataset diagnostics.")
    parser.add_argument("--input", type=str, required=True, help="Path to the dataset CSV/XLSX file.")
    parser.add_argument("--price-from", type=float, default=400.0, help="Starting price for the price reduction simulation.")
    parser.add_argument("--price-to", type=float, default=300.0, help="Lower price for the price reduction simulation.")
    args = parser.parse_args()

    df_path = Path(args.input)
    try:
        print("=== Dataset summary ===")
        df = load_dataset(df_path)
        summarize_dataset(df)

        print("\n=== Conjoint analysis ===")
        report_conjoint_results(df_path)

        print("\n=== Price reduction simulation ===")
        simulate_price_reduction(df_path, args.price_from, args.price_to)
    except Exception as exc:
        print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
