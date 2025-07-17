# tree-canopy

We forecast forest canopy change using a binary classification target:
1. **High Canopy Growth** – The classification compares forest canopy change between 2015 and 2019 (a 4-year period), and counties with a ≥5% increase are labeled as high growth (1), others as 0.
2. **Stable/Declining** – All other counties.

## Forest Canopy Change as Target

[**Our Forest Canopy Colab**](https://colab.research.google.com/drive/10i3CP3Tgoxxj7PTxvr6YGw9AaxoI4Kxu?usp=sharing) prepares forest canopy data for use in our [RealityStream ML](../realitystream/) pipeline. The dataset is retrieved using the [**DataCommons API**](https://datacommons.org/) and paired with county-level geographic information based on FIPS codes.

The Colab notebook generates a `.csv` file that classifies each U.S. county into two groups based on their **relative forest cover growth over the past 4 years**.

View .csv output: [tree-canopy/targets](https://github.com/ModelEarth/tree-canopy/tree/main/input/targets)

This dataset is based on **Copernicus-derived forest land cover** as a percentage, accessed through DataCommons for each U.S. county from the most recent available years (e.g., 2015-2019).

---

## 📈 Processing Steps

**1. County Metadata Collection**:
   - Retrieved all counties in the U.S. using `get_places_in(["country/USA"], "County")`.
   - Extracted **county and state names** for each region.

**2. Forest Land Cover Data Retrieval**:
   - Queried DataCommons for the variable `LandCoverFraction_Forest`.
   - Fetched multi-year data (e.g., 2015–2019) per county.

**3. Determine Growth Window**:
   - Identified the **most recent year** of data.
   - Compared it to data from **years prior**.

**4. Merge and Clean Data**:
   - Cleaned FIPS codes and renamed columns for consistency.
   - Removed " County" suffix and standardized capitalization.

**5. Calculate Relative Growth**:
   - Computed:
     ```python
     relative_growth = ((recent - start) / start) * 100
     ```
   - A county with a **≥5% increase** in forest cover is labeled as `1` (high growth), otherwise `0`.

**6. Export Final Target File**:
   - Saved to:
     ```
     input/targets/forest_canopy_data_target.csv
     ```
   - Columns:
     - `Fips`: U.S. county code
     - `Target`: Binary target

---

## 💡 How It Works

The `.csv` file is used as a **target input** for ML models predicting forest canopy trends based on other features (e.g., economic activity).

You can plug this into any modeling workflow by referencing the parameter YAML described below.

---

## 📦 Target YAML Configuration

```yaml
folder: naics6-forestcanopy-counties-simple
features:
  data: industries
  common: Fips
  path: https://raw.githubusercontent.com/ModelEarth/community-timelines/main/training/naics2/US/counties/2020/US-ME-training-naics2-counties-2020.csv
targets:
  data: forest_canopy
  path: https://raw.githubusercontent.com/ModelEarth/tree-canopy/main/input/targets/forest_canopy_data_target.csv
models: rbf































