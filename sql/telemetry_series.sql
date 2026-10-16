-- id: telemetry_series
-- version: 1
-- sources: cloud
-- params: resource_key:resource_key, start:timestamp, end:timestamp
SELECT observed_at, cpu_percent, memory_bytes
FROM {cloud}.telemetry
WHERE provider = :resource_key.provider AND project_id = :resource_key.project AND resource_id = :resource_key.resource
  AND observed_at >= :start AND observed_at < :end
ORDER BY observed_at
