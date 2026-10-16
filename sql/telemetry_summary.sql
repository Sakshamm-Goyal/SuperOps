-- id: telemetry_summary
-- version: 1
-- sources: cloud
-- params: start:timestamp, end:timestamp
SELECT provider, project_id, resource_id,
       COUNT(*) AS row_count, COUNT(DISTINCT observed_at) AS distinct_times,
       COUNT(cpu_percent) AS cpu_rows, COUNT(memory_bytes) AS memory_rows,
       AVG(cpu_percent) AS avg_cpu_percent, MAX(cpu_percent) AS peak_cpu_percent,
       MAX(memory_bytes) AS peak_memory_bytes, MIN(observed_at) AS first_observed_at, MAX(observed_at) AS last_observed_at
FROM {cloud}.telemetry
WHERE observed_at >= :start AND observed_at < :end
GROUP BY provider, project_id, resource_id
ORDER BY provider, project_id, resource_id
