"""Small toy datasets for testing/illustration purposes."""

import io

import polars as pl

fx: pl.DataFrame = pl.read_csv(
    io.StringIO(
        """product	country	year	volume	price_in_lc	fx_rate	price	revenue
A	US	2020	100	20	1	20	2000
A	US	2021	100	20	1	20	2000
B	China	2020	300	12	0.6	7.2	2160
B	China	2021	360	11.8	0.65	7.67	2761.2
B	Japan	2020	250	15	0.8	12	3000
B	Japan	2021	180	18	0.6	10.8	1944
C	China	2020	200	3	0.6	1.8	360
C	China	2021	270	2.9	0.65	1.885	508.95
C	Japan	2020	200	6	0.8	4.8	960
C	Japan	2021	150	8	0.6	4.8	720""",
    ),
    separator="\t",
)
