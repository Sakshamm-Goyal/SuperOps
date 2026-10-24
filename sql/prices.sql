-- id: prices
-- version: 1
-- sources: ref
-- params: region:identifier
SELECT provider, region, sku, unit, currency, price, effective_from, effective_to, rate_version, price_basis
FROM {ref}.prices
WHERE provider = 'gcp' AND region = :region
ORDER BY sku, effective_from
