-- id: billing_rows
-- version: 1
-- sources: cloud
-- params: start:timestamp, end:timestamp
SELECT billing_record_id, provider, project_id, resource_id, sku, usage_start, usage_end, usage_quantity, usage_unit, cost, currency, rate_version
FROM {cloud}.billing
WHERE usage_start >= :start AND usage_end <= :end
ORDER BY billing_record_id
