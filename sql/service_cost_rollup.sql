-- id: service_cost_rollup
-- version: 1
-- key: service_id
-- sources: cloud, ai
-- params: service_id:service_id, start:timestamp, end:timestamp
-- Cross-source federation: each fact is aggregated at its own grain BEFORE the join (F-JOIN).
SELECT cl.service_id, cl.cloud_cost, cl.currency, cl.billing_rows, ai.model_calls, ai.input_tokens, ai.output_tokens
FROM (SELECT i.service_id, SUM(b.cost) AS cloud_cost, MIN(b.currency) AS currency, COUNT(*) AS billing_rows
      FROM {cloud}.billing b JOIN {cloud}.inventory i
        ON b.provider = i.provider AND b.project_id = i.project_id AND b.resource_id = i.resource_id
      WHERE i.service_id = :service_id AND b.usage_start >= :start AND b.usage_end <= :end
      GROUP BY i.service_id) cl
JOIN (SELECT r.service_id, SUM(CASE WHEN c.call_kind = 'model' THEN 1 ELSE 0 END) AS model_calls,
             SUM(c.input_tokens) AS input_tokens, SUM(c.output_tokens) AS output_tokens
      FROM {ai}.ai_calls c JOIN {ai}.ai_runs r ON c.run_id = r.run_id
      WHERE r.service_id = :service_id AND c.evaluation_partition = 'development' AND c.access_class = 'agent_readable'
      GROUP BY r.service_id) ai
  ON cl.service_id = ai.service_id
