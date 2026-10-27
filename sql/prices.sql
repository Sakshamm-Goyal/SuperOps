-- id: prices
-- version: 2
-- key: sku,effective_from
-- sources: ref
-- params: region:identifier
SELECT provider, region, sku, unit, currency, price, effective_from, effective_to, rate_version, price_basis
FROM {ref}.prices
WHERE region = :region
ORDER BY sku, effective_from
