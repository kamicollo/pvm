# pvm
PVM

## Olist dataset

The `datasets.olist` module reads parquet files from `src/datasets/olist/`. These are generated from the
[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
and are not stored in git. Check the dataset page for its license terms.

1. Create a Kaggle account, open the dataset page above and accept its rules.
2. Create an API token under *Settings → API → Create New Token*. Save the downloaded `kaggle.json` to
   `~/.kaggle/kaggle.json` and restrict it with `chmod 600 ~/.kaggle/kaggle.json`.
3. From the repo root, run:

   ```sh
   make download_olist
   ```

   This downloads and unzips the CSVs into `src/datasets/olist/raw/`, then converts each one to a parquet file
   of the same name in `src/datasets/olist/`. It needs `uv` and network access. The raw CSVs are about 120 MB.

Run `make download_olist` again to refresh the data. Existing files are overwritten.
