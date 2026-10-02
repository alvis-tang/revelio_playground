-- Inspect your schema/table/columns first and adjust identifiers if necessary.
-- Values are bound separately, never interpolated into SQL.
SELECT rcid, country, startdate, enddate
FROM revelio.individual_positions
WHERE rcid = %(rcid)s
  AND country = %(country)s
  AND startdate <= %(end_date)s
  AND (enddate IS NULL OR enddate >= %(start_date)s)
LIMIT %(limit)s
