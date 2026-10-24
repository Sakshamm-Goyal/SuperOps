-- id: ai_usage_by_run
-- version: 1
-- key: run_id
-- sources: ai
-- params: service_id:service_id
SELECT r.run_id, r.workflow_version, r.config_json, r.cases,
       SUM(CASE WHEN c.call_kind = 'model' THEN 1 ELSE 0 END) AS model_calls,
       SUM(CASE WHEN c.call_kind = 'model' AND c.attempt > 1 THEN 1 ELSE 0 END) AS retries,
       SUM(CASE WHEN c.call_kind = 'tool' THEN 1 ELSE 0 END) AS tool_calls,
       SUM(c.input_tokens) AS input_tokens, SUM(c.output_tokens) AS output_tokens, SUM(c.tool_cost) AS tool_cost
FROM {ai}.ai_runs r JOIN {ai}.ai_calls c ON c.run_id = r.run_id
WHERE r.service_id = :service_id AND r.evaluation_partition = 'development' AND r.access_class = 'agent_readable'
  AND c.evaluation_partition = 'development' AND c.access_class = 'agent_readable'
GROUP BY r.run_id, r.workflow_version, r.config_json, r.cases
ORDER BY r.run_id
