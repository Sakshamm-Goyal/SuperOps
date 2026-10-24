-- id: model_prices
-- version: 1
-- sources: ref
-- params:
SELECT model_family, input_per_million, output_per_million, currency, effective_from, effective_to, price_basis FROM {ref}.model_prices
