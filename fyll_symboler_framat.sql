
-- Fyll i symbol_code där det är tomt genom att använda närmaste tidigare tillgängliga värde
UPDATE weather w1
JOIN (
  SELECT w2.timestamp AS ts1, (
    SELECT symbol_code FROM weather
    WHERE symbol_code != ''
      AND timestamp < w2.timestamp
    ORDER BY timestamp DESC
    LIMIT 1
  ) AS nearest_symbol
  FROM weather w2
  WHERE symbol_code = ''
) AS fix
ON w1.timestamp = fix.ts1
SET w1.symbol_code = fix.nearest_symbol;
