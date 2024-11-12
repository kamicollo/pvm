import polars as pl
import io

fx = pl.read_csv(
    io.StringIO(
        """product	country	year	volume	price_in_lc	fx_rate	price	revenue
A	US	2020	100	10	1	10	1000
B	Japan	2020	200	15	1.2	18	3600
C	China	2020	400	12	1.5	18	7200
C	Japan	2020	200	15	1.2	18	3600
B	China	2020	400	12	1.5	18	7200
A	US	2021	150	11	1	11	1650
B	Japan	2021	150	15	1.15	17.25	2587.5
C	China	2021	420	9	1.7	15.3	6426
C	Japan	2021	150	15	1.15	17.25	2587.5
B	China	2021	420	9	1.7	15.3	6426"""
    ),
    separator="\t",
)
