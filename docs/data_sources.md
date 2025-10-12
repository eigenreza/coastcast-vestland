# Data sources and provenance

## Kartverket water level and tide

The Norwegian Mapping Authority Hydrographic Service operates the source API. CoastCast uses permanent station `BGO`, located at latitude 60.398046 and longitude 5.320487.

Requested series:

- quality-controlled observed water level
- astronomical tide prediction
- hourly interval
- mean sea level reference
- UTC timestamps

The learning target is the observed water level minus astronomical tide. Kartverket describes this difference as the weather effect or surge contribution.

Access is open and does not require registration. The data is licensed under Creative Commons Attribution 4.0. The pipeline identifies itself, limits requests to monthly chunks, and stores responses locally as requested by the provider.

References:

- [Kartverket tides and water-level data](https://www.kartverket.no/en/api-and-data/tides-and-water-level-data)
- [Water-level API explorer](https://vannstand.kartverket.no/tideapi_en.html)
- [Communication protocol](https://vannstand.kartverket.no/API%20for%20water%20level%20and%20tides%20-%20communication%20protocol_revJune2025.pdf)

Required attribution:

> Water-level observations and astronomical tide data: Norwegian Mapping Authority, Hydrographic Service, CC BY 4.0.

## Open-Meteo historical weather

CoastCast requests ECMWF IFS historical analysis values through Open-Meteo at the gauge coordinates. Open-Meteo documents ECMWF IFS availability from 2017 onward, which defines the beginning of the matched study window. The weather source provides a gap-free hourly context for:

- mean sea-level pressure
- 10 metre wind speed
- 10 metre wind direction
- 10 metre wind gusts
- precipitation
- 2 metre air temperature

The values are numerical weather analysis, not measurements from a sensor mounted beside the tide gauge. They combine observations and physical modeling. This distinction is preserved in the documentation and should remain visible in downstream reports.

References:

- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo data sources](https://open-meteo.com/en/docs)

Suggested attribution:

> Historical meteorological covariates supplied by Open-Meteo using ECMWF IFS analysis data.

## Temporal policy

Analytical observations are accepted only when their event timestamp falls from 1 January 2017 through 31 December 2025. The configuration, Python data contract, dbt singular test, and artifact metadata all enforce this rule. The completed source tables each contain 78,888 hourly rows with identical first and last timestamps.

Every cached response has request metadata, retrieval time, byte count, and a SHA-256 checksum. Cached bytes are verified before reuse, and completed writes are atomic. Operational metadata is not treated as an observation and never enters training features.

## Data boundaries and interpretation

These boundaries keep conclusions tied to the evidence used by the project:

- A model grid cell summarizes the wider atmosphere and cannot resolve every local wind effect in Bergen's complex coastal terrain.
- The Bergen gauge provides a precise point record; extending conclusions to other fjords or exposed coastal sites requires local validation.
- Provider archives may be revised after quality control. The immutable request cache preserves each completed run, while a clean refetch may receive updated values.
- Mean sea level is the project's reference datum. Comparison with chart datum or NN2000 requires an explicit conversion.
- Missing or provider-flagged extreme observations should receive domain review before safety-related interpretation.

## Responsible retrieval

The pipeline makes one request per configured time chunk, applies bounded exponential backoff, honors HTTP errors, and caches successful responses. It does not poll either provider continuously.
