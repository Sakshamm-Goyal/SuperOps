-- id: carbon_factors
-- version: 1
-- sources: ref
-- params: region:identifier
SELECT region, kg_co2e_per_kwh, kwh_per_vcpu_hour, kwh_per_gib_hour, pue_included, method_version, effective_from, effective_to, factor_source
FROM {ref}.carbon_factors WHERE region = :region
