import os
from datetime import timedelta
from pathlib import Path

import pandas as pd
from prefect import flow, task
from prefect.tasks import task_input_hash
from prefect_gcp.cloud_storage import GcsBucket



@task(retries=3, log_prints=True, cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
def fetch(dataset_url: str) -> pd.DataFrame:
    """Read data from url to pandas DataFrame"""

    df = pd.read_csv(dataset_url)
    return df


@task()
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Fix DataFrame issues."""
    df['lpep_pickup_datetime'] = pd.to_datetime(df['lpep_pickup_datetime'])
    df['lpep_dropoff_datetime'] = pd.to_datetime(df['lpep_dropoff_datetime'])
    print(df.head(2))
    print(f'columns: {df.dtypes}')
    print(f'rows: {(df)}')
    
    return df


@task()
def write_local(df: pd.DataFrame, color: str, dataset_file: str) -> Path:
    """Write data to local parquet file."""
    absolute_path = os.path.dirname(__file__)
    relative_path = f'data/{color}'
    full_path = os.path.join(absolute_path, relative_path)
    path = Path(f'{full_path}/{dataset_file}.parquet')
    df.to_parquet(path, compression='gzip')

    return path


@task()
def write_to_gcs(path: Path, color: str, file_name: str) -> None:
    """Write parquet file to google cloud storage."""
    gcs_buck = GcsBucket.load("dtc-gcs")
    gcs_buck.upload_from_path(
        from_path=f"{path}",
        to_path=f'data/{color}/{file_name}.parquet',
        timeout=240
    )


@flow(name="Ingest to GCP (Homework Q4)", log_prints=True)
def etl_web_to_gcs(color: str = 'green', year: int = 2020, months: list[int] = [11]) -> None:
    """The main ETL function"""

    for month in months:

        dataset_file = f'{color}_tripdata_{year}-{month:02}'
        dataset_url = f'https://github.com/DataTalksClub/nyc-tlc-data/releases/download/{color}/{dataset_file}.csv.gz'

        df = fetch(dataset_url)
        print(f"Rows befor cleaning: {df.shape[0]}")
        df_clean = clean(df)
        print(f"Rows after cleaning: {df_clean.shape[0]}")
        path = write_local(df_clean, color, dataset_file)
        write_to_gcs(path, color, dataset_file)


if __name__ == '__main__':
    etl_web_to_gcs()
