BEGIN;

DROP TABLE IF EXISTS annual_watermain_breaks;

CREATE TABLE annual_watermain_breaks (
    calendar_year int4 PRIMARY KEY,
    days_in_year int4 NOT NULL,
    break_count int4 NOT NULL
);

INSERT INTO annual_watermain_breaks (calendar_year, days_in_year, break_count)
SELECT
    calendar_years.calendar_year,
    make_date(calendar_years.calendar_year + 1, 1, 1) - make_date(calendar_years.calendar_year, 1, 1),
    -- make_date function: MAKE_DATE(year, month, dat) e.g. MAKE_DATE(2026, 09, 23)
    -- so this grabs Jan01 of following year, - Jan01 of current year, converts result to int, that's `days_in_year`
    -- also SQL functions are case-insensitive, which bothers me, but whatever
    COUNT(watermain_breaks.break_date) AS break_count
FROM generate_series(1956, EXTRACT(YEAR FROM CURRENT_DATE)::int)
    AS calendar_years(calendar_year)
LEFT JOIN watermain_breaks
    ON  watermain_breaks.break_date >= make_date(calendar_years.calendar_year, 1, 1) -- break_date >= jan01, current year
    AND watermain_breaks.break_date <  make_date(calendar_years.calendar_year + 1, 1, 1) -- break_date < jan01, next year
GROUP BY calendar_years.calendar_year;

COMMIT;