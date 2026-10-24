-- id: ai_duplicate_lookups
-- version: 1
-- key: run_id,tool_name
-- sources: ai
-- params: service_id:service_id
SELECT d.run_id, d.tool_name, SUM(d.n - 1) AS duplicate_calls
FROM (SELECT c.run_id, c.tool_name, c.args_hash, COUNT(*) AS n
      FROM {ai}.ai_calls c JOIN {ai}.ai_runs r ON c.run_id = r.run_id
      WHERE r.service_id = :service_id AND c.call_kind = 'tool'
        AND c.evaluation_partition = 'development' AND c.access_class = 'agent_readable'
      GROUP BY c.run_id, c.tool_name, c.args_hash) d
WHERE d.n > 1
GROUP BY d.run_id, d.tool_name
ORDER BY d.run_id, d.tool_name
